"""Atomic cache helpers for the canonical Resume Facts document."""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

from .chains.schemas import ResumeFacts


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with open(temporary, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def load_resume_facts(path: Path) -> ResumeFacts:
    with open(path, encoding="utf-8") as file:
        return ResumeFacts.model_validate(json.load(file))
