from app.database import SessionLocal
from app.models import User, UserRole

# Safely grab whatever password hashing function you are using
try:
    from app.core.security import get_password_hash as hash_pwd
except ImportError:
    try:
        from app.core.security import hash_password as hash_pwd
    except ImportError:
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        def hash_pwd(password: str):
            return pwd_context.hash(password)

db = SessionLocal()

# 1. Look for the Sahil user
admin = db.query(User).filter(User.username == "Sahil").first()

# 2. If it doesn't exist, create it from scratch
if not admin:
    print("Creating new Superadmin account...")
    admin = User(
        username="Sahil",
        full_name="G-Byke Owner",
        role=UserRole.superadmin,
        is_active=True
    )
    db.add(admin)
else:
    print("Superadmin found, updating password...")

# 3. Force update the password and save
admin.hashed_password = hash_pwd("Moksh@233234")
db.commit()

print("✅ Superadmin 'Sahil' successfully created and ready for login!")
db.close()