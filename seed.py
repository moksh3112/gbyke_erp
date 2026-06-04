# seed.py
# FIX 7: Password is now read from .env — never hardcoded in source code.
#
# SETUP: create a .env file in the project root with:
#   ADMIN_USERNAME=Sahil
#   ADMIN_PASSWORD=your_secure_password_here
#   ADMIN_FULL_NAME=G-Byke Owner

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.database import SessionLocal
from app.models import User
import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode(), bcrypt.gensalt(12)
    ).decode()


def update_admin(username: str, password: str, full_name: str):
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == "superadmin").first()
        if admin:
            admin.username        = username
            admin.hashed_password = hash_password(password)
            admin.full_name       = full_name
            db.commit()
            print(f"✓ Admin updated — username: {username}")
        else:
            print("✗ No superadmin found. Run reset_db.py first.")
    finally:
        db.close()


def create_test_accounts():
    db = SessionLocal()
    try:
        for uname, pwd, name, role in [
            ("manager1", "manager123", "Test Manager", "manager"),
            ("staff1",   "staff123",   "Test Staff",   "staff"),
        ]:
            if not db.query(User).filter(User.username == uname).first():
                db.add(User(
                    username        = uname,
                    hashed_password = hash_password(pwd),
                    full_name       = name,
                    role            = role,
                    is_active       = True
                ))
                print(f"✓ {uname} created")
            else:
                print(f"✓ {uname} already exists")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    # Read from environment — set these in .env, never hardcode here
    ADMIN_USERNAME  = os.getenv("ADMIN_USERNAME")
    ADMIN_PASSWORD  = os.getenv("ADMIN_PASSWORD")
    ADMIN_FULL_NAME = os.getenv("ADMIN_FULL_NAME", "G-Byke Owner")

    if not ADMIN_USERNAME or not ADMIN_PASSWORD:
        print("❌  ADMIN_USERNAME and ADMIN_PASSWORD must be set in your .env file.")
        sys.exit(1)

    update_admin(ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_FULL_NAME)
    create_test_accounts()
    print(f"\nDone. Login with username: {ADMIN_USERNAME}")