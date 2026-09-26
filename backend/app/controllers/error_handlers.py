import logging
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)


def setup_logging():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )


async def handle_http_exception(request: Request, exception: HTTPException):
    return JSONResponse(
        {"detail": exception.detail},
        status_code=exception.status_code,
        headers=exception.headers,
    )


async def handle_validation_exception(
    request: Request, exception: RequestValidationError
):
    errors = [
        {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
        for e in exception.errors()
    ]
    return JSONResponse(
        {"detail": "Please check the submitted fields.", "errors": errors},
        status_code=422,
    )


async def handle_unexpected_exception(request: Request, exception: Exception):
    # Do not log SQL parameter values, request bodies, tokens, or credentials.
    logger.error(
        "Request failed: %s %s (%s)",
        request.method,
        request.url.path,
        type(exception).__name__,
    )
    return JSONResponse(
        {"detail": "An unexpected server error occurred."}, status_code=500
    )
