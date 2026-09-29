"""
User Model (SQLModel)

使用 SQLModel 定义用户认证模型（PostgreSQL/SQLite）
"""
from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional


class User(SQLModel, table=True):
    """
    User model for authentication (关系型数据库)

    Attributes:
        id: Primary key
        email: Unique email address (indexed, optional for WeChat-only users)
        hashed_password: Bcrypt hashed password (optional for social login users)
        username: User's display name
        phone: Phone number (optional, for phone login)
        wechat_openid: WeChat OpenID (unique, optional)
        wechat_unionid: WeChat UnionID (optional, for multi-app scenarios)
        avatar_url: User avatar URL (optional)
        is_active: Account active status (default: True)
        created_at: Timestamp of account creation
        updated_at: Timestamp of last update
    """
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: Optional[str] = Field(default=None, unique=True, index=True, max_length=255)
    hashed_password: Optional[str] = Field(default=None, max_length=255)
    username: str = Field(min_length=1, max_length=100)
    phone: Optional[str] = Field(default=None, unique=True, index=True, max_length=20)
    wechat_openid: Optional[str] = Field(default=None, unique=True, index=True, max_length=100)
    # UnionID is stable across WeChat apps owned by the same Open Platform
    # account, so it is the canonical cross-AppID identity for login linking.
    wechat_unionid: Optional[str] = Field(
        default=None, unique=True, index=True, max_length=100
    )
    wechat_official_openid: Optional[str] = Field(default=None, unique=True, index=True, max_length=100)
    wechat_official_subscribed: bool = Field(default=False)
    wechat_official_bound_at: Optional[datetime] = Field(default=None)
    avatar_url: Optional[str] = Field(default=None, max_length=500)
    source_channel: Optional[str] = Field(default=None, max_length=50)
    # Scene preference is separate from the scene of an individual operation.
    # ``signup_scene`` is immutable attribution; ``preferred_scene`` is the
    # user-controlled default used when a request does not provide a scene.
    signup_scene: Optional[str] = Field(default=None, max_length=20)
    preferred_scene: Optional[str] = Field(default=None, max_length=20)
    last_active_scene: Optional[str] = Field(default=None, max_length=20)
    scene_usage_streak: int = Field(default=0, ge=0)
    points_balance: int = Field(default=300, ge=0)
    total_points_recharged: int = Field(default=0, ge=0)
    referral_code: Optional[str] = Field(default=None, unique=True, index=True, max_length=10)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def __repr__(self) -> str:
        return f"User(id={self.id}, email={self.email}, username={self.username})"

    def __str__(self) -> str:
        return self.email
