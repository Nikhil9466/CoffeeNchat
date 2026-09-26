from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, Request, Query
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool
from app.db import get_db
from app.config import COOKIE_SECURE
from app.models.user_model import User
from app.models.session_model import AuthSession
from app.models.conversation_model import ConversationParticipant as CP
from app.schema.user_schema import (
    UserCreate,
    UserResponse,
    PublicUser,
    UserUpdate,
    LoginRequest,
    PasswordChange,
    SensitiveAction,
)
from app.services.security import hash_password, verify_password
from app.services.jwt_service import (
    get_current_user,
    authenticate_user,
    create_access_token,
    revoke_access_token,
    oauth2_scheme,
    decode_access_token,
    JWT_EXPIRE_MINUTES,
)

router = APIRouter(prefix="/users", tags=["Users"])


def cookie(response, token, remember=False):
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
        max_age=30 * 86400 if remember else JWT_EXPIRE_MINUTES * 60,
    )


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    payload: UserCreate,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user = User(
        email=str(payload.email).lower(),
        username=payload.username,
        password_hash=await run_in_threadpool(hash_password, payload.password),
        bio="",
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Email or username is already in use.")
    await db.refresh(user)
    cookie(
        response,
        await create_access_token(
            user, db, request.headers.get("user-agent", "Browser")
        ),
    )
    return user


@router.post("/login", response_model=UserResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user = await authenticate_user(db, str(payload.email), payload.password)
    if not user:
        raise HTTPException(401, "Invalid email or password.")
    cookie(
        response,
        await create_access_token(
            user, db, request.headers.get("user-agent", "Browser"), payload.remember_me
        ),
        payload.remember_me,
    )
    return user


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    token: str | None = Depends(oauth2_scheme),
    access_token: str | None = Cookie(default=None),
):
    await revoke_access_token(token or access_token or "")
    response.delete_cookie(
        "access_token", path="/", secure=COOKIE_SECURE, httponly=True, samesite="lax"
    )


@router.get("", response_model=list[PublicUser])
async def users(
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(User).where(User.is_disabled.is_(False))
    if q:
        stmt = stmt.where(
            User.username.ilike("%" + q.replace("%", r"\%").replace("_", r"\_") + "%")
        )
    return (
        await db.scalars(
            stmt.order_by(User.username, User.id).limit(limit).offset(offset)
        )
    ).all()


@router.get("/sessions")
async def sessions(
    token: str | None = Depends(oauth2_scheme),
    access_token: str | None = Cookie(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    current = (await decode_access_token(token or access_token or "", db))["jti"]
    rows = (
        await db.scalars(
            select(AuthSession)
            .where(
                AuthSession.user_id == user.id,
                AuthSession.expires_at > datetime.now(timezone.utc),
            )
            .order_by(AuthSession.created_at.desc())
        )
    ).all()
    return [
        {
            "id": s.id,
            "label": s.label,
            "created_at": s.created_at,
            "expires_at": s.expires_at,
            "current": s.id == current,
        }
        for s in rows
    ]


@router.delete("/sessions/{session_id}", status_code=204)
async def end_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        delete(AuthSession).where(
            AuthSession.id == session_id, AuthSession.user_id == user.id
        )
    )
    await db.commit()


@router.post("/password", status_code=204)
async def password(
    payload: PasswordChange,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not await run_in_threadpool(
        verify_password, payload.current_password, user.password_hash
    ):
        raise HTTPException(403, "Current password is incorrect.")
    user.password_hash = await run_in_threadpool(hash_password, payload.password)
    await db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    await db.commit()
    response.delete_cookie("access_token", path="/")


@router.put("/{user_id}", response_model=UserResponse)
async def update(
    user_id: UUID,
    payload: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.id != user_id:
        raise HTTPException(403, "You can only edit your own profile.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            value = value.strip()
            if key == "username" and len(value) < 3:
                raise HTTPException(422, "Username must contain at least 3 characters")
            setattr(user, key, value)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Username is already in use.")
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
async def remove(
    user_id: UUID,
    payload: SensitiveAction,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.id != user_id:
        raise HTTPException(403, "You can only delete your own account.")
    # Serialize group membership changes using the same conversation locks as group actions.
    from app.services.conversation_service import assert_can_leave, notify_change

    memberships = (
        await db.scalars(
            select(CP).where(CP.user_id == user.id).order_by(CP.conversation_id)
        )
    ).all()
    for membership in memberships:
        await assert_can_leave(db, membership.conversation_id, user.id)
    user = await db.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not await run_in_threadpool(
        verify_password, payload.current_password, user.password_hash
    ):
        raise HTTPException(403, "Current password is incorrect.")
    for member in memberships:
        await notify_change(db, member.conversation_id)
    await db.execute(delete(User).where(User.id == user.id))
    await db.commit()
    response.delete_cookie("access_token", path="/")
