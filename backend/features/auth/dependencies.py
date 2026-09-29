"""
Authentication Dependencies (SQLModel)

使用 SQLModel 实现认证依赖注入
"""
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError

from models.user import User
from infrastructure.security.auth import SECRET_KEY, ALGORITHM
from infrastructure.database.sql import get_session


security = HTTPBearer()
security_optional = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session)
) -> User:
    """
    Get current authenticated user from JWT token.

    Supports multiple login types:
    - Email/password login (sub = email)
    - WeChat login (sub = openid, type = wechat)

    Args:
        credentials: HTTP Bearer credentials (JWT token)
        session: Database session

    Returns:
        Current authenticated User

    Raises:
        HTTPException 401: If token is invalid or user not found
    """
    token = credentials.credentials

    try:
        # Decode JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        identifier: str = payload.get("sub")
        login_type: str = payload.get("type", "email")  # default to email for backwards compatibility

        if identifier is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Find user based on login type
    if login_type == "wechat":
        # WeChat login - identifier is openid
        statement = select(User).where(User.wechat_openid == identifier)
    else:
        # Email login - identifier is email
        statement = select(User).where(User.email == identifier)

    result = await session.execute(statement)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    return user


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional),
    session: AsyncSession = Depends(get_session),
) -> Optional[User]:
    if credentials is None:
        return None
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        identifier: str = payload.get("sub")
        login_type: str = payload.get("type", "email")
        if identifier is None:
            return None
    except JWTError:
        return None

    if login_type == "wechat":
        statement = select(User).where(User.wechat_openid == identifier)
    else:
        statement = select(User).where(User.email == identifier)

    result = await session.execute(statement)
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to get the current active user.

    Args:
        current_user: Current user from get_current_user dependency

    Returns:
        User object if active

    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    return current_user
