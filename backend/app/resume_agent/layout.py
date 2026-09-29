"""Shared resume layout tokens used by document export renderers."""
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict


@lru_cache(maxsize=1)
def get_resume_layout() -> Dict[str, Any]:
    path = Path(__file__).with_name("resume_layout.json")
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)
