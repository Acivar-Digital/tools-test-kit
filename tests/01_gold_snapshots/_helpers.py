import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


def get_last_bot_reply(chat_id: int, platform: str = "test_telegram01") -> str | None:
    """
    Queries the chat_logs table to retrieve the last message sent by the bot
    to the specified user on the specified platform.
    """
    record = get_last_bot_reply_record(chat_id, platform)
    return record["message_text"] if record else None


def get_last_bot_reply_record(chat_id: int, platform: str = "test_telegram01") -> dict | None:
    """
    Queries the chat_logs table to retrieve the last message record sent by the bot
    to the specified user on the specified platform.
    """
    load_dotenv()
    db_url = os.getenv("DATABASE_URL", "sqlite:///bot.db")
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    engine = create_engine(db_url)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT cl.id, cl.message_text, cl.created_at
                FROM chat_logs cl
                JOIN platform_accounts pa ON cl.user_id = pa.user_id
                WHERE pa.platform = :platform AND pa.platform_user_id = :puid AND cl.role = 'bot'
                ORDER BY cl.created_at DESC
                LIMIT 1
                """
            ),
            {"platform": platform, "puid": str(chat_id)},
        ).fetchone()

        if row:
            return {"id": row[0], "message_text": row[1], "created_at": row[2]}
    return None
