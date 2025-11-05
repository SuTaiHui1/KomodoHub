from pathlib import Path
from datetime import datetime, timedelta
import os
import sys

# Ensure project root on sys.path when running as a script
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db import SessionLocal, engine
from app.models import Base, User, SpeciesReport, ReportStatus
from app.security import hash_password


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Users
        if not db.query(User).count():
            admin = User(email="admin@example.com", display_name="Admin", password_hash=hash_password("admin123"), is_admin=True)
            u1 = User(email="alice@example.com", display_name="Alice", password_hash=hash_password("password"))
            u2 = User(email="bob@example.com", display_name="Bob", password_hash=hash_password("password"))
            u3 = User(email="charlie@example.com", display_name="Charlie", password_hash=hash_password("password"))
            db.add_all([admin, u1, u2, u3])
            db.commit()
        users = db.query(User).all()
        users_by_email = {u.email: u for u in users}

        if not db.query(SpeciesReport).count():
            samples = [
                ("Forest lizard observed", "Varanus salvator", "Seen by the river."),
                ("Bird near campus", "Cuculus canorus", "Perched on a tree."),
                ("Unknown beetle", "Coleoptera sp.", "Small and shiny."),
                ("Frog after rain", "Hyla chinensis", "Loud croaks at night."),
                ("Butterfly in garden", "Papilio machaon", "Yellow-black pattern."),
            ]
            now = datetime.utcnow()
            for i, (title, species, desc) in enumerate(samples):
                user = users[i % len(users)]
                rep = SpeciesReport(
                    reporter_id=user.id,
                    title=title,
                    species_name=species,
                    description=desc,
                    status=ReportStatus.approved.value if i % 2 == 0 else ReportStatus.pending.value,
                    created_at=now - timedelta(days=5 - i),
                )
                db.add(rep)
            db.commit()
        print("Seed complete. Admin login: admin@example.com / admin123")
    finally:
        db.close()


if __name__ == "__main__":
    main()
