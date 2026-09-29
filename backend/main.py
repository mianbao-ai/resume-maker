"""Resume Maker backend entry point.

This mirrors the website server layout: ``backend`` is the import root and
feature packages live directly under ``features``.
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from infrastructure.database.sql import close_db, init_db
from features.resume_agent.api import router as resume_agent_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="Resume Maker Agent API",
    description="Resume Maker using the website Resume Agent runtime",
    version="0.2.0",
    lifespan=lifespan,
)

origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(resume_agent_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
