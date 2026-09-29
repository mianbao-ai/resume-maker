"""
Resume Parsing Service - 统一的简历解析服务

该服务整合了完整的简历解析流程：
1. 文档加载：使用 LangChain 从 PDF/DOCX 提取文本
2. 信息提取：使用 LangChain Chains 提取结构化信息
3. 文件存储：保存到用户对应的文件夹

职责：
- 文本提取（LangChain document loaders）
- 信息提取（LangChain chains）
- 结果存储（用户数据目录）
- 缓存管理（避免重复解析）
- 后台任务调度（非阻塞解析）

文件结构：
    data/{env}/{user_id}/
        resume/              # 原始简历文件（由 profile API 管理）
        intermediate/        # 解析后的数据
            resume_facts_<resume_id>.json

Author: Cheng & Claude
Date: 2025-12-07
"""
import os
import asyncio
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Awaitable
from loguru import logger

try:
    from langfuse import get_client, propagate_attributes
    from langfuse.langchain import CallbackHandler
except Exception:  # pragma: no cover - fail-open when langfuse unavailable
    CallbackHandler = None
    get_client = None
    propagate_attributes = None

# LangChain document loaders
try:
    from langchain_community.document_loaders import PyPDFLoader
    PDF_LOADER_AVAILABLE = True
except ImportError:
    PDF_LOADER_AVAILABLE = False
    logger.warning("PyPDFLoader not available. Install: pip install langchain-community pypdf")

try:
    from langchain_community.document_loaders import Docx2txtLoader
    DOCX_LOADER_AVAILABLE = True
except ImportError:
    DOCX_LOADER_AVAILABLE = False
    logger.warning("Docx2txtLoader not available. Install: pip install langchain-community docx2txt")

# LangChain chains for information extraction
from .chains.extraction import DEFAULT_DEEPSEEK_MODEL, extract_resume_facts
from .chains.schemas import ResumeFacts
from .cache import load_resume_facts, write_json_atomic

# Type alias for progress callback
ProgressCallback = Optional[Callable[[str, int, str], Awaitable[None]]]


# ==================== 文件路径工具函数 ====================

def _normalize_env_name(raw_env: str) -> str:
    """标准化环境名称"""
    if not raw_env:
        return "development"
    env = raw_env.lower()
    if env in ("dev", "development", "local"):
        return "development"
    if env in ("prod", "production"):
        return "production"
    if env in ("stage", "staging"):
        return "staging"
    return env


def get_user_data_dir(user_id: str) -> Path:
    """
    获取用户数据目录

    Returns: data/{env}/{user_id}/
    """
    env_name = _normalize_env_name(os.getenv("ENV") or os.getenv("ENVIRONMENT"))
    project_root = Path(__file__).resolve().parents[2]  # 上到 server/
    data_root = Path(os.getenv("DATA_ROOT", project_root / "data"))

    user_dir = data_root / env_name / str(user_id)
    return user_dir


def get_intermediate_dir(user_id: str) -> Path:
    """
    获取中间数据目录（存放解析结果）

    Returns: data/{env}/{user_id}/intermediate/
    """
    return get_user_data_dir(user_id) / "intermediate"


def get_resume_facts_path(user_id: str, resume_id: Optional[str] = None) -> Path:
    """Return the canonical Resume Facts cache path."""
    filename = f"resume_facts_{resume_id}.json" if resume_id else "resume_facts.json"
    return get_intermediate_dir(user_id) / filename


# ==================== 文档加载器 ====================

class DocumentLoader:
    """
    文档加载器 - 使用 LangChain 提取文本

    支持格式：
    - PDF: 使用 PyPDFLoader
    - DOCX: 使用 Docx2txtLoader
    """

    SUPPORTED_EXTENSIONS = {'.pdf', '.docx'}

    def __init__(self):
        """初始化文档加载器"""
        self._validate_dependencies()

    def _validate_dependencies(self):
        """检查 LangChain loaders 是否可用"""
        if not PDF_LOADER_AVAILABLE:
            logger.warning(
                "⚠️ PyPDFLoader not available. "
                "Install: pip install langchain-community pypdf"
            )
        if not DOCX_LOADER_AVAILABLE:
            logger.warning(
                "⚠️ Docx2txtLoader not available. "
                "Install: pip install langchain-community docx2txt"
            )

    def load_text(self, file_path: str) -> str:
        """
        从文件提取文本（使用 LangChain）

        Args:
            file_path: 文件路径 (.pdf 或 .docx)

        Returns:
            提取的文本内容

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 不支持的文件格式
            RuntimeError: 文本提取失败
        """
        # 验证文件存在
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 检测文件格式
        file_ext = Path(file_path).suffix.lower()

        if file_ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"不支持的文件格式: {file_ext}。"
                f"支持的格式: {', '.join(self.SUPPORTED_EXTENSIONS)}"
            )

        # 使用 LangChain 加载文档
        logger.info(f"📄 使用 LangChain 加载文档: {file_path} ({file_ext})")

        try:
            if file_ext == '.pdf':
                text = self._load_from_pdf(file_path)
            elif file_ext == '.docx':
                text = self._load_from_docx(file_path)
            else:
                raise ValueError(f"未实现的文件格式: {file_ext}")

            logger.info(f"✅ 文档加载成功: {len(text)} 字符")
            return text.strip()

        except Exception as e:
            logger.error(f"❌ 文档加载失败: {e}")
            raise RuntimeError(f"文档加载失败: {str(e)}") from e

    def _load_from_pdf(self, pdf_path: str) -> str:
        """从 PDF 文件提取文本（使用 LangChain PyPDFLoader）"""
        if not PDF_LOADER_AVAILABLE:
            raise RuntimeError(
                "PyPDFLoader 未安装。请安装: pip install langchain-community pypdf"
            )

        try:
            loader = PyPDFLoader(pdf_path)
            documents = loader.load()

            # 提取并合并所有页面的文本，跳过损坏的页面
            text_parts = []
            for i, doc in enumerate(documents, start=1):
                try:
                    page_text = doc.page_content
                    text_parts.append(page_text)
                    logger.debug(f"📄 加载第 {i}/{len(documents)} 页: {len(page_text)} 字符")
                except (KeyError, AttributeError) as page_err:
                    logger.warning(f"⚠️ 跳过第 {i}/{len(documents)} 页 (解析失败: {page_err})")
                    continue

            combined_text = "\n".join(text_parts)

            if not combined_text.strip():
                logger.warning("⚠️ PDF 文件为空或无法提取文本")

            return combined_text

        except (KeyError, AttributeError) as e:
            # Handle malformed PDF metadata (e.g. missing 'bbox')
            logger.warning(f"⚠️ PDF 元数据异常，尝试降级提取: {e}")
            try:
                import pypdf
                reader = pypdf.PdfReader(pdf_path)
                text_parts = []
                for i, page in enumerate(reader.pages, start=1):
                    try:
                        text_parts.append(page.extract_text() or "")
                    except Exception:
                        logger.warning(f"⚠️ 降级提取: 跳过第 {i} 页")
                        continue
                return "\n".join(text_parts)
            except Exception as fallback_err:
                raise RuntimeError(f"PDF 加载失败: {str(e)}") from fallback_err
        except Exception as e:
            raise RuntimeError(f"PDF 加载失败: {str(e)}") from e

    def _load_from_docx(self, docx_path: str) -> str:
        """从 DOCX 文件提取文本（使用 LangChain Docx2txtLoader）"""
        if not DOCX_LOADER_AVAILABLE:
            raise RuntimeError(
                "Docx2txtLoader 未安装。请安装: pip install langchain-community docx2txt"
            )

        try:
            loader = Docx2txtLoader(docx_path)
            documents = loader.load()

            # 提取并合并所有文档的文本
            text_parts = [doc.page_content for doc in documents]
            combined_text = "\n".join(text_parts)

            if not combined_text.strip():
                logger.warning("⚠️ DOCX 文件为空或无法提取文本")

            return combined_text

        except Exception as e:
            raise RuntimeError(f"DOCX 加载失败: {str(e)}") from e

    def is_supported(self, file_path: str) -> bool:
        """检查文件格式是否支持"""
        file_ext = Path(file_path).suffix.lower()
        return file_ext in self.SUPPORTED_EXTENSIONS


# ==================== 简历解析服务 ====================

class ResumeParsingService:
    """
    简历解析服务 - 统一的解析、提取、存储服务

    功能：
    1. 文本提取（DocumentLoader + LangChain）
    2. 信息提取（LangChain Chains）
    3. 结果存储（保存到用户文件夹）
    4. 缓存管理（避免重复解析）
    5. 后台任务（非阻塞解析）

    使用示例：
        >>> service = ResumeParsingService()
        >>> # 同步解析并存储
        >>> facts = await service.parse_and_save("/path/to/resume.pdf", "user_123")
        >>> # 后台解析（非阻塞）
        >>> service.schedule_background_parse("/path/to/resume.pdf", "user_123")
        >>> # 获取缓存
        >>> cached = service.get_cached_facts("user_123")
    """

    def __init__(
        self,
        model_name: str = DEFAULT_DEEPSEEK_MODEL,
        temperature: float = 0.0,
        api_key: Optional[str] = None,
    ):
        """
        初始化简历解析服务

        Args:
            model_name: DeepSeek 模型名称
            temperature: 温度参数 (default: 0.0 = 确定性输出)
            api_key: DeepSeek API Key (可选，默认从环境变量读取)
        """
        self.model_name = model_name
        self.temperature = temperature
        self.api_key = (
            api_key
            or os.getenv("DEEPSEEK_API_KEY")
        )

        # 初始化文档加载器
        self.document_loader = DocumentLoader()
        self._runtime_status: Dict[str, Dict[str, Any]] = {}

        logger.info(f"📦 ResumeParsingService initialized (model={model_name})")

    def _set_runtime_status(
        self,
        user_id: str,
        state: str,
        *,
        resume_id: Optional[str] = None,
        error: Optional[str] = None,
        path: Optional[str] = None,
        name: Optional[str] = None,
        updated_at: Optional[float] = None,
    ) -> Dict[str, Any]:
        status = {
            "state": state,
            "parsed": state == "ready",
            "path": path,
            "name": name,
            "updated_at": updated_at,
            "error": error,
        }
        self._runtime_status[f"{user_id}:{resume_id or 'default'}"] = status
        return status

    def _create_langfuse_handler(self, trace_context: Dict[str, Any] | None = None) -> Any | None:
        """Create a Langfuse handler if the SDK and config are available."""
        if CallbackHandler is None or get_client is None:
            return None

        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        if not public_key or not secret_key:
            return None

        try:
            return CallbackHandler(public_key=public_key, trace_context=trace_context)
        except Exception as exc:
            logger.warning(f"⚠️ 创建 Langfuse CallbackHandler 失败，将跳过 tracing: {exc}")
            return None

    # ==================== 核心解析方法 ====================

    async def parse_resume(
        self,
        file_path: str,
        progress_callback: ProgressCallback = None,
        *,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        resume_id: Optional[str] = None,
    ) -> ResumeFacts:
        """
        解析简历文件并提取结构化信息（不保存）

        Args:
            file_path: 简历文件路径 (PDF 或 DOCX)
            progress_callback: 可选的进度回调
                签名: async def callback(stage: str, progress: int, message: str)

        Returns:
            规范化的 ResumeFacts 事实对象

        Example:
            >>> service = ResumeParsingService()
            >>> facts = await service.parse_resume("/path/to/resume.pdf")
            >>> print(facts.basic_info.name, facts.education)
        """
        logger.info(f"🚀 开始解析简历: {file_path}")
        langfuse_client = None

        try:
            # Step 1: 读取文件并提取文本 (0% -> 20%)
            if progress_callback:
                await progress_callback("reading", 10, "正在读取文件...")

            resume_text = self.document_loader.load_text(file_path)

            if progress_callback:
                await progress_callback("reading", 20, f"文件读取完成 ({len(resume_text)} 字符)")

            # Step 2: 使用 LangChain 提取结构化信息 (20% -> 100%)
            if progress_callback:
                await progress_callback("extracting", 30, "使用 LangChain 提取信息...")

            langfuse_client = get_client() if get_client is not None else None
            trace_context = None
            if langfuse_client is not None and session_id:
                trace_context = {"trace_id": langfuse_client.create_trace_id(seed=session_id)}
            langfuse_handler = self._create_langfuse_handler(trace_context)

            if propagate_attributes and (user_id or session_id):
                with propagate_attributes(
                    user_id=user_id,
                    session_id=session_id,
                    metadata={"resume_id": resume_id} if resume_id else None,
                ):
                    facts = await extract_resume_facts(
                        resume_text,
                        resume_id=resume_id or "default",
                        model_name=self.model_name,
                        temperature=self.temperature,
                        api_key=self.api_key,
                        langfuse_handler=langfuse_handler,
                    )
            else:
                facts = await extract_resume_facts(
                    resume_text,
                    resume_id=resume_id or "default",
                    model_name=self.model_name,
                    temperature=self.temperature,
                    api_key=self.api_key,
                    langfuse_handler=langfuse_handler,
                )

            if progress_callback:
                await progress_callback("completed", 100, "简历解析完成！")

            logger.info(f"✅ 简历解析成功: {facts.basic_info.name or 'Unknown'}")
            return facts

        except Exception as e:
            logger.error(f"❌ 简历解析失败: {e}")
            if progress_callback:
                await progress_callback("failed", 0, f"解析失败: {str(e)}")
            raise
        finally:
            if langfuse_client is not None:
                try:
                    langfuse_client.flush()
                except Exception as exc:
                    logger.warning(f"⚠️ Langfuse flush 失败，将继续忽略 tracing: {exc}")

    async def parse_from_bytes(
        self,
        file_data: bytes,
        filename: str,
        progress_callback: ProgressCallback = None,
    ) -> ResumeFacts:
        """
        从字节数据解析简历（用于上传的文件）

        Args:
            file_data: 文件字节数据
            filename: 文件名（用于判断文件类型）
            progress_callback: 可选的进度回调

        Returns:
            规范化的 ResumeFacts 事实对象
        """
        # 保存到临时文件
        file_ext = Path(filename).suffix
        temp_file_path = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
                temp_file.write(file_data)
                temp_file_path = temp_file.name

            # 解析临时文件
            return await self.parse_resume(temp_file_path, progress_callback)

        finally:
            # 清理临时文件
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                logger.debug(f"🧹 临时文件已删除: {temp_file_path}")

    # ==================== 解析 + 存储 ====================

    async def parse_and_save(
        self,
        resume_path: str,
        user_id: str,
        force_reparse: bool = False,
        progress_callback: ProgressCallback = None,
        *,
        session_id: Optional[str] = None,
        resume_id: Optional[str] = None,
    ) -> Optional[ResumeFacts]:
        """
        解析简历并保存到用户文件夹

        Args:
            resume_path: 简历文件路径
            user_id: 用户 ID
            force_reparse: 如果为 True，即使缓存存在也重新解析
            progress_callback: 可选的进度回调

        Returns:
            规范化后的 ResumeFacts，失败返回 None

        存储路径:
            data/{env}/{user_id}/intermediate/resume_facts_<resume_id>.json

        Example:
            >>> service = ResumeParsingService()
            >>> facts = await service.parse_and_save("/path/to/resume.pdf", "user_123")
        """
        facts_path = get_resume_facts_path(user_id, resume_id)

        # Resume Facts is the only persisted parsing result.
        if not force_reparse and facts_path.exists():
            logger.info(f"📦 简历事实已存在，跳过解析: {facts_path}")
            try:
                facts = load_resume_facts(facts_path)
                self._set_runtime_status(
                    user_id,
                    "ready",
                    resume_id=resume_id,
                    path=str(facts_path),
                    name=facts.basic_info.name,
                    updated_at=facts_path.stat().st_mtime,
                )
                return facts
            except Exception as e:
                logger.warning(f"⚠️ 读取简历事实失败: {e}，将重新解析")

        logger.info(f"🚀 开始解析并保存简历: user_id={user_id}, path={resume_path}")
        self._set_runtime_status(user_id, "parsing", resume_id=resume_id)

        try:
            # 解析简历
            facts = await self.parse_resume(
                resume_path,
                progress_callback,
                user_id=user_id,
                session_id=session_id,
                resume_id=resume_id,
            )
            # Persist the canonical facts only.
            write_json_atomic(facts_path, facts.model_dump(mode="json"))

            updated_at = facts_path.stat().st_mtime
            self._set_runtime_status(
                user_id,
                "ready",
                resume_id=resume_id,
                path=str(facts_path),
                name=facts.basic_info.name,
                updated_at=updated_at,
            )

            logger.info(f"✅ 简历事实解析完成并保存: {facts_path}")
            primary_education = facts.education[0] if facts.education else None
            logger.info(
                "📊 解析摘要: 姓名={}, 学校={}, 专业={}",
                facts.basic_info.name,
                primary_education.institution_name if primary_education else "",
                primary_education.major if primary_education else "",
            )

            return facts

        except Exception as e:
            self._set_runtime_status(user_id, "failed", resume_id=resume_id, error=str(e))
            logger.error(f"❌ 解析简历失败: {e}")
            logger.exception(e)
            return None

    # ==================== 缓存管理 ====================

    def get_cached_facts(
        self,
        user_id: str,
        resume_id: Optional[str] = None,
    ) -> Optional[ResumeFacts]:
        facts_path = get_resume_facts_path(user_id, resume_id)
        if not facts_path.exists():
            return None
        try:
            return load_resume_facts(facts_path)
        except Exception as exc:
            logger.error(f"❌ 读取简历事实失败: {exc}")
            return None

    async def delete_cached_info(self, user_id: str, resume_id: Optional[str] = None) -> bool:
        """
        删除缓存的解析结果

        适用场景：
        - 用户上传新简历（应删除旧缓存）
        - 用户删除简历
        - 手动清理缓存

        Args:
            user_id: 用户 ID

        Returns:
            True 如果删除成功，False 如果未找到
        """
        if resume_id:
            paths = [
                get_resume_facts_path(user_id, resume_id),
                get_intermediate_dir(user_id) / f"student_info_{resume_id}.json",
            ]
        else:
            intermediate_dir = get_intermediate_dir(user_id)
            paths = [
                *intermediate_dir.glob("student_info*.json"),
                *intermediate_dir.glob("resume_facts*.json"),
            ]

        if not paths:
            logger.debug(f"📭 缓存文件不存在，无需删除: user_id={user_id}, resume_id={resume_id}")
            for key in list(self._runtime_status):
                if key.startswith(f"{user_id}:"):
                    self._runtime_status.pop(key, None)
            return False

        try:
            deleted = False
            for parsed_info_path in paths:
                if parsed_info_path.exists():
                    parsed_info_path.unlink()
                    deleted = True
                    logger.info(f"🗑️ 已删除缓存的简历信息: {parsed_info_path}")
            if resume_id:
                self._runtime_status.pop(f"{user_id}:{resume_id}", None)
            else:
                for key in list(self._runtime_status):
                    if key.startswith(f"{user_id}:"):
                        self._runtime_status.pop(key, None)
            return deleted
        except Exception as e:
            logger.error(f"❌ 删除缓存失败: {e}")
            return False

    def get_parsing_status(self, user_id: str, resume_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取解析状态

        Returns:
            {
                "state": str,           # not_started | queued | parsing | ready | failed
                "parsed": bool,          # 是否已解析
                "path": str,             # 缓存文件路径（如果存在）
                "name": str,             # 学生姓名（如果可用）
                "updated_at": float,     # 文件修改时间（如果可用）
                "error": str | None      # 失败原因（如果可用）
            }
        """
        facts_path = get_resume_facts_path(user_id, resume_id)
        runtime_status = self._runtime_status.get(f"{user_id}:{resume_id or 'default'}")

        if runtime_status and runtime_status["state"] in {"queued", "parsing", "failed"}:
            return runtime_status

        if not facts_path.exists():
            return {
                "state": "not_started",
                "parsed": False,
                "path": None,
                "name": None,
                "updated_at": None,
                "error": None,
            }

        try:
            # 获取文件修改时间
            updated_at = facts_path.stat().st_mtime
            facts = load_resume_facts(facts_path)
            name = facts.basic_info.name or "Unknown"

            return self._set_runtime_status(
                user_id,
                "ready",
                resume_id=resume_id,
                path=str(facts_path),
                name=name,
                updated_at=updated_at,
            )
        except Exception as e:
            logger.error(f"❌ 获取解析状态失败: {e}")
            return {
                "state": "failed",
                "parsed": True,  # 文件存在但无法读取
                "path": str(facts_path),
                "name": None,
                "updated_at": None,
                "error": str(e),
            }

    # ==================== 后台任务调度 ====================

    def schedule_background_parse(
        self,
        resume_path: str,
        user_id: str,
        force_reparse: bool = False,
        *,
        session_id: Optional[str] = None,
        resume_id: Optional[str] = None,
    ):
        """
        调度后台解析任务（非阻塞）

        该方法立即返回，解析在后台进行，不会阻塞上传响应。

        Args:
            resume_path: 简历文件路径
            user_id: 用户 ID

        Example:
            >>> # 在上传 API 中:
            >>> service.schedule_background_parse("/uploads/resume.pdf", "user_123")
            >>> # 立即返回，解析在后台进行
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # 当前线程没有事件循环
            logger.warning("⚠️ 无法获取事件循环，跳过后台解析")
            return

        self._set_runtime_status(user_id, "queued", resume_id=resume_id)

        # 创建并调度任务
        task = loop.create_task(
            self.parse_and_save(
                resume_path,
                user_id,
                force_reparse=force_reparse,
                session_id=session_id,
                resume_id=resume_id,
            )
        )

        # 添加完成回调
        def on_complete(future):
            try:
                result = future.result()
                if result:
                    logger.info(f"✅ 后台解析任务完成: user_id={user_id}, name={result.get('name')}")
                    # Trigger question pre-generation after successful resume parse
                    _trigger_question_pregen_after_parse(user_id, resume_id)
                else:
                    logger.warning(f"⚠️ 后台解析任务失败: user_id={user_id}")
            except Exception as e:
                logger.error(f"❌ 后台解析任务异常: user_id={user_id}, error={e}")

        task.add_done_callback(on_complete)

        logger.info(f"📋 后台解析任务已调度: user_id={user_id}")


def _trigger_question_pregen_after_parse(user_id: str, resume_id: Optional[str] = None):
    """Trigger question pre-generation after resume parse completes.

    Reads the user's interview settings (if any) to determine question counts,
    otherwise uses defaults.
    """
    try:
        from features.questions.service import schedule_background_question_gen

        # Try to load user's interview settings for question counts
        english, professional, project = 2, 2, 2
        try:
            # We're in a sync callback, so read settings from a sync path.
            # Use asyncio to run the DB query in the existing event loop.
            import asyncio
            from sqlmodel import select
            from models.interview_setting import InterviewSetting
            from models.user import User
            from infrastructure.database.sql import async_session

            async def _load_context():
                async with async_session() as session:
                    stmt = select(InterviewSetting).where(
                        InterviewSetting.user_id == user_id
                    ).order_by(InterviewSetting.updated_at.desc())
                    result = await session.execute(stmt)
                    setting = result.scalar_one_or_none()
                    preferred_scene = "graduate"
                    user_result = await session.execute(select(User).where(User.id == user_id))
                    user = user_result.scalar_one_or_none()
                    if user and user.preferred_scene in {"job", "graduate"}:
                        preferred_scene = user.preferred_scene
                    return setting, preferred_scene

            loop = asyncio.get_event_loop()
            setting_task = loop.create_task(_load_context())

            def _on_setting_loaded(fut):
                try:
                    setting, preferred_scene = fut.result()
                    e = setting.english_questions if setting else 2
                    p = setting.professional_questions if setting else 2
                    pj = setting.project_questions if setting else 2
                    scene = setting.scene if setting and setting.scene in {"job", "graduate"} else preferred_scene
                    jd = setting.job_description if setting and scene == "job" else ""
                    schedule_background_question_gen(
                        user_id,
                        e,
                        p,
                        pj,
                        scene=scene,
                        resume_id=resume_id,
                        job_description=jd,
                    )
                except Exception as ex:
                    logger.warning(f"⚠️ Failed to load settings for question pregen: {ex}")
                    # Fall back to defaults
                    schedule_background_question_gen(user_id, resume_id=resume_id)

            setting_task.add_done_callback(_on_setting_loaded)
        except Exception:
            # If anything fails with settings, just use defaults
            schedule_background_question_gen(user_id, resume_id=resume_id)

    except Exception as e:
        logger.warning(f"⚠️ Failed to trigger question pregen after parse: {e}")


# ==================== 全局实例（单例模式） ====================

_default_service: Optional[ResumeParsingService] = None


def get_parsing_service() -> ResumeParsingService:
    """
    获取默认的 ResumeParsingService 实例（单例模式）

    Returns:
        ResumeParsingService 实例

    Example:
        >>> from features.resume.parsing_service import get_parsing_service
        >>> service = get_parsing_service()
        >>> facts = await service.parse_and_save("/path/to/resume.pdf", "user_123")
    """
    global _default_service
    if _default_service is None:
        _default_service = ResumeParsingService()
    return _default_service


# ==================== 便捷函数 ====================

async def parse_and_save(
    resume_path: str,
    user_id: str,
    force_reparse: bool = False,
    *,
    session_id: Optional[str] = None,
    resume_id: Optional[str] = None,
) -> Optional[ResumeFacts]:
    """
    便捷函数：解析简历并保存

    使用默认的 ResumeParsingService 实例
    """
    return await get_parsing_service().parse_and_save(
        resume_path,
        user_id,
        force_reparse,
        session_id=session_id,
        resume_id=resume_id,
    )


def get_cached_resume_facts(
    user_id: str,
    resume_id: Optional[str] = None,
) -> Optional[ResumeFacts]:
    """Return canonical resume facts for business consumers."""
    return get_parsing_service().get_cached_facts(user_id, resume_id=resume_id)


def schedule_background_parse(
    resume_path: str,
    user_id: str,
    force_reparse: bool = False,
    *,
    session_id: Optional[str] = None,
    resume_id: Optional[str] = None,
):
    """
    便捷函数：调度后台解析任务

    使用默认的 ResumeParsingService 实例
    """
    get_parsing_service().schedule_background_parse(
        resume_path,
        user_id,
        force_reparse=force_reparse,
        session_id=session_id,
        resume_id=resume_id,
    )


def get_parsing_status(user_id: str, resume_id: Optional[str] = None) -> Dict[str, Any]:
    """
    便捷函数：获取解析状态

    使用默认的 ResumeParsingService 实例
    """
    return get_parsing_service().get_parsing_status(user_id, resume_id=resume_id)
