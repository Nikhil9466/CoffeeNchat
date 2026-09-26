"""Bounded, ordered delivery; clients recover from persisted history after gaps."""

import asyncio, json, logging
from uuid import UUID
import asyncpg
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.controllers.chat_controller import chat_controller
from app.db.connection import DATABASE_URL, AsyncSessionLocal
from app.models.message_model import Message
from app.services.chat_service import (
    get_conversation_participant_ids,
    serialize_message_response,
)

logger = logging.getLogger(__name__)


class ChatBroker:
    def __init__(self):
        self.connection = None
        self.monitor = None
        self.consumer = None
        self.queue = asyncio.Queue(maxsize=2000)

    async def _connect(self):
        self.connection = await asyncpg.connect(
            DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1),
            server_settings={"application_name": "coffeenchat-listener"},
        )
        await self.connection.add_listener("coffeenchat_messages", self._notification)
        await self.connection.add_listener("coffeenchat_events", self._notification)

    def _notification(self, connection, pid, channel, payload):
        try:
            self.queue.put_nowait((channel, payload))
        except asyncio.QueueFull:
            # A resync marker replaces one event; authoritative data remains in PostgreSQL.
            self.queue.get_nowait()
            self.queue.task_done()
            self.queue.put_nowait(("resync", ""))

    async def _consume(self):
        while True:
            channel, payload = await self.queue.get()
            try:
                if channel == "resync":
                    await chat_controller.broadcast_to_conversation(
                        list(chat_controller.active_connections),
                        json.dumps({"type": "resync"}),
                    )
                    continue
                async with AsyncSessionLocal() as db:
                    if channel == "coffeenchat_events":
                        data = json.loads(payload)
                        ids = (
                            [UUID(x) for x in data.pop("recipients", [])]
                            if data.get("type") == "conversation"
                            else await get_conversation_participant_ids(
                                db, UUID(data["conversation_id"])
                            )
                        )
                        message = json.dumps(data)
                    else:
                        item = await db.scalar(
                            select(Message)
                            .where(Message.id == UUID(payload))
                            .options(selectinload(Message.sender))
                        )
                        if item is None:
                            continue
                        ids = await get_conversation_participant_ids(
                            db, item.conversation_id
                        )
                        message = json.dumps(
                            {
                                "type": "message",
                                "message": json.loads(serialize_message_response(item)),
                            }
                        )
                await chat_controller.broadcast_to_conversation(ids, message)
            except Exception:
                logger.error(
                    "Chat event delivery failed; client history recovery required"
                )
            finally:
                self.queue.task_done()

    async def start(self):
        await self._connect()
        self.consumer = asyncio.create_task(self._consume())
        self.monitor = asyncio.create_task(self._watch())

    async def _watch(self):
        while True:
            await asyncio.sleep(2)
            if self.connection.is_closed():
                try:
                    await self._connect()
                    await chat_controller.broadcast_to_conversation(
                        list(chat_controller.active_connections),
                        json.dumps({"type": "resync"}),
                    )
                except Exception:
                    logger.warning("Chat listener reconnect failed")

    async def stop(self):
        for task in [self.monitor, self.consumer]:
            if task:
                task.cancel()
        await asyncio.gather(
            *(t for t in [self.monitor, self.consumer] if t), return_exceptions=True
        )
        if self.connection:
            await self.connection.close()


chat_broker = ChatBroker()
