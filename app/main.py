from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database import Base, engine, test_connection
from app.routers import auth
import app.models
@asynccontextmanager
async def lifespan(app: FastAPI):
    test_connection()
    Base.metadata.create_all(bind=engine)
    print("✓ All tables ready.")
    yield

app = FastAPI(
    title="G-Byke ERP",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(auth.router)

@app.get("/")
def root():
    return {"status": "G-Byke ERP server is running", "version": "1.0.0"}

@app.get("/health")
def health():
    return {"status": "ok"}