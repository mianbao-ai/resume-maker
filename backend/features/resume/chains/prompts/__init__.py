"""
Resume Extraction Prompts

与场景无关的 Resume Facts 提取提示词：
基本/教育、Work、Project 和成果。

Author: nicheng
Date: 2025-03-22
"""

from .info_ext import (
    ACHIEVEMENTS_SYSTEM_PROMPT,
    BASIC_EDUCATION_SYSTEM_PROMPT,
    PROJECT_SYSTEM_PROMPT,
    WORK_SYSTEM_PROMPT,
)

__all__ = [
    "ACHIEVEMENTS_SYSTEM_PROMPT",
    "BASIC_EDUCATION_SYSTEM_PROMPT",
    "PROJECT_SYSTEM_PROMPT",
    "WORK_SYSTEM_PROMPT",
]
