# fix_admin.py
# FIX 7: Password now comes from .env — not hardcoded.
#
# Add to your .env:
#   ADMIN_PASSWORD=your_secure_password_here

import os
from dotenv import load_dotenv
load_dotenv()

from app.database import SessionLocal
from app.models import User, UserRole
from app.core.security import hash_password

db = SessionLocal()

new_password = os.getenv("ADMIN_PASSWORD")
if not new_password:
    print("❌  ADMIN_PASSWORD not set in .env — aborting.")
    db.close()
    exit(1)

admin = db.query(User).filter(User.username == "Sahil").first()

if not admin:
    print("Creating new Superadmin account...")
    admin = User(
        username  = "Sahil",
        full_name = "G-Byke Owner",
        role      = UserRole.superadmin,
        is_active = True
    )
    db.add(admin)
else:
    print("Superadmin found, updating password...")

admin.hashed_password = hash_password(new_password)
db.commit()
print("✅  Superadmin ready.")
db.close()