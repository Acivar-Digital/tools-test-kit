import asyncio
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def print_status(component: str, status: bool, detail: str = ""):
    icon = f"{GREEN}[ OK ]{RESET}" if status else f"{RED}[FAIL]{RESET}"
    msg = f"{icon} {component:<35}"
    if detail:
        msg += f" - {detail}"
    print(msg)


async def check_env_configs() -> bool:
    api_base = os.getenv("TELEGRAM_API_BASE", "")
    expected = "http://127.0.0.1:9999"
    ok = True

    if api_base.rstrip("/") == expected:
        print_status("1. .env TELEGRAM_API_BASE", True, f"Pointing to mock server: {api_base}")
    else:
        print_status("1. .env TELEGRAM_API_BASE", False, f"Expected '{expected}', found '{api_base}'")
        ok = False

    ier_model = os.getenv("IER_MODEL", "")
    if ier_model:
        print_status("1. .env IER_MODEL", True, f"Configured: {ier_model}")
    else:
        print_status("1. .env IER_MODEL", False, "Missing! Please set IER_MODEL in .env.")
        ok = False

    ier_url = os.getenv("IER_URL", "")
    if ier_url:
        print_status("1. .env IER_URL", True, "Configured")
    else:
        print_status("1. .env IER_URL", False, "Missing! Please set IER_URL in .env.")
        ok = False

    return ok


async def check_mock_telegram_server() -> bool:
    url = "http://127.0.0.1:9999/intercepted"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url)
            if resp.status_code in (200, 404):
                print_status("2. Mock Telegram Server (Port 9999)", True, "Online & responsive")
                return True
    except Exception as e:
         print_status(
            "2. Mock Telegram Server (Port 9999)",
            False,
            f"Offline. Run 'uv run python 01_gold_snapshots/00_infra/fake_telegram.py' in the background. Error: {e}",
        )
    return False


async def check_model_gateway_ready() -> bool:
    from pydantic_ai import Agent

    from admin.controls.controls import CONTROL_SHEET

    print_status("3. Test Model Gateway Readiness", True, "Auditing all Control Sheet roles...")

    all_ready = True
    for role, model in CONTROL_SHEET:
        try:
            agent = Agent(model, instructions="Respond with exactly the word 'PONG'.")
            res = await agent.run("PING")
            response_text = str(res.output).strip()
            print_status(f"   - Role '{role}' ({model.model_name})", True, f"Response: '{response_text}'")
        except Exception as e:
            print_status(f"   - Role '{role}' ({model.model_name})", False, f"Error: {e}")
            all_ready = False

    return all_ready


async def check_qdrant_ready() -> bool:
    qdrant_url = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{qdrant_url.rstrip('/')}/collections")
            if resp.status_code == 200:
                print_status("4. Qdrant Local Database", True, "Online & responsive")
                return True
    except Exception as e:
        print_status("4. Qdrant Local Database", False, f"Offline on {qdrant_url}: {e}")
    return False


async def check_valkey_ready() -> bool:
    valkey_host = os.getenv("VALKEY_HOST", "127.0.0.1")
    valkey_port = int(os.getenv("VALKEY_PORT", "6379"))
    import redis.asyncio as redis

    try:
        r = redis.Redis(host=valkey_host, port=valkey_port, socket_timeout=3.0)
        pong = await r.ping()
        if pong:
            print_status("5. Valkey Server Connection", True, f"Online & responsive at {valkey_host}:{valkey_port}")
            return True
    except Exception as e:
        print_status("5. Valkey Server Connection", False, f"Offline at {valkey_host}:{valkey_port}. Error: {e}")
    return False


async def check_celery_worker_ready() -> bool:
    try:
        from src2.worker.celery_app import app

        valkey_host = os.getenv("VALKEY_HOST", "127.0.0.1")
        valkey_port = os.getenv("VALKEY_PORT", "6379")
        expected_broker = f"{valkey_host}:{valkey_port}"
        if expected_broker not in app.conf.broker_url:
            print_status(
                "6. Celery Workers Active",
                False,
                f"Mismatched broker! Celery app configured to {app.conf.broker_url}, but .env expects {expected_broker}",
            )
            return False

        loop = asyncio.get_running_loop()

        def _ping_workers():
            try:
                pings = app.control.ping(timeout=2.0)
                return pings
            except Exception:
                return []

        pings = await loop.run_in_executor(None, _ping_workers)
        if pings:
            workers = [list(d.keys())[0] for d in pings]
            print_status("6. Celery Workers Active", True, f"Online: {', '.join(workers)}")
            return True
        else:
            print_status(
                "6. Celery Workers Active",
                False,
                "No active workers detected. Start worker using 'celery -A src2.worker.celery_app worker --loglevel=info'",
            )
    except Exception as e:
        print_status("6. Celery Workers Active", False, f"Configuration or connection failed. Error: {e}")
    return False


async def run_uat_preflight():
    print("=== Running BaziForecaster UAT E2E Preflight Checks ===\n")
    results = await asyncio.gather(
        check_env_configs(),
        check_mock_telegram_server(),
        check_model_gateway_ready(),
        check_qdrant_ready(),
        check_valkey_ready(),
        check_celery_worker_ready(),
    )
    print("\n" + "=" * 55)
    if all(results):
        print(f"\n{GREEN}[ SUCCESS ]{RESET} All UAT E2E requirements are met. You can now safely run the E2E tests!")
        sys.exit(0)
    else:
        print(f"\n{RED}[ FAILURE ]{RESET} One or more preflight checks failed. Please fix the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_uat_preflight())
