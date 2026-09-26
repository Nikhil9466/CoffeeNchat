# app/routes/conversation_router.py

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models.message_model import Message
from app.models.user_model import User
from app.schema.conversation_schema import (
    AddParticipantRequest,
    ConversationCreate,
    ConversationResponse,
    GroupCreate,
    GroupUpdate,
    ParticipantResponse,
)
from app.schema.message_schema import MessageCreate, MessageResponse
from app.services.conversation_service import (
    add_participant_to_group,
    create_group_conversation,
    create_or_get_conversation as create_or_get_conversation_service,
    delete_group_conversation,
    get_user_conversations as get_user_conversations_service,
    promote_participant_to_admin,
    remove_participant_or_leave,
)
from app.services.chat_service import is_user_in_conversation, save_message
from app.services.jwt_service import get_current_user
from app.services.conversation_service import (
    update_group_info,
    get_conversation_details,
)

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.post(
    "", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED
)
async def get_or_create_conversation(
    payload: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ensures a conversation exists for the current user and participants."""
    return await create_or_get_conversation_service(db, current_user.id, payload)


@router.get("", response_model=list[ConversationResponse])
async def get_user_conversations(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetches all active conversations for the authenticated user."""
    return await get_user_conversations_service(db, current_user.id, limit, offset)


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_conversation_messages(
    conversation_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    before: UUID | None = None,
    q: str = Query(default="", max_length=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not await is_user_in_conversation(db, current_user.id, conversation_id):
        raise HTTPException(403, "You do not have access to this conversation.")
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .options(selectinload(Message.sender))
    )
    if before:
        anchor = await db.get(Message, before)
        if not anchor or anchor.conversation_id != conversation_id:
            raise HTTPException(400, "Invalid history cursor.")
        from sqlalchemy import tuple_

        stmt = stmt.where(
            tuple_(Message.created_at, Message.id)
            < tuple_(anchor.created_at, anchor.id)
        )
    if q:
        stmt = stmt.where(
            Message.deleted_at.is_(None),
            Message.content.ilike(
                "%" + q.replace("%", "\\%").replace("_", "\\_") + "%"
            ),
        )
    rows = (
        await db.scalars(
            stmt.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit)
        )
    ).all()
    return list(reversed(rows))


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation_message(
    conversation_id: UUID,
    payload: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.conversation_id != conversation_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversation ID does not match the request path",
        )

    if not await is_user_in_conversation(db, current_user.id, conversation_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a participant in this conversation",
        )

    return await save_message(db, current_user.id, payload)


@router.post(
    "/group", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED
)
async def create_group_endpoint(
    payload: GroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Creates a new group conversation with current_user as admin."""
    return await create_group_conversation(db, current_user.id, payload)


@router.post(
    "/{conversation_id}/participants",
    response_model=ParticipantResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_member_endpoint(
    conversation_id: UUID,
    payload: AddParticipantRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Allows active group members to invite or add another user."""
    return await add_participant_to_group(
        db, conversation_id, current_user.id, payload.user_id
    )


@router.delete(
    "/{conversation_id}/participants/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_or_leave_endpoint(
    conversation_id: UUID,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Allows members to leave or admins to kick participants."""
    await remove_participant_or_leave(db, conversation_id, current_user.id, user_id)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group_endpoint(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deletes an entire group conversation (Admin only)."""
    await delete_group_conversation(db, conversation_id, current_user.id)


@router.patch(
    "/{conversation_id}/participants/{user_id}/promote",
    response_model=ParticipantResponse,
)
async def promote_member_endpoint(
    conversation_id: UUID,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Promotes a group member to an admin role (Admin only)."""
    return await promote_participant_to_admin(
        db, conversation_id, current_user.id, user_id
    )


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_group_details(
    conversation_id: UUID,
    payload: GroupUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await update_group_info(
        db=db,
        conversation_id=conversation_id,
        requestor_id=current_user.id,
        payload=payload,
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation_info(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns group details, picture, and full member list with roles."""
    return await get_conversation_details(db, conversation_id, current_user.id)
