import asyncio
import os
import tempfile
from unittest.mock import patch

import pytest

from src.bot.db import Database
from src.bot.queue_worker import QueueManager


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    db = Database(path)
    yield db
    db.close()
    os.remove(path)


@pytest.mark.asyncio
async def test_queue_concurrency_deduplication(temp_db):
    """
    Simulate 50 concurrent add_job calls from the same user to ensure
    race conditions are prevented by the asyncio.Lock, and de-duplication
    strictly limits the queue to 1 active job at a time.
    """
    queue_manager = QueueManager(temp_db)
    user_id = 999

    # Ensure user exists as a normal user (FREE tier, limit 2)
    temp_db.upsert_user(user_id, role="user", tier="FREE")

    # Mock get_user_limits to avoid needing full app setup
    with patch("src.bot.security.get_user_limits", return_value={"max_reports_per_day": 2}):
        # Fire 50 concurrent requests
        tasks = [queue_manager.add_job(user_id) for _ in range(50)]
        results = await asyncio.gather(*tasks)

        # With strict sequential processing via Lock, exactly 1 should succeed
        success_count = sum(1 for r in results if r is True)
        assert success_count == 1, f"Expected exactly 1 successful job due to dedup, got {success_count}"

        # Verify DB state
        jobs = temp_db.get_active_jobs(user_id)
        assert len(jobs) == 1, f"Expected 1 active job in DB, got {len(jobs)}"
