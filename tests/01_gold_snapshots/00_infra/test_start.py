# ruff: noqa: E402
import importlib
import os
import subprocess
import sys
import types
from pathlib import Path

# 1. Resolve project root and put it at the front of sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 2. Load the mock test_control module dynamically since 00_infra is not a valid Python identifier
# [baziforecaster-only: TEST/GOLD/00_infra/test_control.py not in kit download]
test_control = importlib.import_module("TEST.GOLD.00_infra.test_control")

# 3. Inject mock into sys.modules to intercept imports of admin.controls.controls
controls_mock = types.ModuleType("admin.controls.controls")
controls_mock.settings = test_control.settings
controls_mock.CONTROL_SHEET = test_control.CONTROL_SHEET
controls_mock.PROVIDERS = test_control.PROVIDERS
sys.modules["admin.controls.controls"] = controls_mock

# 4. Lock down APP_PORT environment queries to UAT port to prevent collisions with production .env
target_port = str(getattr(test_control.settings, "app_port", 8445))

# Patch os.environ and os.getenv to force APP_PORT to UAT default
original_getenv = os.getenv


def mock_getenv(key, default=None):
    if key == "APP_PORT":
        return target_port
    return original_getenv(key, default)


os.getenv = mock_getenv

os.environ["APP_PORT"] = target_port

# Intercept load_dotenv to prevent overriding APP_PORT
try:
    import dotenv
    original_load_dotenv = dotenv.load_dotenv

    def mock_load_dotenv(*args, **kwargs):
        res = original_load_dotenv(*args, **kwargs)
        os.environ["APP_PORT"] = target_port
        return res

    dotenv.load_dotenv = mock_load_dotenv
except ImportError:
    pass


def kill_stale_processes(port: int):
    """Aggressively find and kill any process listening on the target port."""
    if os.name == "nt":
        return  # Skip on Windows if running in simple linux bash

    try:
        output = subprocess.check_output(
            ["lsof", "-ti", f"tcp:{port}"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if output:
            print(f"[UAT] Found stale processes on port {port}. Terminating PIDs: {output.splitlines()}")
            for pid in output.splitlines():
                subprocess.run(["kill", "-9", pid], capture_output=True)
    except Exception:
        pass


# 5. Now delegate execution directly to the original start2.py entry point
if __name__ == "__main__":
    kill_stale_processes(int(target_port))

    # Run the original start2.py main entry point under this mocked environment
    import start2

    # Forward command-line arguments to run_bot
    reset_flag = "--reset" in sys.argv
    skip_preflight_flag = "--skip-preflight" in sys.argv
    start2.run_bot(reset=reset_flag, skip_preflight=skip_preflight_flag)
