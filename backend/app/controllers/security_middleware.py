import time
from collections import defaultdict, deque
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.config import ORIGINS


class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.requests = defaultdict(deque)
        self.last_cleanup = 0

    async def dispatch(self, request, call_next):
        now = time.monotonic()
        if now - self.last_cleanup > 60:
            self.requests = {
                k: v for k, v in self.requests.items() if v and now - v[-1] < 60
            }
            self.requests = defaultdict(deque, self.requests)
            self.last_cleanup = now
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and origin.rstrip("/") not in ORIGINS:
                return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
        path = request.url.path
        # Reject declared large bodies before multipart parsing. The reverse proxy also
        # limits chunked requests; never expose the application port publicly.
        maximum = 11 * 1024 * 1024 if path.endswith("/attachments") else 65536
        try:
            if int(request.headers.get("content-length", "0")) > maximum:
                return JSONResponse(
                    {"detail": "Request body is too large"}, status_code=413
                )
        except ValueError:
            return JSONResponse({"detail": "Invalid content length"}, status_code=400)
        auth = path in {
            "/users/login",
            "/users/register",
            "/auth/forgot-password",
            "/auth/reset-password",
        }
        key = (
            request.client.host if request.client else "unknown",
            "auth" if auth else "api",
        )
        queue = self.requests[key]
        while queue and now - queue[0] > 60:
            queue.popleft()
        if len(queue) >= (20 if auth else 600):
            return JSONResponse(
                {"detail": "Too many requests. Try again shortly."},
                status_code=429,
                headers={"Retry-After": "60"},
            )
        queue.append(now)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store"
        return response
