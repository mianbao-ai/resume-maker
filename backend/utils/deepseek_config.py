"""Shared DeepSeek API defaults for the current public API."""

from __future__ import annotations

import os


DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_THINKING_TYPE = "disabled"
ALLOWED_DEEPSEEK_THINKING_TYPES = {"enabled", "disabled"}


def get_deepseek_base_url() -> str:
    return os.getenv("DEEPSEEK_BASE_URL") or DEFAULT_DEEPSEEK_BASE_URL


def get_deepseek_model(env_var: str = "DEEPSEEK_MODEL") -> str:
    return os.getenv(env_var) or DEFAULT_DEEPSEEK_MODEL


def normalize_deepseek_thinking_type(value: str | None = None) -> str:
    thinking_type = (value or os.getenv("DEEPSEEK_THINKING_TYPE") or DEFAULT_DEEPSEEK_THINKING_TYPE)
    thinking_type = thinking_type.strip().lower()
    if thinking_type not in ALLOWED_DEEPSEEK_THINKING_TYPES:
        return DEFAULT_DEEPSEEK_THINKING_TYPE
    return thinking_type


def get_deepseek_extra_body(thinking_type: str | None = None) -> dict:
    return {"thinking": {"type": normalize_deepseek_thinking_type(thinking_type)}}
