import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware

from .database import connection, init_db, row_to_dict
from .schemas import Resume, ResumeCreate, ResumeSummary, ResumeUpdate


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Resume Maker API",
    description="Local-first resume builder API",
    version="0.1.0",
    lifespan=lifespan,
)

origins = os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/resumes", response_model=list[ResumeSummary])
def list_resumes() -> list[dict]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT id, title, template, accent_color, updated_at "
            "FROM resumes ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/resumes", response_model=Resume, status_code=status.HTTP_201_CREATED)
def create_resume(payload: ResumeCreate) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    resume_id = str(uuid4())
    with connection() as conn:
        conn.execute(
            "INSERT INTO resumes VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                resume_id,
                payload.title,
                payload.template,
                payload.accent_color,
                payload.content.model_dump_json(),
                now,
                now,
            ),
        )
        row = conn.execute("SELECT * FROM resumes WHERE id = ?", (resume_id,)).fetchone()
    return row_to_dict(row)


@app.get("/api/resumes/{resume_id}", response_model=Resume)
def get_resume(resume_id: str) -> dict:
    with connection() as conn:
        row = conn.execute("SELECT * FROM resumes WHERE id = ?", (resume_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    return row_to_dict(row)


@app.put("/api/resumes/{resume_id}", response_model=Resume)
def update_resume(resume_id: str, payload: ResumeUpdate) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with connection() as conn:
        result = conn.execute(
            """UPDATE resumes
               SET title = ?, template = ?, accent_color = ?, content = ?, updated_at = ?
               WHERE id = ?""",
            (
                payload.title,
                payload.template,
                payload.accent_color,
                payload.content.model_dump_json(),
                now,
                resume_id,
            ),
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Resume not found")
        row = conn.execute("SELECT * FROM resumes WHERE id = ?", (resume_id,)).fetchone()
    return row_to_dict(row)


@app.delete("/api/resumes/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(resume_id: str) -> Response:
    with connection() as conn:
        result = conn.execute("DELETE FROM resumes WHERE id = ?", (resume_id,))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Resume not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
