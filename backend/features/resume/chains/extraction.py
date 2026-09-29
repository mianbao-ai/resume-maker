"""Canonical, scene-independent Resume Facts extraction chains."""

from __future__ import annotations

import asyncio
import os
from typing import Any, Optional

import httpx
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI
from loguru import logger

from .normalization import normalize_extraction_output
from .prompts.info_ext import (
    ACHIEVEMENTS_SYSTEM_PROMPT,
    BASIC_EDUCATION_SYSTEM_PROMPT,
    PROJECT_SYSTEM_PROMPT,
    USER_PROMPT,
    WORK_SYSTEM_PROMPT,
)
from .schemas import ResumeFacts
from utils.deepseek_config import (
    DEFAULT_DEEPSEEK_MODEL,
    get_deepseek_base_url,
    get_deepseek_extra_body,
)
from utils.proxy_config import get_langchain_deepseek_config


def _build_langchain_config(langfuse_handler: Any | None) -> dict[str, Any] | None:
    return {"callbacks": [langfuse_handler]} if langfuse_handler is not None else None


def _build_chat_llm(
    model_name: str,
    temperature: float,
    api_key: Optional[str] = None,
) -> ChatOpenAI:
    resolved_api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
    if not resolved_api_key:
        raise ValueError("Resume extraction requires DEEPSEEK_API_KEY")
    base_url = get_deepseek_base_url()
    llm_kwargs = {
        "model": model_name,
        "temperature": temperature,
        "api_key": resolved_api_key,
        "base_url": base_url,
        "extra_body": get_deepseek_extra_body("disabled"),
    }
    if "deepseek.com" in base_url.lower():
        llm_kwargs["http_async_client"] = httpx.AsyncClient(timeout=60.0)
    else:
        llm_kwargs.update(get_langchain_deepseek_config())
    return ChatOpenAI(**llm_kwargs)


def _create_section_chain(
    system_prompt: str,
    *,
    model_name: str = DEFAULT_DEEPSEEK_MODEL,
    temperature: float = 0.0,
    api_key: Optional[str] = None,
):
    llm = _build_chat_llm(
        model_name=model_name,
        temperature=temperature,
        api_key=api_key,
    )
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=system_prompt),
        ("human", USER_PROMPT),
    ])
    return (
        {"resume_text": RunnablePassthrough()}
        | prompt
        | llm.with_structured_output(method="json_mode")
    )


def create_basic_education_chain(**kwargs):
    return _create_section_chain(BASIC_EDUCATION_SYSTEM_PROMPT, **kwargs)


def create_work_chain(**kwargs):
    return _create_section_chain(WORK_SYSTEM_PROMPT, **kwargs)


def create_project_chain(**kwargs):
    return _create_section_chain(PROJECT_SYSTEM_PROMPT, **kwargs)


def create_achievements_chain(**kwargs):
    return _create_section_chain(ACHIEVEMENTS_SYSTEM_PROMPT, **kwargs)


async def extract_resume_facts(
    resume_text: str,
    *,
    resume_id: str,
    model_name: str = DEFAULT_DEEPSEEK_MODEL,
    temperature: float = 0.0,
    api_key: Optional[str] = None,
    langfuse_handler: Any | None = None,
    source_page_count: int | None = None,
) -> ResumeFacts:
    """Extract four fact sections in parallel and normalize partial successes."""
    logger.info("🚀 开始 Resume Facts 提取（四个分项 Chain）")
    kwargs = {
        "model_name": model_name,
        "temperature": temperature,
        "api_key": api_key,
    }
    chains = {
        "basic_education": create_basic_education_chain(**kwargs),
        "work": create_work_chain(**kwargs),
        "project": create_project_chain(**kwargs),
        "achievements": create_achievements_chain(**kwargs),
    }
    config = _build_langchain_config(langfuse_handler)
    results = await asyncio.gather(
        *(chain.ainvoke(resume_text, config=config) for chain in chains.values()),
        return_exceptions=True,
    )

    raw_output: dict[str, Any] = {"section_errors": {}}
    successful_sections = 0
    for section_name, result in zip(chains, results):
        if isinstance(result, Exception):
            logger.warning(f"⚠️ 简历 {section_name} 提取失败，保留其他分项结果: {result}")
            raw_output["section_errors"][section_name] = str(result)
        elif isinstance(result, dict):
            raw_output[section_name] = result
            successful_sections += 1
        else:
            message = f"unexpected result type: {type(result).__name__}"
            logger.warning(f"⚠️ 简历 {section_name} {message}")
            raw_output["section_errors"][section_name] = message

    if successful_sections == 0:
        section_errors = raw_output["section_errors"]
        raise RuntimeError(f"all Resume Facts extraction sections failed: {section_errors}")

    facts = normalize_extraction_output(
        raw_output,
        resume_id=resume_id,
        source_page_count=source_page_count,
    )
    logger.info(
        "✅ 简历事实提取完成: education={}, work={}, project={}, warnings={}, quality={:.3f}",
        len(facts.education),
        len(facts.work_experience),
        len(facts.project_experience),
        len(facts.extraction_metadata.warnings),
        facts.extraction_metadata.quality_score or 0.0,
    )
    return facts
