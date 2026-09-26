import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
ORIGINS = [
    x.strip().rstrip("/")
    for x in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if x.strip()
]
PRODUCTION = os.getenv("APP_ENV", "development") == "production"
COOKIE_SECURE = os.getenv("COOKIE_SECURE", str(PRODUCTION)).lower() == "true"
UPLOAD_DIR = Path(
    os.getenv("UPLOAD_DIR", str(Path(__file__).resolve().parents[2] / "data/uploads"))
)
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

if PRODUCTION and not COOKIE_SECURE:
    raise ValueError("Production requires COOKIE_SECURE=true and HTTPS")
