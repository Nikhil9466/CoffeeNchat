import asyncio
import logging
from uuid import UUID
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ChatController:
    def __init__(self):
        self.active_connections: dict[UUID, set[WebSocket]] = {}
        self.locks = {}
        self.tokens = {}

    async def connect(self, user_id, websocket, token=None):
        if len(self.active_connections.get(user_id, ())) >= 10:
            await websocket.close(code=1008)
            return False
        await websocket.accept()
        self.active_connections.setdefault(user_id, set()).add(websocket)
        self.locks[websocket] = asyncio.Lock()
        if token:
            self.tokens[websocket] = token
        return True

    def disconnect(self, user_id, websocket):
        sockets = self.active_connections.get(user_id)
        if sockets is not None:
            sockets.discard(websocket)
            if not sockets:
                self.active_connections.pop(user_id, None)
        self.tokens.pop(websocket, None)
        self.locks.pop(websocket, None)

    async def send(self, user_id, socket, payload):
        try:
            async with self.locks[socket]:
                if socket in self.tokens:
                    from app.services.jwt_service import validate_token

                    if await validate_token(self.tokens[socket]) != user_id:
                        await socket.close(code=1008)
                        self.disconnect(user_id, socket)
                        return
                await asyncio.wait_for(socket.send_text(payload), timeout=5)
        except Exception:
            self.disconnect(user_id, socket)
            try:
                await socket.close(code=1013)
            except Exception:
                pass

    async def broadcast_to_conversation(self, participant_ids, message_json):
        await asyncio.gather(
            *(
                self.send(uid, s, message_json)
                for uid in set(participant_ids)
                for s in tuple(self.active_connections.get(uid, ()))
            )
        )


chat_controller = ChatController()
