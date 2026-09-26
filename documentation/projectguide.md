# Deployment, maintenance and recovery

## Docker local preview

From the project root, copy `.env.example` to `.env`, set fresh random hex values for `POSTGRES_PASSWORD` and `JWT_SECRET_KEY`, then run `docker compose up --build -d`. Use URL-safe/hex database passwords in this example connection URL. The migration service must succeed before API startup; nginx waits for readiness. Open http://localhost:8080. Register an account and grant administration with `docker compose exec api python manage.py create-admin --email your-email@example.com`.

Only the web port is published, bound to loopback. PostgreSQL and API ports remain internal. Named database and upload volumes persist across ordinary container restarts. **Do not run `docker compose down -v` on data you need.** Container execution is not locally verified in this delivery; first exercise the stack with disposable volumes. Image tags are intentionally readable baseline tags, not digest-pinned supply-chain artifacts; pin verified digests in your own release process.

## Public HTTPS deployment

Put the loopback web service behind your TLS reverse proxy. Set:

- `APP_ENV=production`
- `COOKIE_SECURE=true`
- `CORS_ORIGINS=https://your-chat-domain.example` (exact browser origin, no wildcard)
- `PUBLIC_FRONTEND_URL=https://your-chat-domain.example`
- Fresh database/JWT credentials and a backup retention policy.

Terminate TLS, redirect HTTP to HTTPS and configure HSTS at that trusted edge. Preserve WebSocket upgrades. The app refuses production with insecure cookies. The provided inner nginx trusts no arbitrary real-IP headers; if there is an additional trusted proxy, configure real-IP extraction against only its addresses so per-IP limits remain meaningful. Uvicorn trusts forwarded headers only because its port is isolated behind nginx; do not publish that application port. Restrict trusted proxy sources if adapting the topology.

All API replicas need the same database/signing key and access to the same uploaded-file storage. The included named volume works for multiple processes on one Docker host. Multi-host object storage and antivirus scanning require additional work. Keep PostgreSQL LISTEN connections out of transaction-pooling modes that do not preserve sessions.

The nginx configuration includes SPA deep-link fallback, cookie-compatible `/api` proxying, WebSocket upgrade, complete request body limits, login throttling and CSP. Google Fonts is currently loaded from Google; self-host fonts or replace the import when the deployment requires no third-party requests. Browser notifications require HTTPS (localhost development is an exception), permission and an open browser tab.

## SMTP password recovery

Set `SMTP_HOST`, `SMTP_PORT` (default 587), `SMTP_FROM`, `SMTP_USER`, `SMTP_PASSWORD`, and `PUBLIC_FRONTEND_URL`. SMTP uses STARTTLS and certificate verification. Use a sender verified by your mail provider. The login page shows recovery only when SMTP is enabled. Test delivery, expiry, one-time use, spam handling and provider errors with controlled test accounts before relying on recovery. Do not point test environments at real user addresses. Reset tokens are stored only as SHA-256 hashes, expire after 15 minutes and are sent in the frontend URL fragment; the frontend removes the fragment from history after reading it. Delivery failure logs a safe error class and does not disclose account existence in the HTTP response.

## Maintenance

- Monitor `/health`, `/ready`, HTTP error/429 rates, WebSocket disconnections, broker reconnect/overflow logs, PostgreSQL connections and upload disk usage. Readiness is per worker.
- Run `python manage.py cleanup-uploads` explicitly (inside the API container or configured backend environment) to remove disk files no longer referenced by an attachment row and older than 24 hours. There is no automatic deletion scheduler.
- Review expired password-reset/revoked-token rows and retention as part of operations. Expired session rows are pruned during login.
- Rotate signing keys to invalidate all existing cookies. Store secrets outside source control. No secret or user database is packaged with the release.
- Run versioned migrations once per deployment, after testing a database copy. Never run schema downgrade over live data; restore a backup if rollback is required.

## Backup and restore procedure

1. Take an encrypted PostgreSQL custom-format dump using `pg_dump -Fc` with a protected service credential or `.pgpass`. Do not put a password in a committed script.
2. Back up the uploads directory/volume alongside the database. For a consistent pair, briefly stop API writers while taking the database snapshot and copying upload files. Record the source revision and configuration separately without exposing secrets.
3. Restore into an **empty isolated database** with `pg_restore --no-owner --no-acl`, restore the matching upload files and give the API runtime user read/write access.
4. Start an isolated application against the restored copy. Check the migration version, row counts, representative messages, membership restrictions and actual file downloads. Keep SMTP disabled in recovery drills.
5. Only after that verification perform a planned cutover. Keep the original database/volume until the rollback window closes. A successful SQL restore alone does not establish upload consistency or a full disaster recovery objective.

Migration tests verify fresh creation, repeat upgrade, preservation of representative legacy history and refusal of ambiguous email identities. The shipped verification report distinguishes those checks from Docker/TLS/provider validation. Configure off-host backups and repeat a full database-plus-upload restoration drill before public use; no uptime, RPO/RTO or high-scale guarantee is claimed.
