"""
Reset or create a user with a new password, and optionally grant admin.

Usage:
  python scripts/reset_user.py email@example.com newpassword [--admin]
"""
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    email = sys.argv[1].strip().lower()
    password = sys.argv[2]
    make_admin = len(sys.argv) >= 4 and sys.argv[3] == "--admin"

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from app.db import SessionLocal, engine
    from app.models import Base, User
    from app.security import hash_password

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == email).one_or_none()
        if u is None:
            u = User(email=email, display_name=email.split("@")[0], password_hash=hash_password(password), is_admin=make_admin)
            db.add(u)
            db.commit()
            print(f"Created user {email}. Admin={make_admin}")
        else:
            u.password_hash = hash_password(password)
            if make_admin:
                u.is_admin = True
            db.add(u)
            db.commit()
            print(f"Updated password for {email}. Admin={u.is_admin}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

