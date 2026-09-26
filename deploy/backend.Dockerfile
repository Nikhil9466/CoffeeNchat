FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home coffeenchat
COPY --chown=coffeenchat:coffeenchat backend/ ./
RUN mkdir -p /app/backend/data/uploads && chown -R coffeenchat:coffeenchat /app/backend/data
USER coffeenchat
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--ws-max-size", "65536", "--proxy-headers", "--forwarded-allow-ips", "*"]
