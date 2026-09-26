import json, os, secrets, hashlib, smtplib, logging
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Query,
    BackgroundTasks,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import select, delete, text, func
from sqlalchemy.orm import selectinload
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool
from app.db import get_db
from app.config import UPLOAD_DIR, MAX_UPLOAD_BYTES
from app.models.feature_model import Attachment, SavedMessage, Report, PasswordReset
from app.models.message_model import Message
from app.models.user_model import User
from app.models.session_model import AuthSession
from app.models.conversation_model import ConversationParticipant as CP
from app.schema.message_schema import MessageResponse
from app.schema.user_schema import UserCreate
from app.services.jwt_service import get_current_user
from app.services.security import hash_password
from app.services.conversation_service import membership, lock_conversation

router = APIRouter(tags=["Workspace"])


@router.post("/conversations/{cid}/attachments", status_code=201)
async def upload(
    cid: UUID,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await membership(db, cid, user.id)
    # Opaque filenames and attachment disposition prevent uploaded HTML/SVG execution.
    aid = uuid4()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_DIR / str(aid)
    size = 0
    try:
        with path.open("xb") as stream:
            while chunk := await file.read(65536):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "Maximum attachment size is 10 MB.")
                await run_in_threadpool(stream.write, chunk)
        if size == 0:
            raise HTTPException(422, "Attachment is empty.")
        name = (file.filename or "attachment").replace("\\", "/").split("/")[-1][:255]
        item = Attachment(
            id=aid,
            conversation_id=cid,
            owner_id=user.id,
            filename=name,
            content_type="application/octet-stream",
        )
        await lock_conversation(db, cid)
        await membership(db, cid, user.id)
        db.add(item)
        await db.commit()
        return {
            "id": str(aid),
            "url": "/attachments/" + str(aid),
            "filename": name,
            "size": size,
        }
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


@router.get("/attachments/{aid}")
async def download(
    aid: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(Attachment, aid)
    if not item:
        raise HTTPException(404, "Attachment not found.")
    await membership(db, item.conversation_id, user.id)
    path = UPLOAD_DIR / str(aid)
    if not path.is_file():
        raise HTTPException(404, "Attachment not found.")
    return FileResponse(
        path,
        filename=item.filename,
        media_type="application/octet-stream",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/conversations/{cid}/files")
async def files(
    cid: UUID,
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await membership(db, cid, user.id)
    rows = (
        await db.scalars(
            select(Attachment)
            .where(Attachment.conversation_id == cid)
            .order_by(Attachment.created_at.desc())
            .limit(50)
            .offset(offset)
        )
    ).all()
    return [
        {
            "id": r.id,
            "filename": r.filename,
            "url": "/attachments/" + str(r.id),
            "created_at": r.created_at,
        }
        for r in rows
    ]


class ReadInput(BaseModel):
    last_message_id: UUID


@router.post("/conversations/{cid}/read", status_code=204)
async def read(
    cid: UUID,
    payload: ReadInput,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, member = await membership(db, cid, user.id)
    message = await db.get(Message, payload.last_message_id)
    if not message or message.conversation_id != cid:
        raise HTTPException(400, "Invalid read cursor")
    if member.last_read_at and member.last_read_at >= message.created_at:
        return
    member.last_read_at = message.created_at
    await db.execute(
        text("SELECT pg_notify('coffeenchat_events',:event)"),
        {
            "event": json.dumps(
                {
                    "type": "read",
                    "conversation_id": str(cid),
                    "user_id": str(user.id),
                    "at": member.last_read_at.isoformat(),
                }
            )
        },
    )
    await db.commit()


@router.get("/inbox")
async def inbox(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Lateral lookup uses the conversation/time index; unread excludes own messages.
    rows = (
        (
            await db.execute(
                text("""SELECT c.id, m.content, m.created_at AS last_message_at, m.media_url,
        (SELECT count(*) FROM messages u WHERE u.conversation_id=c.id AND u.sender_id<>:uid AND u.deleted_at IS NULL AND (cp.last_read_at IS NULL OR u.created_at>cp.last_read_at)) AS unread
        FROM conversations c JOIN conversation_participants cp ON cp.conversation_id=c.id AND cp.user_id=:uid
        LEFT JOIN LATERAL (SELECT content,created_at,media_url FROM messages WHERE conversation_id=c.id ORDER BY created_at DESC,id DESC LIMIT 1) m ON true
        ORDER BY COALESCE(m.created_at,c.created_at) DESC,c.id LIMIT :limit OFFSET :offset"""),
                {"uid": user.id, "limit": limit, "offset": offset},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


@router.get("/saved", response_model=list[MessageResponse])
async def saved(
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return (
        await db.scalars(
            select(Message)
            .join(SavedMessage, SavedMessage.message_id == Message.id)
            .join(CP, CP.conversation_id == Message.conversation_id)
            .where(SavedMessage.user_id == user.id, CP.user_id == user.id)
            .options(selectinload(Message.sender))
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(50)
            .offset(offset)
        )
    ).all()


@router.put("/messages/{mid}/saved", status_code=204)
async def save(
    mid: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(Message, mid)
    if not item:
        raise HTTPException(404, "Message not found")
    await membership(db, item.conversation_id, user.id)
    await db.execute(
        insert(SavedMessage)
        .values(user_id=user.id, message_id=mid)
        .on_conflict_do_nothing()
    )
    await db.commit()


@router.delete("/messages/{mid}/saved", status_code=204)
async def unsave(
    mid: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        delete(SavedMessage).where(
            SavedMessage.user_id == user.id, SavedMessage.message_id == mid
        )
    )
    await db.commit()


class ReportInput(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


@router.post("/messages/{mid}/report", status_code=201)
async def report(
    mid: UUID,
    payload: ReportInput,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(Message, mid)
    if not item:
        raise HTTPException(404, "Message not found")
    await membership(db, item.conversation_id, user.id)
    await db.execute(
        insert(Report)
        .values(
            id=uuid4(),
            message_id=mid,
            reporter_id=user.id,
            reason=payload.reason,
            status="open",
        )
        .on_conflict_do_nothing()
    )
    await db.commit()
    return {"detail": "Report received."}


@router.delete("/messages/{mid}", status_code=204)
async def delete_message(
    mid: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(Message, mid)
    if not item:
        raise HTTPException(404, "Message not found")
    await lock_conversation(db, item.conversation_id)
    await membership(db, item.conversation_id, user.id)
    if item.sender_id != user.id:
        raise HTTPException(403, "You can only delete your own messages.")
    item.content = "Message deleted"
    item.media_url = None
    item.deleted_at = datetime.now(timezone.utc)
    await db.execute(
        text("SELECT pg_notify('coffeenchat_messages',:id)"), {"id": str(mid)}
    )
    await db.commit()


class ResetRequest(BaseModel):
    email: EmailStr


class ResetConfirm(BaseModel):
    token: str = Field(min_length=32, max_length=128)
    password: str = Field(min_length=10, max_length=72)


@router.get("/auth/capabilities")
async def capabilities():
    return {"password_reset": bool(os.getenv("SMTP_HOST"))}


@router.post("/auth/forgot-password")
async def forgot(
    payload: ResetRequest, tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)
):
    if not os.getenv("SMTP_HOST"):
        raise HTTPException(
            503, "Email recovery is not configured. Contact your administrator."
        )
    user = await db.scalar(
        select(User).where(
            func.lower(User.email) == str(payload.email).lower(),
            User.is_disabled.is_(False),
        )
    )
    if user:
        token = secrets.token_urlsafe(32)
        await db.execute(delete(PasswordReset).where(PasswordReset.user_id == user.id))
        db.add(
            PasswordReset(
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                user_id=user.id,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            )
        )
        await db.commit()
        msg = EmailMessage()
        msg["Subject"] = "Reset your CoffeeNchat password"
        msg["From"] = os.environ["SMTP_FROM"]
        msg["To"] = user.email
        msg.set_content(
            os.environ["PUBLIC_FRONTEND_URL"].rstrip("/")
            + "/reset-password#"
            + token
            + "\nThis link expires in 15 minutes."
        )

        def send():
            with smtplib.SMTP(
                os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587")), timeout=15
            ) as smtp:
                smtp.starttls()
                if os.getenv("SMTP_USER"):
                    smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
                smtp.send_message(msg)

        def deliver():
            try:
                send()
            except Exception as exc:
                logging.getLogger(__name__).error(
                    "Password reset delivery failed (%s)", type(exc).__name__
                )

        tasks.add_task(deliver)
    return {"detail": "If the account exists, a reset link has been sent."}


@router.post("/auth/reset-password", status_code=204)
async def reset(payload: ResetConfirm, db: AsyncSession = Depends(get_db)):
    try:
        UserCreate.password_bytes(payload.password)
    except ValueError:
        raise HTTPException(422, "Password exceeds 72 UTF-8 bytes.")
    digest = hashlib.sha256(payload.token.encode()).hexdigest()
    reset = await db.scalar(
        select(PasswordReset)
        .where(PasswordReset.token_hash == digest)
        .with_for_update()
    )
    if not reset or reset.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(400, "Reset link is invalid or expired.")
    user = await db.scalar(
        select(User).where(User.id == reset.user_id).with_for_update()
    )
    user.password_hash = await run_in_threadpool(hash_password, payload.password)
    await db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    await db.delete(reset)
    await db.commit()
