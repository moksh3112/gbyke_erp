import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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
        admin = db.query(User).filter(
            User.role == "superadmin"
        ).first()

        if admin:
            admin.username         = username
            admin.hashed_password  = hash_password(password)
            admin.full_name        = full_name
            db.commit()
            print(f"✓ Admin updated — username: {username}")
        else:
            print("✗ No superadmin found in database.")
    finally:
        db.close()


def create_test_accounts():
    db = SessionLocal()
    try:
        # Manager
        manager = db.query(User).filter(
            User.username == "manager1"
        ).first()
        if not manager:
            manager = User(
                username        = "manager1",
                hashed_password = hash_password("manager123"),
                full_name       = "Test Manager",
                role            = "manager",
                is_active       = True
            )
            db.add(manager)
            print("✓ manager1 created")
        else:
            print("✓ manager1 already exists")

        # Staff
        staff = db.query(User).filter(
            User.username == "staff1"
        ).first()
        if not staff:
            staff = User(
                username        = "staff1",
                hashed_password = hash_password("staff123"),
                full_name       = "Test Staff",
                role            = "staff",
                is_active       = True
            )
            db.add(staff)
            print("✓ staff1 created")
        else:
            print("✓ staff1 already exists")

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    # ── CHANGE YOUR ADMIN CREDENTIALS HERE ────────────────────
    ADMIN_USERNAME  = "Sahil"
    ADMIN_PASSWORD  = "Moksh@233234"
    ADMIN_FULL_NAME = "G-Byke Owner"
    # ──────────────────────────────────────────────────────────

    update_admin(ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_FULL_NAME)
    create_test_accounts()
    print("\nDone. You can now login with:")
    print(f"  Username : {ADMIN_USERNAME}")
    print(f"  Password : {ADMIN_PASSWORD}")