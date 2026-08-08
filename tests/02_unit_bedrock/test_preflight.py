import unittest
from unittest.mock import patch

# Import the module under test
from src.bot.preflight import run_preflight


class TestPreflightGracefulDegradation(unittest.IsolatedAsyncioTestCase):
    @patch("src.bot.preflight.sys.exit")
    @patch("src.bot.preflight.check_env_vars")
    @patch("src.bot.preflight.check_database")
    @patch("src.bot.preflight.check_telegram_token")
    @patch("src.bot.preflight.check_telegram_webhook")
    @patch("src.bot.preflight.check_openrouter_api")
    @patch("src.bot.preflight.check_bazirag_mcp")
    @patch("src.bot.preflight.check_bgem3")
    @patch("src.bot.preflight.check_qdrant")
    async def test_all_systems_go_exit_zero(
        self,
        mock_qdrant,
        mock_bgem3,
        mock_bazirag,
        mock_or,
        mock_webhook,
        mock_token,
        mock_db,
        mock_env,
        mock_exit,
    ):
        """If all critical and optional systems are online, preflight exits with 0."""
        # Set all systems to online (True)
        mock_env.return_value = True
        mock_db.return_value = True
        mock_token.return_value = True
        mock_webhook.return_value = True
        mock_or.return_value = True
        mock_bazirag.return_value = True
        mock_bgem3.return_value = True
        mock_qdrant.return_value = True

        await run_preflight()

        mock_exit.assert_called_once_with(0)

    @patch("src.bot.preflight.notify_admin_failure")
    @patch("src.bot.preflight.sys.exit")
    @patch("src.bot.preflight.check_env_vars")
    @patch("src.bot.preflight.check_database")
    @patch("src.bot.preflight.check_telegram_token")
    @patch("src.bot.preflight.check_telegram_webhook")
    @patch("src.bot.preflight.check_openrouter_api")
    @patch("src.bot.preflight.check_bazirag_mcp")
    @patch("src.bot.preflight.check_bgem3")
    @patch("src.bot.preflight.check_qdrant")
    async def test_optional_services_offline_exit_one(
        self,
        mock_qdrant,
        mock_bgem3,
        mock_bazirag,
        mock_or,
        mock_webhook,
        mock_token,
        mock_db,
        mock_env,
        mock_exit,
        mock_notify,
    ):
        """If optional services are offline but criticals are up, preflight still exits with 1 (all-or-nothing policy)."""
        mock_env.return_value = True
        mock_db.return_value = True
        mock_token.return_value = True
        mock_webhook.return_value = True
        mock_or.return_value = True

        mock_bazirag.return_value = False
        mock_bgem3.return_value = False
        mock_qdrant.return_value = False

        await run_preflight()

        mock_exit.assert_called_once_with(1)

    @patch("src.bot.preflight.notify_admin_failure")
    @patch("src.bot.preflight.sys.exit")
    @patch("src.bot.preflight.check_env_vars")
    @patch("src.bot.preflight.check_database")
    @patch("src.bot.preflight.check_telegram_token")
    @patch("src.bot.preflight.check_telegram_webhook")
    @patch("src.bot.preflight.check_openrouter_api")
    @patch("src.bot.preflight.check_bazirag_mcp")
    @patch("src.bot.preflight.check_bgem3")
    @patch("src.bot.preflight.check_qdrant")
    async def test_critical_failure_exit_one(
        self,
        mock_qdrant,
        mock_bgem3,
        mock_bazirag,
        mock_or,
        mock_webhook,
        mock_token,
        mock_db,
        mock_env,
        mock_exit,
        mock_notify,
    ):
        """If any critical system is offline, preflight exits with 1 regardless of optional systems."""
        mock_env.return_value = True
        mock_db.return_value = False
        mock_token.return_value = True
        mock_webhook.return_value = True
        mock_or.return_value = True

        mock_bazirag.return_value = True
        mock_bgem3.return_value = True
        mock_qdrant.return_value = True

        await run_preflight()

        mock_exit.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
