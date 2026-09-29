"""
Proxy Configuration Utility for SSH Tunnel (SOCKS5)

This module provides proxy configuration specifically for DeepSeek and Daily.co API calls
when using SSH tunnel from China to overseas servers.

使用场景：
1. 在国外服务器上启用 SSH 服务（确保端口22开放）
2. 从国内服务器创建 SSH 动态隧道：ssh -D 1080 user@foreign-ip
3. 设置环境变量：PROXY_URL=socks5://127.0.0.1:1080
4. DeepSeek 和 Daily.co API 将自动通过隧道转发

依赖安装：
    uv add 'httpx[socks]'

Author: Cheng & Claude AI
Created: 2025-02-05
"""

import os
from typing import Optional
from loguru import logger


def get_proxy_url() -> Optional[str]:
    """
    获取代理 URL（从环境变量）

    优先级：PROXY_URL > HTTPS_PROXY > HTTP_PROXY

    Returns:
        代理 URL 字符串（如 socks5://127.0.0.1:1080），未配置则返回 None
    """
    proxy_url = os.getenv("PROXY_URL")
    if proxy_url:
        return proxy_url

    https_proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    if https_proxy:
        return https_proxy

    http_proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
    if http_proxy:
        return http_proxy

    return None


def get_deepseek_http_client():
    """
    创建配置了代理的 httpx.AsyncClient（用于 DeepSeek 兼容 SDK）

    DeepSeek 当前通过 OpenAI 兼容 SDK 接入，因此支持传入自定义 httpx 客户端来配置代理。
    这样可以让 DeepSeek API 请求通过 SSH 隧道转发。

    Returns:
        httpx.AsyncClient 实例（已配置代理）

    Usage:
        >>> from openai import AsyncOpenAI
        >>> from utils.proxy_config import get_deepseek_http_client
        >>>
        >>> http_client = get_deepseek_http_client()
        >>> client = AsyncOpenAI(api_key="...", http_client=http_client)

    注意事项：
        - SOCKS5 代理需要安装：uv add 'httpx[socks]'
        - 如果未安装 SOCKS 支持，会抛出 ImportError
    """
    import httpx

    proxy_url = get_proxy_url()

    if not proxy_url:
        # 未配置代理，返回默认客户端
        return httpx.AsyncClient(timeout=60.0)

    # 检查是否是 SOCKS 代理
    if proxy_url.startswith("socks5://") or proxy_url.startswith("socks4://"):
        try:
            import socksio  # noqa: F401
            logger.debug(f"✅ 使用 SOCKS 代理: {proxy_url}")
        except ImportError:
            logger.error(
                "❌ SOCKS 代理需要安装额外依赖。请运行: uv add 'httpx[socks]'"
            )
            raise ImportError(
                "SOCKS proxy support requires httpx[socks]. "
                "Install with: uv add 'httpx[socks]'"
            )

    # 创建配置了代理的 httpx 客户端
    return httpx.AsyncClient(
        proxy=proxy_url,  # httpx 使用 proxy 而不是 proxies
        timeout=60.0,
    )


def get_langchain_deepseek_config() -> dict:
    """
    获取 LangChain ChatOpenAI 的代理配置参数（用于 DeepSeek）

    LangChain 的 ChatOpenAI 支持传入 http_async_client 来配置代理。

    Returns:
        包含代理配置的参数字典，可直接解包到 ChatOpenAI 构造函数

    Usage:
        >>> from langchain_openai import ChatOpenAI
        >>> from utils.proxy_config import get_langchain_deepseek_config
        >>>
        >>> proxy_config = get_langchain_deepseek_config()
        >>> llm = ChatOpenAI(
        ...     model="deepseek-chat",
        ...     temperature=0.0,
        ...     **proxy_config  # 解包代理配置
        ... )
    """
    proxy_url = get_proxy_url()

    if not proxy_url:
        # 未配置代理，返回空字典
        return {}

    # 创建配置了代理的 httpx 客户端
    http_client = get_deepseek_http_client()

    # LangChain 使用异步客户端
    return {
        "http_async_client": http_client,
    }


def log_proxy_status():
    """
    记录当前代理配置状态（用于调试和启动日志）

    在应用启动时调用，输出代理配置信息。
    """
    proxy_url = get_proxy_url()

    if proxy_url:
        # 隐藏敏感信息（用户名/密码）
        if "@" in proxy_url:
            # 格式：socks5://user:pass@host:port
            safe_url = proxy_url.split("@")[1]
            proxy_type = proxy_url.split("://")[0]
            logger.info(f"🌐 DeepSeek/Daily.co 代理: {proxy_type}://*****@{safe_url}")
        else:
            logger.info(f"🌐 DeepSeek/Daily.co 代理: {proxy_url}")

        # 检查 SOCKS 支持
        if proxy_url.startswith("socks"):
            try:
                import socksio  # noqa: F401
                logger.info("✅ SOCKS 代理支持已安装 (httpx[socks])")
            except ImportError:
                logger.warning(
                    "⚠️ 检测到 SOCKS 代理配置，但缺少依赖。"
                    "请安装: uv add 'httpx[socks]'"
                )
    else:
        logger.info("🌐 DeepSeek/Daily.co 直连模式（未配置代理）")


def get_openai_http_client():
    """Backward-compatible alias for legacy imports."""
    return get_deepseek_http_client()


def get_langchain_openai_config() -> dict:
    """Backward-compatible alias for legacy imports."""
    return get_langchain_deepseek_config()
