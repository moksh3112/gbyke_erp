from app.database import SessionLocal, engine, Base
from app.core.security import hash_password
from app.models import User
import app.models

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Check if admin already exists
        existing = db.query(User).filter(User.username == "admin").first()
        if existing:
            print("✓ Admin account already exists. Skipping.")
            return

        admin = User(
            full_name="G-Byke Admin",
            username="admin",
            hashed_password=hash_password("gbyke@admin123"),
            role="admin",
            is_active=True
        )
        db.add(admin)
        db.commit()
        print("✓ Admin account created successfully.")
        print("  Username : admin")
        print("  Password : gbyke@admin123")
        print("  ⚠  Change this password after first login.")

    except Exception as e:
        print(f"✗ Seed failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed()