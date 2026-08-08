# ruff: noqa: E402
import sys
from pathlib import Path

# Add project root to path so we can import the original controls
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import the original models and providers to maintain exact compatibility
from admin.controls.controls import (
    PROVIDERS,  # noqa: F401
    SystemSettings,
    gemma_4_31b_it,
)


# Instantiate settings and override for UAT testing
class TestSystemSettings(SystemSettings):
    telegram_api_base: str = "http://127.0.0.1:9999"
    app_port: int = 8443  # UAT test port (production uses 8445)


settings = TestSystemSettings(app_port=8443)


# Map all keys in CONTROL_SHEET to the cheap test model (gemma_4_31b_it)
class TestControlSheet(dict):
    def __getitem__(self, key):
        return gemma_4_31b_it

    def get(self, key, default=None):
        return gemma_4_31b_it


CONTROL_SHEET = TestControlSheet()
