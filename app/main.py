from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database import Base, engine, test_connection
from app.routers import auth, inventory, models, users, manufacturing, pdi
import app.models

@asynccontextmanager
async def lifespan(app: FastAPI):
    test_connection()
    Base.metadata.create_all(bind=engine)
    print("✓ All tables ready.")
    yield

app = FastAPI(
    title="G-Byke ERP",
    version="1.0.2",
    lifespan=lifespan
)

app.include_router(auth.router)
app.include_router(inventory.router)
app.include_router(models.router)
app.include_router(users.router)
app.include_router(manufacturing.router)
app.include_router(pdi.router)


@app.get("/")
def root():
    return {"status": "G-Byke ERP server is running", "version": "1.0.2"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/version")
def get_version():
    return {
        "version":        "1.0.2",
        "force_update":   False,
        "update_message": ""
    }