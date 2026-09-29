"""
SQL Database Configuration (PostgreSQL/SQLite)

使用 SQLModel + SQLAlchemy 管理关系型数据库
用于存储用户认证数据
"""
import os
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from loguru import logger


# 数据库配置
# 使用 Docker PostgreSQL (userauth-db-1 容器)
# 如果PostgreSQL不可用，回退到SQLite
DATABASE_URL = os.getenv(
    "SQL_DATABASE_URL",
    "sqlite+aiosqlite:///./userauth.db"  # 使用SQLite作为默认，便于开发测试
    # 生产环境可以使用: SQL_DATABASE_URL=postgresql+asyncpg://user:pass@host/db
)

# 创建异步引擎
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # 关闭SQL打印，减少噪音
    future=True,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

# 创建异步会话工厂
async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


def _migrate_missing_columns(conn):
    """检测并补齐 SQLModel 模型中存在但数据库表中缺失的列。"""
    inspector = inspect(conn)
    for table_name, table in SQLModel.metadata.tables.items():
        if not inspector.has_table(table_name):
            continue
        existing = {col["name"] for col in inspector.get_columns(table_name)}
        for col in table.columns:
            if col.name in existing:
                continue
            col_type = col.type.compile(dialect=conn.dialect)
            scalar_default = None
            if col.default is not None and getattr(col.default, "is_scalar", False):
                scalar_default = col.default.arg

            if scalar_default is None:
                default_clause = "DEFAULT NULL" if col.nullable else ""
                nullable_clause = ""
            elif isinstance(scalar_default, bool):
                default_clause = f"DEFAULT {'TRUE' if scalar_default else 'FALSE'}"
                nullable_clause = "NOT NULL"
            elif isinstance(scalar_default, (int, float)):
                default_clause = f"DEFAULT {scalar_default}"
                nullable_clause = "NOT NULL"
            elif isinstance(scalar_default, str):
                escaped = scalar_default.replace("'", "''")
                default_clause = f"DEFAULT '{escaped}'"
                nullable_clause = "NOT NULL"
            else:
                default_clause = ""
                nullable_clause = ""

            preparer = conn.dialect.identifier_preparer
            quoted_table = preparer.quote(table_name)
            quoted_column = preparer.quote(col.name)
            stmt = (
                f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_column} {col_type} "
                f"{default_clause} {nullable_clause}"
            ).strip()
            conn.execute(text(stmt))
            logger.info(f"Migration: added column {table_name}.{col.name} ({col_type})")

    inspector = inspect(conn)
    if inspector.has_table("expert_consultants"):
        existing = {col["name"] for col in inspector.get_columns("expert_consultants")}
        if "application_status" in existing:
            result = conn.execute(
                text(
                    "UPDATE expert_consultants "
                    "SET application_status = 'approved' "
                    "WHERE application_status IS NULL"
                )
            )
            if (result.rowcount or 0) > 0:
                logger.info(
                    "Migration: backfilled expert_consultants.application_status "
                    f"for {result.rowcount} rows"
                )
        if {"application_status", "is_published", "user_id"}.issubset(existing):
            result = conn.execute(
                text(
                    "UPDATE expert_consultants "
                    "SET is_published = FALSE "
                    "WHERE user_id IS NULL "
                    "AND application_status = 'approved' "
                    "AND is_published = TRUE"
                )
            )
            if (result.rowcount or 0) > 0:
                logger.info(
                    "Migration: unpublished expert_consultants rows without user_id "
                    f"for {result.rowcount} approved rows"
                )

    if inspector.has_table("users"):
        duplicate_unionid = conn.execute(
            text(
                "SELECT wechat_unionid FROM users "
                "WHERE wechat_unionid IS NOT NULL "
                "GROUP BY wechat_unionid HAVING COUNT(*) > 1 LIMIT 1"
            )
        ).first()
        if duplicate_unionid:
            # Do not prevent the service from starting on a legacy database.
            # A subsequent successful login repairs a duplicated identity; the
            # migration will create the index on the next restart.
            logger.warning(
                "Migration: skipped unique WeChat UnionID index because legacy "
                "duplicate identities still exist"
            )
        else:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "ux_users_wechat_unionid_not_null "
                    "ON users (wechat_unionid) "
                    "WHERE wechat_unionid IS NOT NULL"
                )
            )


async def init_db():
    """初始化数据库（创建所有表，并补齐已有表的缺失列）"""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        await conn.run_sync(_migrate_missing_columns)
    logger.info("SQL 数据库初始化完成")


async def get_session() -> AsyncSession:
    """获取数据库会话（依赖注入）"""
    async with async_session() as session:
        yield session


async def close_db():
    """关闭数据库连接"""
    await engine.dispose()
    logger.info("SQL 数据库连接已关闭")
