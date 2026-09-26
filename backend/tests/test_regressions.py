"""Fast regressions; no database connection is made by these tests."""

import os
import unittest
from uuid import uuid4
from unittest.mock import AsyncMock

os.environ.setdefault(
    "SQLALCHEMY_DATABASE_URL", "postgresql://test@127.0.0.1/nagender_test"
)
os.environ.setdefault("JWT_SECRET_KEY", "unit-test-only-key-never-use-in-production")

from app.controllers.chat_controller import ChatController
from app.services.chat_service import parse_and_validate_message
from app.services.security import hash_password, verify_password


class ChatConnections(unittest.IsolatedAsyncioTestCase):
    async def test_both_tabs_receive(self):
        controller = ChatController()
        uid = uuid4()
        a, b = AsyncMock(), AsyncMock()
        await controller.connect(uid, a)
        await controller.connect(uid, b)
        await controller.broadcast_to_conversation([uid, uid], "hello")
        a.send_text.assert_awaited_once_with("hello")
        b.send_text.assert_awaited_once_with("hello")

    async def test_old_tab_disconnect_preserves_new_tab(self):
        controller = ChatController()
        uid = uuid4()
        a, b = AsyncMock(), AsyncMock()
        await controller.connect(uid, a)
        await controller.connect(uid, b)
        controller.disconnect(uid, a)
        await controller.broadcast_to_conversation([uid], "hello")
        a.send_text.assert_not_awaited()
        b.send_text.assert_awaited_once_with("hello")

    async def test_failed_socket_does_not_remove_other_tab(self):
        controller = ChatController()
        uid = uuid4()
        a, b = AsyncMock(), AsyncMock()
        a.send_text.side_effect = RuntimeError("closed")
        await controller.connect(uid, a)
        await controller.connect(uid, b)
        await controller.broadcast_to_conversation([uid], "hello")
        self.assertEqual(controller.active_connections[uid], {b})
        controller.disconnect(uid, b)
        self.assertNotIn(uid, controller.active_connections)


class Validation(unittest.TestCase):
    def test_non_object_messages_are_controlled_errors(self):
        for raw in ("[]", "null", "1", '"text"', "{invalid"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_and_validate_message(raw)

    def test_valid_message(self):
        uid = uuid4()
        result = parse_and_validate_message(
            '{"conversation_id":"%s","content":"hello"}' % uid
        )
        self.assertEqual(result.conversation_id, uid)

    def test_password_round_trip(self):
        hashed = hash_password("TestPass123!")
        self.assertTrue(verify_password("TestPass123!", hashed))
        self.assertFalse(verify_password("wrong", hashed))

    def test_oversized_password_returns_false_on_login(self):
        self.assertFalse(verify_password("A" * 80, "unused"))

    def test_hash_limit_is_bytes_not_characters(self):
        with self.assertRaises(ValueError):
            hash_password("é" * 37)


if __name__ == "__main__":
    unittest.main()
