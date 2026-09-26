import json
from uuid import UUID
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, text, func
from sqlalchemy.orm import selectinload
from app.models.conversation_model import ConversationParticipant as CP
from app.models.message_model import Message
from app.models.feature_model import Attachment
from app.schema.message_schema import MessageCreate, MessageResponse
from app.services.conversation_service import lock_conversation


async def is_user_in_conversation(db, user_id, conversation_id):
    return await db.get(CP, (conversation_id, user_id)) is not None


async def save_message(db, sender_id, message_data):
    await lock_conversation(db, message_data.conversation_id)
    if not await is_user_in_conversation(db, sender_id, message_data.conversation_id):
        raise HTTPException(403, "Conversation access was removed.")
    if message_data.client_id:
        await db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
            {"key": str(sender_id) + str(message_data.client_id)},
        )
        old = await db.scalar(
            select(Message)
            .where(
                Message.sender_id == sender_id,
                Message.client_id == message_data.client_id,
            )
            .options(selectinload(Message.sender))
        )
        if old:
            if (
                old.conversation_id != message_data.conversation_id
                or old.content != message_data.content
                or old.media_url != message_data.media_url
            ):
                raise HTTPException(
                    409, "Message ID was already used for different content."
                )
            return old
    if message_data.media_url:
        try:
            aid = UUID(message_data.media_url.removeprefix("/attachments/"))
            attachment = await db.get(Attachment, aid)
        except ValueError:
            attachment = None
        if not attachment or attachment.conversation_id != message_data.conversation_id:
            raise HTTPException(
                422, "Attachment is not available in this conversation."
            )
        message_data.media_url = "/attachments/" + str(attachment.id)
    item = Message(
        conversation_id=message_data.conversation_id,
        sender_id=sender_id,
        content=message_data.content,
        media_url=message_data.media_url,
        client_id=message_data.client_id,
        created_at=await db.scalar(select(func.clock_timestamp())),
    )
    db.add(item)
    await db.flush()
    await db.execute(
        text("SELECT pg_notify('coffeenchat_messages', :id)"), {"id": str(item.id)}
    )
    await db.commit()
    return await db.scalar(
        select(Message)
        .where(Message.id == item.id)
        .options(selectinload(Message.sender))
    )


async def get_conversation_participant_ids(db, conversation_id):
    return list(
        (
            await db.scalars(
                select(CP.user_id).where(CP.conversation_id == conversation_id)
            )
        ).all()
    )


def parse_and_validate_message(raw_data):
    try:
        return MessageCreate.model_validate_json(raw_data)
    except ValidationError:
        raise ValueError(
            "Invalid message. Check conversation ID and content (maximum 10,000 characters)."
        )


def build_error_payload(code, message, detail=None):
    return json.dumps({"type": "error", "code": code, "detail": message})


def serialize_message_response(message):
    return MessageResponse.model_validate(message).model_dump_json()
