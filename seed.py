from app.database import SessionLocal, engine, Base
from app.models import User
import app.models
import bcrypt

def hash_pwd(password: str) -> str:
    return bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        existing = db.query(User).filter(User.username == "admin").first()
        if existing:
            print("✓ Super Admin already exists. Skipping.")
            return

        superadmin = User(
            full_name="G-Byke Owner",
            username="admin",
            hashed_password=hash_pwd("gbyke@admin123"),
            role="superadmin",
            is_active=True
        )
        db.add(superadmin)
        db.commit()
        print("✓ Super Admin created.")
        print("  Username : admin")
        print("  Password : gbyke@admin123")
        print("  Role     : superadmin")
        print("  ⚠  Change this password after first login.")

    except Exception as e:
        print(f"✗ Seed failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed()