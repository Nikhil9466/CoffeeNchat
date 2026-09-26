# CoffeeNchat

Built by Nagender Rao while learning WebSockets, FastAPI and reliable real-time application design.

A self-hosted chat workspace built with React, FastAPI and PostgreSQL. This version replaces the disconnected dashboard with real direct/group conversations and a responsive purple/dark interface inspired by the supplied design. Light appearance is also available.


![CoffeeNchat desktop and mobile preview](documentation/previews/CoffeeNchat-preview.png)

[View the preview PDF](documentation/previews/CoffeeNchat-preview.pdf) · [Project portfolio](https://github.com/Nikhil9466/My-portfolio)

## What works

- Account registration/login, HttpOnly cookie sessions, logout, connected-session revocation, password changes and account deletion.
- Direct messages, groups with explicit administrators, member addition/removal, promotion, renaming and group deletion.
- Persisted messages, recent-first cursor history, message search, per-conversation drafts, duplicate-safe retries and WebSocket updates across API workers.
- Unread counts, typing indicators, read receipts, private file downloads (10 MB maximum), saved messages and reports.
- Actual admin statistics, user suspension and report dismissal/message removal.
- Profile editing, desktop browser notifications while a tab remains open, mobile conversation selection and light/dark appearance.
- Password recovery when a STARTTLS SMTP provider is configured. Token verification/revocation is tested; delivery through a real provider is an operator setup task.

Calls, screen sharing, OAuth/social login, tasks, full online presence, push notifications while the browser is closed and end-to-end encryption are **not implemented**. The UI does not present these as working controls. “Connected” refers to the live-update connection, not another user's presence. The visual reference is inspiration, not a claim of pixel-identical feature coverage.

## Local setup (Linux)

Use Python 3.12, Node 24 and PostgreSQL 16. Run these commands from the extracted project root. Python runtime dependencies are resolved in `backend/requirements.txt`; npm uses `frontend/package-lock.json`.

```sh
python3.12 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
npm ci --prefix frontend
cp backend/.env.example backend/.env
```

Create a PostgreSQL database and set `SQLALCHEMY_DATABASE_URL` in `backend/.env`. Generate your own signing secret with `.venv/bin/python -c "import secrets; print(secrets.token_hex(32))"` and set `JWT_SECRET_KEY`. Never use the example value. PostgreSQL must allow the application user to create tables during migration.

```sh
.venv/bin/python backend/manage.py migrate
cd backend
../.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --ws-max-size 65536
```

In another terminal, from the project root:

```sh
npm --prefix frontend run dev
```

Open **http://127.0.0.1:5173** (or localhost:5173). Vite proxies `/api` and WebSockets to port 8000, so cookies stay on the browser's origin. You do not need a frontend `.env` for this default. If you override `VITE_API_BASE_URL`, preserve same-site cookies and include the browser origin in `CORS_ORIGINS`.

Register your own account. To make that existing account an administrator:

```sh
.venv/bin/python backend/manage.py create-admin --email your-email@example.com
```

There are no default accounts, passwords or embedded secrets. `/health` is liveness; `/ready` checks PostgreSQL and this worker's notification listener. A healthy response from a load-balanced worker is not proof that all workers are healthy.

## Existing databases

Do not run a fresh-schema initializer over existing data. Back up the database and uploads, restore into an isolated copy and test migration first. For an **unversioned database matching the original Nagender schema**:

```sh
.venv/bin/python backend/manage.py migrate --adopt-legacy
```

The command checks the expected legacy column names, stamps the baseline and applies migrations. That check is not a complete certification of legacy column types, indexes or custom triggers. Review schema differences first. Already versioned databases use `migrate` without the adoption flag. Startup only verifies the migration revision; it never changes the schema.

Migration stops for case-insensitive duplicate emails, direct chats with more than two members or populated groups without an administrator. Review those records in a copy and decide the correct ownership/history policy; the application does not silently merge or discard them. Duplicate valid direct histories remain separate; the first reused pair receives a unique canonical key for future creation. New sessions are required after this upgrade because old JWTs do not have session records. Destructive downgrades are disabled: rollback means restoring a verified backup.

## Verification

Fast unit tests do not connect to PostgreSQL:

```sh
cd backend
../.venv/bin/python -m unittest discover -s tests -p test_regressions.py -v
```

The integration suite requires **an explicitly selected disposable database** and running API instances. Never supply production URLs. It creates test users/messages, promotes a synthetic administrator and tests deletion/revocation. Start a second API process on port 8001 against the same test database, then:

```sh
export COFFEENCHAT_TEST_URL=http://127.0.0.1:8000
export COFFEENCHAT_SECOND_URL=http://127.0.0.1:8001
export TEST_DATABASE_URL=postgresql://TEST_USER:TEST_PASSWORD@127.0.0.1:5432/coffeenchat_test
export TEST_POSTGRES_ADMIN_URL=postgresql://TEST_USER:TEST_PASSWORD@127.0.0.1:5432/postgres
../.venv/bin/python -m unittest discover -s tests -v
```

Migration tests create/drop uniquely named databases on that test server, requiring CREATEDB. The database name of the main integration URL is not sufficient protection by itself; choose a separate disposable PostgreSQL instance. Tests skip when their opt-in environment variables are absent. Set both server URLs to exercise two processes.

With the test API and Vite running, from the root:

```sh
npm --prefix frontend run lint
npm --prefix frontend run build
cd frontend
npx playwright install chromium
npm run test:e2e
```

Playwright uses three browser workflows and synthetic accounts, including a simulated lost response after a successful message commit. Default URLs are local; override `COFFEENCHAT_WEB_URL` and `COFFEENCHAT_API_URL` for a test deployment. Back-to-back runs may hit intentional auth rate limits; wait for the one-minute window rather than disabling production limits. CI configuration is included, but remote CI has not been run as part of this local delivery.

## Deployment and operations

See [deployment and recovery](documentation/projectguide.md), [architecture and data flow](documentation/dataflow.md) and [verification and remaining limits](documentation/verification.md). Docker Compose and nginx configurations are included as a deployment starting point. Container startup has not been exercised on the delivery machine because Docker daemon access and Compose were unavailable; validate them in your environment before public use.

## Brand update

The app is named **CoffeeNchat**. Source references to the previous personal project name use **Nagender**. Application notification channels, local preference/session keys, test environment variable prefixes and example infrastructure identifiers now use `coffeenchat` / `COFFEENCHAT`. Restart all API workers together and reload browser tabs when upgrading; do not mix old and new notification channels. Existing database names are controlled by your connection URL and do not need to be renamed. No stored user data is rewritten by this branding change.
