import sqlite3
import sys
from uuid import UUID
from unittest.mock import AsyncMock, MagicMock, patch

# Redirect bot.db to :memory: to keep workspace clean
original_connect = sqlite3.connect
def mock_connect(database, *args, **kwargs):
    if database == "bot.db":
        return original_connect(":memory:", *args, **kwargs)
    return original_connect(database, *args, **kwargs)
sqlite3.connect = mock_connect

import unittest  # noqa: E402

from src.bot.db import Database  # noqa: E402
from src.bot.queue_worker import QueueManager  # noqa: E402
from src.bot.reliability import PipelineAbortError  # noqa: E402
from src.database.models import JobQueue  # noqa: E402


class TestQueueWorkerRetry(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Create an in-memory database instance
        self.db = Database(":memory:")
        self.queue_manager = QueueManager(self.db)
        session = self.db.Session()
        session.query(JobQueue).delete()
        session.commit()

    def tearDown(self):
        self.db.conn.close()

    @patch("src.bot.queue_worker.process_report")
    @patch("src.bot.queue_worker.asyncio.sleep", new_callable=AsyncMock)
    @patch("src.bot.utils.send_telegram_message", new_callable=AsyncMock)
    @patch("src.bot.session.get_session")
    @patch("src.bot.session.save_session")
    async def test_transient_error_retry_success(
        self, mock_save, mock_get, mock_send, mock_sleep, mock_process
    ):
        """A job that fails once with a transient error succeeds on retry."""
        call_count = 0

        async def side_effect(job):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Transient rate limit")
            return "Success"

        mock_process.side_effect = side_effect

        # Enqueue a job for user 123
        self.db.enqueue_job(123)
        job = self.db.dequeue_job()
        self.assertIsNotNone(job)
        self.assertEqual(job["retry_count"], 0)

        # Run the job
        await self.queue_manager._run_job(job)

        # Verify transient error occurred:
        # 1. sleep should be called once with backoff 2**0 = 1 sec
        mock_sleep.assert_called_once_with(1)

        # 2. Database should have marked it back to pending with retry_count = 1
        refetched_job = self.db.dequeue_job()
        self.assertIsNotNone(refetched_job)
        self.assertEqual(refetched_job["retry_count"], 1)

        # 3. No permanent failure notification sent yet
        mock_send.assert_not_called()

        # Now run it again (2nd attempt). It will succeed.
        await self.queue_manager._run_job(refetched_job)

        # Verify it completed successfully in DB
        session = self.db.Session()
        job_obj = session.query(JobQueue).filter_by(id=UUID(job["id"])).first()
        self.assertIsNotNone(job_obj)
        self.assertEqual(job_obj.status, "completed")

    @patch("src.bot.queue_worker.process_report")
    @patch("src.bot.queue_worker.asyncio.sleep", new_callable=AsyncMock)
    @patch("src.bot.utils.send_telegram_message", new_callable=AsyncMock)
    @patch("src.bot.session.get_session")
    @patch("src.bot.session.save_session")
    async def test_pipeline_abort_immediate_failure(
        self, mock_save, mock_get, mock_send, mock_sleep, mock_process
    ):
        """A PipelineAbortError triggers immediate permanent failure and notifies the user."""
        mock_process.side_effect = PipelineAbortError("Profile is incomplete")

        # Mock the session returned by get_session
        mock_session = MagicMock()
        mock_session.step = "PROCESSING"
        mock_get.return_value = mock_session

        # Enqueue a job
        self.db.enqueue_job(123)
        job = self.db.dequeue_job()

        # Run the job
        await self.queue_manager._run_job(job)

        # Verify no sleep occurred (no retries for fatal errors)
        mock_sleep.assert_not_called()

        # Verify job is marked as failed in database
        session = self.db.Session()
        job_obj = session.query(JobQueue).filter_by(id=UUID(job["id"])).first()
        self.assertIsNotNone(job_obj)
        self.assertEqual(job_obj.status, "failed")

        # Verify session step was reset to COMPLETE
        self.assertEqual(mock_session.step, "COMPLETE")
        mock_save.assert_called_once_with(mock_session)

        # Verify user was notified via Telegram
        mock_send.assert_called_once_with(
            123,
            "Sorry, we encountered a calculation issue with your report. Please try again shortly.",
        )

    @patch("src.bot.queue_worker.process_report")
    @patch("src.bot.queue_worker.asyncio.sleep", new_callable=AsyncMock)
    @patch("src.bot.utils.send_telegram_message", new_callable=AsyncMock)
    @patch("src.bot.session.get_session")
    @patch("src.bot.session.save_session")
    async def test_exceed_max_retries(
        self, mock_save, mock_get, mock_send, mock_sleep, mock_process
    ):
        """A job that continually raises transient errors fails permanently on the 3rd attempt."""
        mock_process.side_effect = RuntimeError("Always timeout")

        # Mock session
        mock_session = MagicMock()
        mock_session.step = "PROCESSING"
        mock_get.return_value = mock_session

        # Enqueue a job
        self.db.enqueue_job(123)

        # Attempt 1: retry_count = 0. Fails and goes back to pending.
        job = self.db.dequeue_job()
        await self.queue_manager._run_job(job)
        mock_sleep.assert_called_once_with(1)
        mock_sleep.reset_mock()

        # Attempt 2: retry_count = 1. Fails and goes back to pending.
        job = self.db.dequeue_job()
        self.assertEqual(job["retry_count"], 1)
        await self.queue_manager._run_job(job)
        mock_sleep.assert_called_once_with(2)
        mock_sleep.reset_mock()

        # Attempt 3: retry_count = 2. Fails and triggers permanent failure.
        job = self.db.dequeue_job()
        self.assertEqual(job["retry_count"], 2)
        await self.queue_manager._run_job(job)

        # Verify no sleep on permanent failure
        mock_sleep.assert_not_called()

        # Verify job marked failed in DB
        session = self.db.Session()
        job_obj = session.query(JobQueue).filter_by(id=UUID(job["id"])).first()
        self.assertIsNotNone(job_obj)
        self.assertEqual(job_obj.status, "failed")

        # Verify session reset to COMPLETE
        self.assertEqual(mock_session.step, "COMPLETE")
        mock_save.assert_called_once_with(mock_session)

        # Verify Telegram warning dispatched
        mock_send.assert_called_once_with(
            123,
            "Sorry, we encountered a calculation issue with your report. Please try again shortly.",
        )


if __name__ == "__main__":
    unittest.main()
