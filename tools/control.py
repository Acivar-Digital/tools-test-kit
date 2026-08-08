import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

TARGET_ROOT = os.getenv("KIT_TARGET_ROOT")
if not TARGET_ROOT:
    raise RuntimeError("KIT_TARGET_ROOT is required — set it in kit-tools/.env to your target repository path.")
REPO_ROOT = Path(TARGET_ROOT).resolve()

INFRA_ROOT = os.getenv("KIT_INFRA_ROOT")

_source_root = os.getenv("KIT_SOURCE_ROOT", "src")


def _Model(name):
    return type("M", (), {"model_name": name})


class ControlSheet:
    codebase_model = _Model(os.getenv("KIT_CODEBASE_MODEL", ""))
    web_model = _Model(os.getenv("KIT_WEB_MODEL", ""))


class SystemSettings:
    exa_api_key = os.getenv("EXA_API_KEY", "")
    tavily_api_key = os.getenv("TAVILY_API_KEY", "")
    searxng_url = os.getenv("SEARXNG_URL", "https://searxng.com")


class Settings:
    report_channel_id = os.getenv("KIT_REPORT_CHANNEL_ID")
    dev_chat_id = os.getenv("KIT_DEV_CHAT_ID")
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_api_base = os.getenv("TELEGRAM_API_BASE", "https://api.telegram.org")


if __name__ == "__main__":
    print(f"REPO_ROOT={REPO_ROOT}")
    print(f"ControlSheet.codebase_model.model_name={ControlSheet.codebase_model.model_name}")
    print(f"SystemSettings.exa_api_key={SystemSettings.exa_api_key!r}")
