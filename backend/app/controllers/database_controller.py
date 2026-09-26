from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI

from app.db import engine, init_db, verify_db_connection
from app.services.chat_broker import chat_broker

logger = logging.getLogger(__name__)


class LifespanController:
    @staticmethod
    @asynccontextmanager
    async def handle_lifespan(app: FastAPI):
        try:
            # Verify PostgreSQL connection
            await verify_db_connection()
            # Verify the explicit migration revision; startup never creates tables
            await init_db()
        except Exception:
            logger.exception(
                "Database initialization failed during application startup"
            )
            raise

        try:
            await chat_broker.start()
            yield
        finally:
            await chat_broker.stop()
            await engine.dispose()
