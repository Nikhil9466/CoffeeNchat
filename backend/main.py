import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.controllers.error_handlers import (
    handle_http_exception,
    handle_unexpected_exception,
    handle_validation_exception,
    setup_logging,
)

setup_logging()

from app.controllers.cors import setup_cors
from app.controllers.database_controller import LifespanController
from app.routes.chat_routes import router as chat_router
from app.routes.user_routes import router as user_router
from app.routes.conversation_router import router as conversation_router
from app.routes.admin_routes import router as admin_router

app = FastAPI(lifespan=LifespanController.handle_lifespan)

app.add_exception_handler(StarletteHTTPException, handle_http_exception)
app.add_exception_handler(RequestValidationError, handle_validation_exception)
app.add_exception_handler(Exception, handle_unexpected_exception)

app.include_router(user_router)
app.include_router(conversation_router)
app.include_router(chat_router)
app.include_router(admin_router)
from app.routes.feature_routes import router as feature_router
from app.controllers.security_middleware import SecurityMiddleware

app.add_middleware(SecurityMiddleware)
setup_cors(app)
app.include_router(feature_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    from app.db import engine
    from sqlalchemy import text
    from app.services.chat_broker import chat_broker
    from fastapi import HTTPException

    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    if not chat_broker.connection or chat_broker.connection.is_closed():
        raise HTTPException(503, "Chat listener unavailable")
    return {"status": "ready"}
