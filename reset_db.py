from app.database import engine
from app.models import Base
from sqlalchemy import text

print("Dropping all existing database tables (including ghost tables)...")

with engine.connect() as conn:
    # This directly tells PostgreSQL to nuke the schema and everything inside it cleanly
    conn.execute(text("DROP SCHEMA public CASCADE;"))
    conn.execute(text("CREATE SCHEMA public;"))
    conn.commit()

print("Recreating database tables with the new architecture...")
Base.metadata.create_all(bind=engine)

print("✅ Database reset successfully! You can now start your FastAPI server.")