"""Explicit operational commands. Never invoked automatically on application startup."""

import argparse, asyncio, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from alembic.config import Config
from alembic import command

parser = argparse.ArgumentParser()
parser.add_argument("action", choices=["migrate", "create-admin", "cleanup-uploads"])
parser.add_argument("--email")
parser.add_argument("--adopt-legacy", action="store_true")
args = parser.parse_args()
if args.action == "migrate":
    config = Config(str(Path(__file__).with_name("alembic.ini")))
    if args.adopt_legacy:

        async def verify():
            from sqlalchemy import inspect
            from app.db import engine

            expected = {
                "users": {
                    "id",
                    "email",
                    "username",
                    "password_hash",
                    "is_admin",
                    "created_at",
                    "profile_picture_url",
                },
                "conversations": {
                    "id",
                    "is_group",
                    "name",
                    "group_picture_url",
                    "created_at",
                },
                "messages": {
                    "id",
                    "conversation_id",
                    "sender_id",
                    "content",
                    "media_url",
                    "created_at",
                },
                "conversation_participants": {
                    "conversation_id",
                    "user_id",
                    "role",
                    "joined_at",
                },
                "revoked_tokens": {"jti", "expires_at"},
            }
            async with engine.connect() as conn:

                def check(c):
                    inspector = inspect(c)
                    if "alembic_version" in inspector.get_table_names():
                        raise RuntimeError("Database is already versioned")
                    for table, columns in expected.items():
                        if {
                            col["name"] for col in inspector.get_columns(table)
                        } != columns:
                            raise RuntimeError(
                                "Legacy schema differs at "
                                + table
                                + "; inspect before adopting"
                            )

                await conn.run_sync(check)
            await engine.dispose()

        asyncio.run(verify())
        command.stamp(config, "0001_baseline")
    command.upgrade(config, "head")
else:

    async def run():
        from sqlalchemy import select
        from app.db import AsyncSessionLocal, engine
        from app.models.user_model import User
        from app.models.feature_model import Attachment

        async with AsyncSessionLocal() as db:
            if args.action == "create-admin":
                if not args.email:
                    raise RuntimeError(
                        "Supply --email for an existing registered account"
                    )
                user = await db.scalar(
                    select(User).where(User.email == args.email.lower())
                )
                if not user:
                    raise RuntimeError("Account not found. Register it first.")
                user.is_admin = True
                await db.commit()
                print("Administrator role granted.")
            else:
                from app.config import UPLOAD_DIR
                import time

                live = {str(x) for x in (await db.scalars(select(Attachment.id))).all()}
                count = 0
                for path in UPLOAD_DIR.glob("*"):
                    if (
                        path.is_file()
                        and path.name not in live
                        and time.time() - path.stat().st_mtime > 86400
                    ):
                        path.unlink()
                        count += 1
                print("Removed orphaned files:", count)
        await engine.dispose()

    asyncio.run(run())
