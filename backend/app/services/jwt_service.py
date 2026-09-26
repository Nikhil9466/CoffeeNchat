from datetime import datetime, timedelta, timezone
import os, secrets
from uuid import UUID
import jwt
from fastapi import Cookie, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool
from app.db import get_db, AsyncSessionLocal
from app.models.session_model import AuthSession
from app.models.user_model import User
from app.models.revoked_token_model import RevokedToken
from app.services.security import verify_password

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
if len(JWT_SECRET_KEY) < 32:
    raise ValueError("JWT_SECRET_KEY must contain at least 32 characters")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "30"))
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login", auto_error=False)


async def authenticate_user(db, email, password):
    user = await db.scalar(
        select(User).where(func.lower(User.email) == email.lower()).with_for_update()
    )
    if (
        not user
        or user.is_disabled
        or not await run_in_threadpool(verify_password, password, user.password_hash)
    ):
        return None
    return user


async def create_access_token(user, db, label="Browser", remember=False):
    now = datetime.now(timezone.utc)
    expiry = now + (
        timedelta(days=30) if remember else timedelta(minutes=JWT_EXPIRE_MINUTES)
    )
    jti = secrets.token_hex(24)
    await db.execute(delete(AuthSession).where(AuthSession.expires_at < now))
    db.add(
        AuthSession(
            id=jti,
            user_id=user.id,
            label=label[:256],
            created_at=now,
            expires_at=expiry,
        )
    )
    await db.commit()
    return jwt.encode(
        {"sub": str(user.id), "jti": jti, "iat": now, "exp": expiry},
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


async def decode_access_token(token, db):
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "jti", "exp", "iat"]},
        )
        uid = UUID(payload["sub"])
        session = await db.get(AuthSession, payload["jti"])
        user = await db.get(User, uid)
        if (
            not session
            or session.user_id != uid
            or session.expires_at <= datetime.now(timezone.utc)
            or not user
            or user.is_disabled
            or await db.get(RevokedToken, payload["jti"])
        ):
            raise ValueError()
        return payload
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        raise HTTPException(
            401,
            "Session expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def validate_token(token):
    try:
        async with AsyncSessionLocal() as db:
            payload = await decode_access_token(token, db)
            return UUID(payload["sub"])
    except Exception:
        return None


async def revoke_access_token(token):
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"verify_exp": False},
        )
    except jwt.PyJWTError:
        return
    async with AsyncSessionLocal() as db:
        await db.execute(
            delete(AuthSession).where(AuthSession.id == payload.get("jti"))
        )
        await db.commit()


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str | None = Depends(oauth2_scheme),
    access_token: str | None = Cookie(default=None),
):
    payload = await decode_access_token(token or access_token or "", db)
    return await db.get(User, UUID(payload["sub"]))


async def require_admin(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(403, "Administrator access required")
    return current_user
