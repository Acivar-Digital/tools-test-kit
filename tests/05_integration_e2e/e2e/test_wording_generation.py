import asyncio
import os
import sys

# Add src to path
sys.path.append(os.getcwd())

# Mock environment variables for handlers
os.environ["CHRONO_MODEL"] = "google/gemini-2.0-flash-001"
os.environ["CHRONO_BASE_URL"] = "https://openrouter.ai/api/v1"
os.environ["CHRONO_API_KEY"] = "mock_key"
os.environ["OPENROUTER_API_KEY"] = "mock_key"
os.environ["K3_DISPATCH_INTERVAL"] = "0"  # No delay for tests
import src.engine.openrouter

os.environ.pop("QDRANT_URL", None)
os.environ.pop("BGEM3_URL", None)
from src.bot import chronomancer_handler


async def mock_call(*args, **kwargs):
    return "This is a mock strategic overview. Things look stable for your chart."


# Inject into both locations to be safe
src.engine.openrouter.call_openrouter_async = mock_call
chronomancer_handler.call_openrouter_async = mock_call

from src.bot.chronomancer_handler import (  # noqa: E402
    handle_daily,
    handle_forecast,
    handle_forecast_category,
    handle_forecast_menu,
)
from src.bot.db import Database  # noqa: E402
from src.bot.session import Session, UserProfile, save_session  # noqa: E402


async def generate_examples():
    db = Database("bot.db")
    chat_id = 999999  # Mock ID

    # Setup mock profile
    p = UserProfile(
        alias="TESTER",
        gender="M",
        year_pillar={"stem": "Jia", "branch": "Zi"},
        month_pillar={"stem": "Yi", "branch": "Chou"},
        day_pillar={"stem": "Bing", "branch": "Yin"},
        hour_pillar={"stem": "Ding", "branch": "Mao"},
        day_master_strength="Strong",
        favorable_elements=["Water", "Metal"],
        unfavorable_elements=["Fire", "Wood"],
        structure="General",
    )

    # Force profile into DB for handlers
    db.upsert_user(chat_id, "admin")
    db.set_monthly_code(chat_id, True)
    db.set_feature_code(chat_id, True)

    from src.bot.session import delete_session

    db.delete_chrono_cache_for_user(chat_id)
    delete_session(chat_id)
    session = Session(chat_id=chat_id, profile=p)
    save_session(session)

    results = {}

    print("Generating /daily...")
    results["/daily"] = await handle_daily(chat_id)

    print("Generating /best...")
    results["/best"] = await handle_forecast_category(chat_id, "best")

    print("Generating /career...")
    results["/career"] = await handle_forecast_category(chat_id, "career")

    print("Generating /love...")
    results["/love"] = await handle_forecast_category(chat_id, "love")

    print("Generating /wealth...")
    results["/wealth"] = await handle_forecast_category(chat_id, "wealth")

    print("Generating /forecast (Menu)...")
    results["/forecast"] = handle_forecast_menu()

    print("Generating /30 (List View)...")
    results["/30"] = await handle_forecast(chat_id, 30)

    print("Generating /travel...")
    results["/travel"] = await handle_forecast_category(chat_id, "travel")

    print("Generating /health...")
    results["/health"] = await handle_forecast_category(chat_id, "health")

    # Save to markdown
    output_path = "TEST/reports/function_wordings_v5.md"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Function Wordings Verification Report\n\n")
        f.write("This report shows the exact output for each primary Chronomancer function.\n\n")

        for cmd, wording in results.items():
            f.write(f"## {cmd}\n")
            f.write("```markdown\n")
            f.write("⏳ _Chronomancer is thinking..._\n\n")  # Simulated thinking msg from app.py
            f.write(wording)
            f.write("\n```\n\n")

    print(f"Report saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(generate_examples())
