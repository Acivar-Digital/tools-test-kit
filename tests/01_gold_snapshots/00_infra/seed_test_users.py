import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src2.core.database.models import PlatformAccount, User


def seed_users():
    load_dotenv()
    db_url = os.getenv("DATABASE_URL", "sqlite:///bot.db")
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    engine = create_engine(db_url)
    make_session = sessionmaker(bind=engine)
    session = make_session()

    try:
        existing = (
            session.query(PlatformAccount)
            .filter_by(
                platform="test_telegram01",
                platform_user_id="999123489",
            )
            .first()
        )

        if existing:
            print("User 999123489 already seeded on test_telegram01.")
            return

        new_user = User(tier="PAID", region="SG")
        session.add(new_user)
        session.flush()

        new_account = PlatformAccount(
            user_id=new_user.id,
            platform="test_telegram01",
            platform_user_id="999123489",
            is_primary=True,
        )
        session.add(new_account)
        session.commit()
        print("Successfully seeded user 999123489 as PAID on test_telegram01.")
    except Exception as e:
        session.rollback()
        print(f"Error seeding users: {e}")
    finally:
        session.close()


if __name__ == "__main__":
    seed_users()
