import json
from fastapi import HTTPException
from sqlalchemy import select, func, text, delete
from sqlalchemy.orm import selectinload
from app.models.conversation_model import Conversation, ConversationParticipant as CP
from app.models.user_model import User
from app.models.message_model import Message
from app.schema.conversation_schema import ConversationCreate, GroupCreate, GroupUpdate


async def lock_conversation(db, conversation_id):
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": str(conversation_id)},
    )


async def notify_change(db, conversation_id, extra_ids=()):
    ids = set(
        (
            await db.scalars(
                select(CP.user_id).where(CP.conversation_id == conversation_id)
            )
        ).all()
    ) | set(extra_ids)
    event = json.dumps(
        {
            "type": "conversation",
            "conversation_id": str(conversation_id),
            "recipients": [str(x) for x in ids],
        }
    )
    await db.execute(
        text("SELECT pg_notify('coffeenchat_events',:event)"), {"event": event}
    )


async def membership(db, conversation_id, user_id, admin=False, group=False):
    conv = await db.get(Conversation, conversation_id)
    member = await db.get(CP, (conversation_id, user_id))
    if not conv or not member:
        raise HTTPException(403, "You do not have access to this conversation.")
    if group and not conv.is_group:
        raise HTTPException(400, "Direct conversations cannot change membership.")
    if admin and member.role != "admin":
        raise HTTPException(403, "Only group administrators can do this.")
    return conv, member


async def get_conversation_details(db, conversation_id, current_user_id):
    await membership(db, conversation_id, current_user_id)
    return await db.scalar(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.participants).selectinload(CP.user))
        .execution_options(populate_existing=True)
    )


async def check_users(db, ids):
    if len(ids) > 100:
        raise HTTPException(422, "Groups support up to 100 participants.")
    existing = set(
        (
            await db.scalars(
                select(User.id).where(User.id.in_(ids), User.is_disabled.is_(False))
            )
        ).all()
    )
    if existing != set(ids):
        raise HTTPException(404, "One or more users are unavailable.")


async def create_or_get_conversation(db, current_user_id, payload: ConversationCreate):
    if payload.is_group:
        raise HTTPException(422, "Create groups through the group endpoint.")
    peers = set(payload.participant_ids) - {current_user_id}
    if len(peers) != 1:
        raise HTTPException(
            422, "A direct conversation requires exactly one other person."
        )
    ids = peers | {current_user_id}
    await check_users(db, ids)
    key = ":".join(sorted(str(x) for x in ids))
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key}
    )
    conv = await db.scalar(select(Conversation).where(Conversation.direct_key == key))
    if not conv:
        # Reuse only legacy conversations whose complete membership is the exact pair.
        matches = (
            await db.scalars(
                select(Conversation)
                .where(Conversation.is_group.is_(False))
                .join(CP)
                .where(CP.user_id == current_user_id)
                .options(selectinload(Conversation.participants))
            )
        ).all()
        conv = next(
            (c for c in matches if {m.user_id for m in c.participants} == ids), None
        )
        if conv:
            conv.direct_key = key
        else:
            conv = Conversation(is_group=False, direct_key=key)
            db.add(conv)
            await db.flush()
            for uid in ids:
                db.add(CP(conversation_id=conv.id, user_id=uid, role="member"))
        await db.flush()
        await notify_change(db, conv.id)
        await db.commit()
    return await get_conversation_details(db, conv.id, current_user_id)


async def create_group_conversation(db, creator_id, payload: GroupCreate):
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, "Group name is required.")
    ids = set(payload.participant_ids) | {creator_id}
    await check_users(db, ids)
    conv = Conversation(is_group=True, name=name)
    db.add(conv)
    await db.flush()
    for uid in ids:
        db.add(
            CP(
                conversation_id=conv.id,
                user_id=uid,
                role="admin" if uid == creator_id else "member",
            )
        )
    await db.flush()
    await notify_change(db, conv.id)
    await db.commit()
    return await get_conversation_details(db, conv.id, creator_id)


async def get_user_conversations(db, current_user_id, limit=50, offset=0):
    latest = (
        select(func.max(Message.created_at))
        .where(Message.conversation_id == Conversation.id)
        .correlate(Conversation)
        .scalar_subquery()
    )
    return (
        await db.scalars(
            select(Conversation)
            .join(CP)
            .where(CP.user_id == current_user_id)
            .options(selectinload(Conversation.participants).selectinload(CP.user))
            .order_by(
                func.coalesce(latest, Conversation.created_at).desc(), Conversation.id
            )
            .limit(limit)
            .offset(offset)
        )
    ).all()


async def add_participant_to_group(db, conversation_id, requestor_id, new_user_id):
    await lock_conversation(db, conversation_id)
    await membership(db, conversation_id, requestor_id, admin=True, group=True)
    await check_users(db, {new_user_id})
    member = await db.get(CP, (conversation_id, new_user_id))
    if not member:
        count = await db.scalar(
            select(func.count())
            .select_from(CP)
            .where(CP.conversation_id == conversation_id)
        )
        if count >= 100:
            raise HTTPException(422, "This group has reached its 100-member limit.")
        db.add(CP(conversation_id=conversation_id, user_id=new_user_id, role="member"))
    await db.flush()
    await notify_change(db, conversation_id)
    await db.commit()
    return await db.scalar(
        select(CP)
        .where(CP.conversation_id == conversation_id, CP.user_id == new_user_id)
        .options(selectinload(CP.user))
    )


async def assert_can_leave(db, conversation_id, user_id):
    await lock_conversation(db, conversation_id)
    member = await db.get(CP, (conversation_id, user_id))
    if member and member.role == "admin":
        members = (
            await db.scalars(select(CP).where(CP.conversation_id == conversation_id))
        ).all()
        if len(members) > 1 and not any(
            m.user_id != user_id and m.role == "admin" for m in members
        ):
            raise HTTPException(
                409,
                "Promote another administrator before leaving or deleting your account.",
            )


async def remove_participant_or_leave(
    db, conversation_id, requestor_id, target_user_id
):
    await lock_conversation(db, conversation_id)
    await membership(
        db,
        conversation_id,
        requestor_id,
        admin=requestor_id != target_user_id,
        group=True,
    )
    if not await db.get(CP, (conversation_id, target_user_id)):
        raise HTTPException(404, "Member not found.")
    await assert_can_leave(db, conversation_id, target_user_id)
    await db.execute(
        delete(CP).where(
            CP.conversation_id == conversation_id, CP.user_id == target_user_id
        )
    )
    await notify_change(db, conversation_id, [target_user_id])
    remaining = await db.scalar(
        select(func.count())
        .select_from(CP)
        .where(CP.conversation_id == conversation_id)
    )
    if not remaining:
        await db.execute(delete(Conversation).where(Conversation.id == conversation_id))
    await db.commit()


async def delete_group_conversation(db, conversation_id, requestor_id):
    await lock_conversation(db, conversation_id)
    await membership(db, conversation_id, requestor_id, admin=True, group=True)
    await notify_change(db, conversation_id)
    await db.execute(delete(Conversation).where(Conversation.id == conversation_id))
    await db.commit()


async def promote_participant_to_admin(
    db, conversation_id, requestor_id, target_user_id
):
    await lock_conversation(db, conversation_id)
    await membership(db, conversation_id, requestor_id, admin=True, group=True)
    member = await db.get(CP, (conversation_id, target_user_id))
    if not member:
        raise HTTPException(404, "Member not found.")
    member.role = "admin"
    await notify_change(db, conversation_id)
    await db.commit()
    return await db.scalar(
        select(CP)
        .where(CP.conversation_id == conversation_id, CP.user_id == target_user_id)
        .options(selectinload(CP.user))
    )


async def update_group_info(db, conversation_id, requestor_id, payload: GroupUpdate):
    await lock_conversation(db, conversation_id)
    conv, _ = await membership(
        db, conversation_id, requestor_id, admin=True, group=True
    )
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(422, "Group name is required.")
        conv.name = name
    await notify_change(db, conversation_id)
    await db.commit()
    return await get_conversation_details(db, conversation_id, requestor_id)
