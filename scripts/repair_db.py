"""
One-off DB repair script to add missing columns for existing SQLite DB.
Usage: python scripts/repair_db.py
"""
from pathlib import Path
import sys


def main():
    # import app modules
    current = Path(__file__).resolve().parent
    root = current.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from sqlalchemy import text
    from app.db import engine

    with engine.begin() as conn:
        # species_reports taxonomy columns
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(species_reports)"))}
        for name, typ in [
            ("phylum", "TEXT"),
            ("class_name", "TEXT"),
            ("order_name", "TEXT"),
            ("family", "TEXT"),
            ("genus", "TEXT"),
        ]:
            if name not in cols:
                conn.execute(text(f"ALTER TABLE species_reports ADD COLUMN {name} {typ}"))

        # users profile columns
        ucols = {row[1] for row in conn.execute(text("PRAGMA table_info(users)"))}
        for name, typ in [
            ("avatar_url", "TEXT"),
            ("gender", "TEXT"),
            ("bio", "TEXT"),
            ("city", "TEXT"),
            ("theme", "TEXT"),
            ("favorites", "TEXT"),
            ("public_profile", "INTEGER DEFAULT 0"),
            ("last_active_at", "DATETIME"),
        ]:
            if name not in ucols:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {typ}"))

    print("DB schema repair completed.")


if __name__ == "__main__":
    main()

