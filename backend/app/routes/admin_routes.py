from datetime import datetime, timedelta, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, delete, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.models.user_model import User
from app.models.message_model import Message
from app.models.conversation_model import Conversation
from app.models.session_model import AuthSession
from app.models.feature_model import Report
from app.schema.user_schema import UserResponse
from app.services.jwt_service import require_admin

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/stats")
async def stats(
    user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    now = datetime.now(timezone.utc)
    return {
        "total_users": await db.scalar(select(func.count()).select_from(User)),
        "active_rooms": await db.scalar(select(func.count()).select_from(Conversation)),
        "messages_today": await db.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.created_at >= now - timedelta(days=1))
        ),
        "reported_content": await db.scalar(
            select(func.count()).select_from(Report).where(Report.status == "open")
        ),
        "active_sessions": await db.scalar(
            select(func.count())
            .select_from(AuthSession)
            .where(AuthSession.expires_at > now)
        ),
    }


@router.get("/users")
async def users(
    q: str = Query(default="", max_length=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(User)
    if q:
        stmt = stmt.where(User.username.ilike("%" + q + "%"))
    rows = (
        await db.scalars(
            stmt.order_by(User.created_at.desc(), User.id).limit(50).offset(offset)
        )
    ).all()
    return [
        {**UserResponse.model_validate(u).model_dump(), "is_disabled": u.is_disabled}
        for u in rows
    ]


class UserAction(BaseModel):
    disabled: bool


@router.patch("/users/{uid}")
async def status(
    uid: UUID,
    payload: UserAction,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    target = await db.scalar(select(User).where(User.id == uid).with_for_update())
    if not target:
        raise HTTPException(404, "User not found")
    if target.is_admin:
        raise HTTPException(403, "Administrator accounts cannot be suspended here.")
    target.is_disabled = payload.disabled
    if payload.disabled:
        await db.execute(delete(AuthSession).where(AuthSession.user_id == uid))
    await db.commit()
    return {"detail": "Account updated"}


@router.get("/reports")
async def reports(
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(Report, Message)
            .join(Message, Message.id == Report.message_id)
            .where(Report.status == "open")
            .order_by(Report.created_at)
            .limit(50)
            .offset(offset)
        )
    ).all()
    return [
        {
            "id": r.id,
            "reason": r.reason,
            "created_at": r.created_at,
            "content": m.content,
            "message_id": m.id,
        }
        for r, m in rows
    ]


class Resolve(BaseModel):
    action: str


@router.post("/reports/{rid}/resolve", status_code=204)
async def resolve(
    rid: UUID,
    payload: Resolve,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if payload.action not in {"dismiss", "delete"}:
        raise HTTPException(422, "Invalid moderation action")
    report = await db.get(Report, rid)
    if not report:
        raise HTTPException(404, "Report not found")
    report.status = "resolved"
    if payload.action == "delete":
        item = await db.get(Message, report.message_id)
        item.content = "Message removed by moderation"
        item.media_url = None
        item.deleted_at = datetime.now(timezone.utc)
        await db.execute(
            text("SELECT pg_notify('coffeenchat_messages',:id)"), {"id": str(item.id)}
        )
    await db.commit()
