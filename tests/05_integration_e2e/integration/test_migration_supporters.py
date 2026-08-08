
from pathlib import Path

from src.bot.db import Database


def migrate_supporters():
    # Initializing Database will trigger the migrations (_run_migrations)
    db = Database("bot.db")
    prd_dir = Path("_prd")

    if not prd_dir.exists():
        print(f"Error: {prd_dir} does not exist.")
        return

    # Get all numeric directories in _prd
    supporter_ids = []
    for item in prd_dir.iterdir():
        if item.is_dir() and item.name.isdigit():
            supporter_ids.append(int(item.name))

    print(f"Found {len(supporter_ids)} potential supporters: {supporter_ids}")

    for user_id in supporter_ids:
        print(f"Granting FREE4now access to user {user_id}...")
        db.set_monthly_code(user_id, True)

    db.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate_supporters()
