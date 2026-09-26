import asyncio, json, time
from uuid import UUID
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from sqlalchemy import text
from app.config import ORIGINS
from app.controllers.chat_controller import chat_controller
from app.db import AsyncSessionLocal
from app.services.jwt_service import validate_token
from app.services.chat_service import (
    parse_and_validate_message,
    save_message,
    is_user_in_conversation,
)

router = APIRouter(prefix="/ws", tags=["Chat"])


@router.websocket("/chat")
async def chat(socket: WebSocket):
    if socket.headers.get("origin", "").rstrip("/") not in ORIGINS:
        await socket.close(code=1008)
        return
    token = socket.cookies.get("access_token", "")
    uid = await validate_token(token)
    if not uid:
        await socket.close(code=1008)
        return
    if not await chat_controller.connect(uid, socket, token):
        return
    timestamps = []
    try:
        while True:
            if await validate_token(token) != uid:
                await socket.close(code=1008)
                break
            try:
                raw = await asyncio.wait_for(socket.receive_text(), timeout=3)
            except asyncio.TimeoutError:
                continue
            if await validate_token(token) != uid:
                await socket.close(code=1008)
                break
            if len(raw) > 45000:
                await socket.close(code=1009)
                break
            now = time.monotonic()
            timestamps = [t for t in timestamps if now - t < 10]
            if len(timestamps) >= 30:
                await chat_controller.send(
                    uid,
                    socket,
                    json.dumps({"type": "error", "detail": "Please slow down."}),
                )
                continue
            timestamps.append(now)
            try:
                data = json.loads(raw)
                async with AsyncSessionLocal() as db:
                    if isinstance(data, dict) and data.get("type") == "typing":
                        cid = UUID(data["conversation_id"])
                        if not await is_user_in_conversation(db, uid, cid):
                            raise HTTPException(403, "Conversation access denied")
                        event = json.dumps(
                            {
                                "type": "typing",
                                "conversation_id": str(cid),
                                "user_id": str(uid),
                            }
                        )
                        await db.execute(
                            text("SELECT pg_notify('coffeenchat_events',:event)"),
                            {"event": event},
                        )
                        await db.commit()
                    else:
                        item = await save_message(
                            db, uid, parse_and_validate_message(raw)
                        )
                        await chat_controller.send(
                            uid,
                            socket,
                            json.dumps(
                                {
                                    "type": "ack",
                                    "id": str(item.id),
                                    "client_id": str(item.client_id)
                                    if item.client_id
                                    else None,
                                }
                            ),
                        )
            except (ValueError, KeyError, HTTPException) as exc:
                await chat_controller.send(
                    uid,
                    socket,
                    json.dumps(
                        {
                            "type": "error",
                            "detail": exc.detail
                            if isinstance(exc, HTTPException)
                            else "Invalid message.",
                        }
                    ),
                )
            except Exception:
                await chat_controller.send(
                    uid,
                    socket,
                    json.dumps(
                        {
                            "type": "error",
                            "detail": "Unable to save message. Retry with the same client ID.",
                        }
                    ),
                )
    except WebSocketDisconnect:
        pass
    finally:
        chat_controller.disconnect(uid, socket)
