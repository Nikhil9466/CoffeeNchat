"""Creates/drops randomly named databases only on an explicitly supplied test server."""

import asyncio
import os
from pathlib import Path
import subprocess
import sys
import unittest
import uuid
from urllib.parse import urlsplit, urlunsplit
import asyncpg

BACKEND = Path(__file__).resolve().parents[1]


@unittest.skipUnless(
    os.getenv("TEST_POSTGRES_ADMIN_URL"),
    "Requires a disposable PostgreSQL server with CREATEDB",
)
class Migrations(unittest.TestCase):
    def setUp(self):
        self.name = "coffeenchat_migration_" + uuid.uuid4().hex[:12]
        admin = os.environ["TEST_POSTGRES_ADMIN_URL"]
        parts = urlsplit(admin)
        self.url = urlunsplit(parts._replace(path="/" + self.name))

        async def create():
            con = await asyncpg.connect(admin)
            await con.execute("CREATE DATABASE " + self.name)
            await con.close()

        asyncio.run(create())
        self.env = {**os.environ, "SQLALCHEMY_DATABASE_URL": self.url}

    def tearDown(self):
        async def remove():
            con = await asyncpg.connect(os.environ["TEST_POSTGRES_ADMIN_URL"])
            await con.execute("DROP DATABASE " + self.name + " WITH (FORCE)")
            await con.close()

        asyncio.run(remove())

    def sql(self, sql):
        async def run():
            con = await asyncpg.connect(self.url)
            try:
                return await con.fetch(sql)
            finally:
                await con.close()

        return asyncio.run(run())

    def migrate(self, *args):
        return subprocess.run(
            [sys.executable, str(BACKEND / "manage.py"), "migrate", *args],
            cwd=BACKEND,
            env=self.env,
            capture_output=True,
            text=True,
        )

    def baseline(self):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "0001_baseline"],
            cwd=BACKEND,
            env=self.env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_fresh_and_repeat(self):
        for _ in range(2):
            result = self.migrate()
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.sql("SELECT version_num FROM alembic_version")[0]["version_num"],
            "0003_integrity",
        )
        self.assertEqual(
            len(self.sql("SELECT tablename FROM pg_tables WHERE schemaname='public'")),
            11,
        )

    def test_adopt_legacy_preserves_history(self):
        self.baseline()
        uid, cid, mid = [str(uuid.uuid4()) for _ in range(3)]

        async def seed():
            con = await asyncpg.connect(self.url)
            await con.execute(f"""INSERT INTO users(id,email,username,password_hash) VALUES('{uid}','legacy@example.com','Legacy','existing-hash');
            INSERT INTO conversations(id,is_group,name) VALUES('{cid}',true,'Legacy group');
            INSERT INTO conversation_participants(conversation_id,user_id,role) VALUES('{cid}','{uid}','admin');
            INSERT INTO messages(id,conversation_id,sender_id,content) VALUES('{mid}','{cid}','{uid}','Historical message');
            DROP TABLE alembic_version;""")
            await con.close()

        asyncio.run(seed())
        result = self.migrate("--adopt-legacy")
        self.assertEqual(result.returncode, 0, result.stderr)
        row = self.sql("SELECT id,content FROM messages")[0]
        self.assertEqual(str(row["id"]), mid)
        self.assertEqual(row["content"], "Historical message")
        self.assertEqual(
            self.sql("SELECT password_hash FROM users")[0]["password_hash"],
            "existing-hash",
        )

    def test_ambiguous_legacy_identity_stops_migration(self):
        self.baseline()
        self.sql(
            f"INSERT INTO users(id,email,username,password_hash) VALUES('{uuid.uuid4()}','Same@example.com','One','x'),('{uuid.uuid4()}','same@example.com','Two','y')"
        )
        result = self.migrate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("case-insensitive duplicate emails", result.stderr)
        self.assertEqual(self.sql("SELECT count(*) AS n FROM users")[0]["n"], 2)
