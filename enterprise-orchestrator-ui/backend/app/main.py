from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.jobs import router as jobs_router
from app.database import engine
from app.db_models import Base

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"


@asynccontextmanager
async def lifespan(application: FastAPI):
    # Create tables on startup (use Alembic migrations in production)
    Base.metadata.create_all(bind=engine)
    # Ensure reports directory exists
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="Enterprise Orchestrator UI API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(jobs_router)

# Serve generated HTML reports as static files
app.mount("/reports", StaticFiles(directory=str(REPORTS_DIR), html=True), name="reports")
