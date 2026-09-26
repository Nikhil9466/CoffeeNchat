"""Opt-in integration suite against an explicitly supplied disposable deployment."""

import asyncio
import json
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
import asyncpg
import httpx
from websockets.sync.client import connect
from websockets.exceptions import ConnectionClosed


@unittest.skipUnless(
    os.getenv("COFFEENCHAT_TEST_URL") and os.getenv("TEST_DATABASE_URL"),
    "Requires disposable integration environment",
)
class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = os.environ["COFFEENCHAT_TEST_URL"]
        cls.suffix = uuid.uuid4().hex[:10]
        cls.clients = []
        cls.users = []
        for name in ["Alice", "Bob", "Carla", "Admin"]:
            client = httpx.Client(base_url=cls.base, timeout=20)
            cls.clients.append(client)
            r = client.post(
                "/users/register",
                json={
                    "email": name.lower() + cls.suffix + "@example.com",
                    "username": name + cls.suffix,
                    "password": "TestPass123!",
                },
            )
            assert r.status_code == 201, r.text
            cls.users.append(r.json())
        cls.a, cls.b, cls.c, cls.admin = cls.clients

        async def promote():
            conn = await asyncpg.connect(os.environ["TEST_DATABASE_URL"])
            await conn.execute(
                "UPDATE users SET is_admin=true WHERE id=$1",
                uuid.UUID(cls.users[3]["id"]),
            )
            await conn.close()

        asyncio.run(promote())
        r = cls.a.post("/conversations", json={"participant_ids": [cls.users[1]["id"]]})
        assert r.status_code == 201, r.text
        cls.direct = r.json()["id"]
        r = cls.a.post(
            "/conversations/group",
            json={"name": "Integration group", "participant_ids": [cls.users[1]["id"]]},
        )
        assert r.status_code == 201, r.text
        cls.group = r.json()["id"]

    @classmethod
    def tearDownClass(cls):
        for c in cls.clients:
            c.close()

    def test_01_response_privacy_and_direct_boundary(self):
        r = self.a.post(
            f"/conversations/{self.group}/participants",
            json={"user_id": self.users[2]["id"]},
        )
        self.assertEqual(r.status_code, 201, r.text)
        self.assertNotIn("password_hash", r.text)
        self.assertNotIn("email", r.json()["user"])
        self.assertNotIn("is_admin", r.json()["user"])
        self.assertEqual(
            self.a.post(
                f"/conversations/{self.direct}/participants",
                json={"user_id": self.users[2]["id"]},
            ).status_code,
            400,
        )
        self.assertEqual(
            self.c.get(f"/conversations/{self.direct}/messages").status_code, 403
        )
        self.assertTrue(
            all(
                "email" not in u and "password_hash" not in u
                for u in self.a.get("/users").json()
            )
        )

    def test_02_domain_rules_and_concurrent_creation(self):
        for payload in [
            {"participant_ids": [self.users[0]["id"]]},
            {"participant_ids": [self.users[1]["id"], self.users[2]["id"]]},
            {"is_group": True, "participant_ids": [self.users[1]["id"]]},
        ]:
            self.assertEqual(
                self.a.post("/conversations", json=payload).status_code, 422
            )

        def create(_):
            return self.a.post(
                "/conversations", json={"participant_ids": [self.users[1]["id"]]}
            ).json()["id"]

        with ThreadPoolExecutor(max_workers=6) as pool:
            self.assertEqual(set(pool.map(create, range(12))), {self.direct})
        self.assertEqual(
            self.b.post(
                f"/conversations/{self.group}/participants",
                json={"user_id": self.users[2]["id"]},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.a.delete(
                f"/conversations/{self.group}/participants/{self.users[0]['id']}"
            ).status_code,
            409,
        )

    def test_03_history_retry_search_and_validation(self):
        ids = []
        for i in range(65):
            r = self.a.post(
                f"/conversations/{self.direct}/messages",
                json={
                    "conversation_id": self.direct,
                    "content": f"history-{self.suffix}-{i:03d}",
                    "client_id": str(uuid.uuid4()),
                },
            )
            self.assertEqual(r.status_code, 201, r.text)
            ids.append(r.json()["id"])
        recent = self.a.get(f"/conversations/{self.direct}/messages").json()
        self.assertEqual(len(recent), 50)
        self.assertEqual(recent[-1]["id"], ids[-1])
        self.assertEqual(recent[0]["id"], ids[15])
        older = self.a.get(
            f"/conversations/{self.direct}/messages", params={"before": recent[0]["id"]}
        ).json()
        self.assertEqual([m["id"] for m in older], ids[:15])
        found = self.a.get(
            f"/conversations/{self.direct}/messages",
            params={"q": f"history-{self.suffix}-064"},
        ).json()
        self.assertEqual(len(found), 1)
        payload = {
            "conversation_id": self.direct,
            "content": "retry once",
            "client_id": str(uuid.uuid4()),
        }
        with ThreadPoolExecutor(max_workers=5) as pool:
            responses = list(
                pool.map(
                    lambda _: self.a.post(
                        f"/conversations/{self.direct}/messages", json=payload
                    ),
                    range(5),
                )
            )
        self.assertTrue(all(r.status_code == 201 for r in responses))
        self.assertEqual(len({r.json()["id"] for r in responses}), 1)
        payload["content"] = "different"
        self.assertEqual(
            self.a.post(
                f"/conversations/{self.direct}/messages", json=payload
            ).status_code,
            409,
        )
        self.assertEqual(
            self.a.get(
                f"/conversations/{self.direct}/messages?limit=100000"
            ).status_code,
            422,
        )
        self.assertEqual(
            self.a.post(
                f"/conversations/{self.direct}/messages",
                json={"conversation_id": self.direct, "content": "   "},
            ).status_code,
            422,
        )
        secret = "a" * 129
        r = self.a.post(
            "/users/login", json={"email": "a@example.com", "password": secret}
        )
        self.assertEqual(r.status_code, 422)
        self.assertNotIn(secret, r.text)

    def test_04_files_saved_reports_and_admin_actions(self):
        r = self.a.post(
            f"/conversations/{self.direct}/attachments",
            files={"file": ("test.html", b"<script>alert(1)</script>", "text/html")},
        )
        self.assertEqual(r.status_code, 201, r.text)
        url = r.json()["url"]
        download = self.b.get(url)
        self.assertEqual(download.status_code, 200)
        self.assertIn("attachment", download.headers["content-disposition"])
        self.assertEqual(download.headers["content-type"], "application/octet-stream")
        self.assertEqual(self.c.get(url).status_code, 403)
        r = self.a.post(
            f"/conversations/{self.direct}/messages",
            json={
                "conversation_id": self.direct,
                "content": "test file",
                "media_url": url,
                "client_id": str(uuid.uuid4()),
            },
        )
        self.assertEqual(r.status_code, 201, r.text)
        mid = r.json()["id"]
        self.assertEqual(self.b.put(f"/messages/{mid}/saved").status_code, 204)
        self.assertIn(mid, [m["id"] for m in self.b.get("/saved").json()])
        self.assertEqual(
            self.b.post(
                f"/messages/{mid}/report",
                json={"reason": "Integration moderation test"},
            ).status_code,
            201,
        )
        self.assertEqual(self.a.get("/admin/reports").status_code, 403)
        rid = next(
            r["id"]
            for r in self.admin.get("/admin/reports").json()
            if r["message_id"] == mid
        )
        self.assertEqual(
            self.admin.post(
                f"/admin/reports/{rid}/resolve", json={"action": "delete"}
            ).status_code,
            204,
        )
        history = self.b.get(f"/conversations/{self.direct}/messages").json()
        self.assertTrue(next(m for m in history if m["id"] == mid)["deleted_at"])
        self.assertEqual(
            self.b.post(
                f"/conversations/{self.direct}/read", json={"last_message_id": mid}
            ).status_code,
            204,
        )
        self.assertEqual(
            next(
                c["unread"]
                for c in self.b.get("/inbox").json()
                if c["id"] == self.direct
            ),
            0,
        )
        self.assertEqual(self.admin.get("/admin/stats").status_code, 200)

    def test_05_socket_cross_worker_and_logout(self):
        other = os.getenv("COFFEENCHAT_SECOND_URL", self.base)
        wsurl = other.replace("http://", "ws://") + "/ws/chat"
        with connect(
            wsurl,
            origin="http://localhost:5173",
            additional_headers={
                "Cookie": "access_token=" + self.b.cookies.get("access_token")
            },
        ) as ws:
            r = self.a.post(
                f"/conversations/{self.direct}/messages",
                json={
                    "conversation_id": self.direct,
                    "content": "cross worker",
                    "client_id": str(uuid.uuid4()),
                },
            )
            self.assertEqual(r.status_code, 201)
            event = json.loads(ws.recv(timeout=10))
            self.assertEqual(event["type"], "message")
            self.assertEqual(event["message"]["id"], r.json()["id"])
            self.assertEqual(self.b.post("/users/logout").status_code, 204)
            with self.assertRaises(ConnectionClosed):
                ws.recv(timeout=8)
        self.assertEqual(self.b.get("/users/me").status_code, 401)
        r = self.b.post(
            "/users/login",
            json={"email": self.users[1]["email"], "password": "TestPass123!"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["id"], self.users[1]["id"])

    def test_06_origin_profile_and_sessions(self):
        self.assertEqual(
            self.a.post(
                "/users/logout", headers={"Origin": "https://attacker.example"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.a.put(
                "/users/" + self.users[1]["id"], json={"bio": "intrusion"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.a.put(
                "/users/" + self.users[0]["id"],
                json={"username": self.users[1]["username"]},
            ).status_code,
            409,
        )
        self.assertEqual(
            self.a.put(
                "/users/" + self.users[0]["id"], json={"bio": "Updated profile"}
            ).status_code,
            200,
        )
        self.assertTrue(any(s["current"] for s in self.a.get("/users/sessions").json()))
        self.assertEqual(
            self.a.post(
                "/users/password",
                json={"current_password": "wrong", "password": "NewTestPass123!"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.a.options(
                f"/conversations/{self.group}",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "PATCH",
                },
            ).status_code,
            200,
        )

    def test_07_deletion_retains_anonymous_history(self):
        cid = self.c.post(
            "/conversations", json={"participant_ids": [self.users[1]["id"]]}
        ).json()["id"]
        mid = self.c.post(
            f"/conversations/{cid}/messages",
            json={"conversation_id": cid, "content": "Retained history"},
        ).json()["id"]
        token = self.c.cookies.get("access_token")
        r = self.c.request(
            "DELETE",
            "/users/" + self.users[2]["id"],
            json={"current_password": "TestPass123!"},
        )
        self.assertEqual(r.status_code, 204, r.text)
        self.assertEqual(
            httpx.get(
                self.base + "/users/me", headers={"Cookie": "access_token=" + token}
            ).status_code,
            401,
        )
        item = next(
            m
            for m in self.b.get(f"/conversations/{cid}/messages").json()
            if m["id"] == mid
        )
        self.assertIsNone(item["sender_id"])
        self.assertIsNone(item["sender"])
        self.assertEqual(item["content"], "Retained history")

    def test_08_device_revocation_and_password_change(self):
        with httpx.Client(
            base_url=os.getenv("COFFEENCHAT_SECOND_URL", self.base)
        ) as device:
            self.assertEqual(
                device.post(
                    "/users/login",
                    json={"email": self.users[1]["email"], "password": "TestPass123!"},
                ).status_code,
                200,
            )
            sid = next(
                s["id"] for s in device.get("/users/sessions").json() if s["current"]
            )
            token = device.cookies.get("access_token")
            self.assertEqual(self.a.delete("/users/sessions/" + sid).status_code, 204)
            self.assertEqual(
                device.get("/users/me").status_code, 200
            )  # cannot revoke someone else's session
            self.assertEqual(self.b.delete("/users/sessions/" + sid).status_code, 204)
            self.assertEqual(device.get("/users/me").status_code, 401)
            self.assertEqual(
                self.b.post(
                    "/users/password",
                    json={
                        "current_password": "TestPass123!",
                        "password": "ChangedPass123!",
                    },
                ).status_code,
                204,
            )
            self.assertEqual(self.b.get("/users/me").status_code, 401)
            self.assertEqual(
                self.b.post(
                    "/users/login",
                    json={"email": self.users[1]["email"], "password": "TestPass123!"},
                ).status_code,
                401,
            )
            self.assertEqual(
                self.b.post(
                    "/users/login",
                    json={
                        "email": self.users[1]["email"],
                        "password": "ChangedPass123!",
                    },
                ).status_code,
                200,
            )
            self.assertEqual(
                device.get(
                    "/users/me", headers={"Authorization": "Bearer " + token}
                ).status_code,
                401,
            )

    def test_09_socket_validation_and_member_removal(self):
        cid = self.a.post(
            "/conversations/group",
            json={"name": "Membership race", "participant_ids": [self.users[1]["id"]]},
        ).json()["id"]
        token = self.b.cookies.get("access_token")
        other = os.getenv("COFFEENCHAT_SECOND_URL", self.base)
        with connect(
            other.replace("http", "ws", 1) + "/ws/chat",
            origin="http://localhost:5173",
            additional_headers={"Cookie": "access_token=" + token},
        ) as ws:
            for raw in ["[]", "null", "{invalid"]:
                ws.send(raw)
                self.assertEqual(json.loads(ws.recv(timeout=5))["type"], "error")
            self.assertEqual(
                self.a.delete(
                    f"/conversations/{cid}/participants/" + self.users[1]["id"]
                ).status_code,
                204,
            )
            event = json.loads(ws.recv(timeout=5))
            self.assertEqual(event["type"], "conversation")
            ws.send(
                json.dumps(
                    {"conversation_id": cid, "content": "forbidden after removal"}
                )
            )
            self.assertEqual(json.loads(ws.recv(timeout=5))["type"], "error")
            self.assertEqual(
                self.b.get(f"/conversations/{cid}/messages").status_code, 403
            )
        self.assertEqual(self.a.delete(f"/conversations/{cid}").status_code, 204)

    def test_10_concurrent_last_administrators(self):
        cid = self.a.post(
            "/conversations/group",
            json={
                "name": "Admin race",
                "participant_ids": [self.users[1]["id"], self.users[3]["id"]],
            },
        ).json()["id"]
        self.assertEqual(
            self.a.patch(
                f"/conversations/{cid}/participants/" + self.users[1]["id"] + "/promote"
            ).status_code,
            200,
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(
                pool.map(
                    lambda item: (
                        item[0]
                        .delete(f"/conversations/{cid}/participants/" + item[1])
                        .status_code
                    ),
                    [(self.a, self.users[0]["id"]), (self.b, self.users[1]["id"])],
                )
            )
        self.assertEqual(sorted(outcomes), [204, 409])
        members = self.admin.get("/conversations/" + cid).json()["participants"]
        self.assertEqual(sum(p["role"] == "admin" for p in members), 1)

    def test_11_reset_token_is_single_use_and_revokes_sessions(self):
        import hashlib, secrets
        from datetime import datetime, timedelta, timezone

        token = secrets.token_urlsafe(32)

        async def seed():
            conn = await asyncpg.connect(os.environ["TEST_DATABASE_URL"])
            await conn.execute(
                "INSERT INTO password_resets(token_hash,user_id,expires_at) VALUES($1,$2,$3)",
                hashlib.sha256(token.encode()).hexdigest(),
                uuid.UUID(self.users[1]["id"]),
                datetime.now(timezone.utc) + timedelta(minutes=5),
            )
            await conn.close()

        asyncio.run(seed())
        payload = {"token": token, "password": "RecoveredPass123!"}
        self.assertEqual(
            self.b.post("/auth/reset-password", json=payload).status_code, 204
        )
        self.assertEqual(self.b.get("/users/me").status_code, 401)
        self.assertEqual(
            self.b.post("/auth/reset-password", json=payload).status_code, 400
        )
        self.assertEqual(
            self.b.post(
                "/users/login",
                json={"email": self.users[1]["email"], "password": "RecoveredPass123!"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.admin.patch(
                "/admin/users/" + self.users[1]["id"], json={"disabled": True}
            ).status_code,
            200,
        )
        self.assertEqual(self.b.get("/users/me").status_code, 401)
        self.assertEqual(
            self.admin.patch(
                "/admin/users/" + self.users[1]["id"], json={"disabled": False}
            ).status_code,
            200,
        )
        self.assertEqual(self.b.get("/users/me").status_code, 401)

    def test_12_listener_recovery_signals_history_resync(self):
        other = os.getenv("COFFEENCHAT_SECOND_URL", self.base)
        token = self.a.cookies.get("access_token")
        with connect(
            other.replace("http", "ws", 1) + "/ws/chat",
            origin="http://localhost:5173",
            additional_headers={"Cookie": "access_token=" + token},
        ) as ws:

            async def interrupt_listeners():
                con = await asyncpg.connect(os.environ["TEST_DATABASE_URL"])
                rows = await con.fetch(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=current_database() AND application_name='coffeenchat-listener'"
                )
                await con.close()
                return len(rows)

            self.assertGreaterEqual(asyncio.run(interrupt_listeners()), 1)
            response = self.a.post(
                f"/conversations/{self.direct}/messages",
                json={
                    "conversation_id": self.direct,
                    "content": "Saved during listener restart",
                    "client_id": str(uuid.uuid4()),
                },
            )
            self.assertEqual(response.status_code, 201, response.text)
            for _ in range(5):
                if json.loads(ws.recv(timeout=10))["type"] == "resync":
                    break
            else:
                self.fail("No resync event after listener reconnect")
            ids = [
                m["id"]
                for m in self.a.get(f"/conversations/{self.direct}/messages").json()
            ]
            self.assertIn(response.json()["id"], ids)

    def test_13_session_expiry_closes_idle_socket(self):
        other = os.getenv("COFFEENCHAT_SECOND_URL", self.base)
        token = self.admin.cookies.get("access_token")
        session = next(
            s["id"] for s in self.admin.get("/users/sessions").json() if s["current"]
        )
        with connect(
            other.replace("http", "ws", 1) + "/ws/chat",
            origin="http://localhost:5173",
            additional_headers={"Cookie": "access_token=" + token},
        ) as ws:

            async def expire():
                con = await asyncpg.connect(os.environ["TEST_DATABASE_URL"])
                await con.execute(
                    "UPDATE auth_sessions SET expires_at=now()-interval '1 second' WHERE id=$1",
                    session,
                )
                await con.close()

            asyncio.run(expire())
            with self.assertRaises(ConnectionClosed):
                ws.recv(timeout=8)
        self.assertEqual(self.admin.get("/users/me").status_code, 401)
