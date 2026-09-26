# Architecture and contracts

## Components

`frontend/src/App.tsx` owns authentication, cross-tab session synchronization, theme and routing. `Workspace.tsx` stores conversations and messages by conversation ID, including drafts and unconfirmed sends. `api.ts` owns credentialed HTTP requests and URL construction. New-conversation, details, profile and admin screens live in separate modules. Native dialogs provide browser focus handling. The default browser origin serves `/api`; Vite or nginx removes that prefix for FastAPI.

FastAPI routes use public/private Pydantic response schemas. Conversation policies and message persistence live in service modules. SQLAlchemy's async engine talks to PostgreSQL. Alembic performs explicit upgrades. The application does not use Express, localStorage tokens, recipient-ID routing or HTML iframes.

## Authentication

A signed HS256 JWT is placed in an HttpOnly, SameSite=Lax cookie. It contains a user ID, random session ID, issued time and expiry. Every authentication verifies the signature, database session, expiry and active account. Non-remembered sessions default to 30 minutes; remembered sessions last 30 days. There is no silent refresh-token flow. A device listing exposes session identifiers, never reusable JWTs.

Logout/device revocation removes a session; password change/reset revokes all sessions. Suspension revokes sessions and denies authentication. WebSockets revalidate before received messages, before outgoing sends and at most every three seconds while idle. A request already authorized/in flight may complete concurrently with revocation. A cookie copied into an Authorization bearer header is supported by HTTP endpoints; the browser does not store or read that token. WebSockets accept cookies with allowed browser Origins.

Passwords use bcrypt off the event loop. Inputs are bounded to 72 UTF-8 bytes. Login and password-changing operations serialize on the user row so concurrent login cannot bypass a completed password revocation. Registration normalizes email; a database unique index on lower(email) covers legacy case variations. Public profiles exclude email/admin status/password hashes. Current-user and administrator responses expose only deliberate private fields.

## Conversations and messages

A direct conversation is created for exactly two users. Pair-based advisory locking plus a unique key prevents duplicate new direct conversations. Existing direct membership cannot be expanded. Groups have a 100-member maximum; only group administrators can invite/remove/promote/rename/delete. A last administrator must promote someone else before leaving a populated group. Sole-member groups may be left/deleted. Invitees can read existing group history; there is no join-date history boundary.

Sending obtains the conversation transaction lock, rechecks membership, validates attachment scope and commits the message plus a PostgreSQL notification. Optional client UUIDs are unique per sender; repeating the same payload returns the existing message, while reusing that UUID for another payload returns conflict. The browser always uses client UUIDs and HTTP writes; WebSockets deliver updates and typing. Pending retries are held in browser memory, not persisted across refreshes. Do not reload while resolving an unconfirmed send if you need to preserve its retry ID.

History returns the newest bounded page in chronological display order. Older pages use a message UUID anchor with `(created_at,id)` ordering. Search is bounded substring search. Unread counts exclude the current user's messages. Read position is anchored to an actual message and moves monotonically. A group read check means at least one other participant has read through that message, not every member.

`chat_broker.py` runs one PostgreSQL LISTEN connection and one bounded consumer per API process. Notifications contain message IDs or small events; each process fetches authoritative data and current recipients. The socket registry supports multiple tabs per user and serializes writes per socket. Slow sends time out. Queue overflow/listener reconnect sends a resync signal; the frontend reloads persisted history and merges by ID. Live notifications are not a durable message queue. The backend does not promise exactly-once socket delivery; persistence plus retry IDs and reconciliation provide the user-facing recovery mechanism.

## Files, deletion and moderation

Files use opaque UUID disk names, a 10 MB file limit and membership-protected attachment downloads. Content is sent as an attachment with octet-stream and nosniff headers; it is never rendered as trusted HTML. Storage must be shared by all API processes/hosts. There is no malware scanner or storage quota per account. The proxy bounds complete multipart bodies at 11 MB; keep the API port private.

Deleting a message leaves a tombstone and preserves ordering. Removing a message does **not** erase its previously uploaded file from the conversation Files tab. Group deletion cascades database attachments; the explicit cleanup command removes orphaned disk files after a 24-hour grace period. Account deletion removes identity/session/membership records and anonymizes already-shared messages; those messages remain visible to remaining participants. Backups may retain deleted data until their configured retention expires.

Saved-message retrieval rechecks conversation membership. Reports are unique per reporter/message. Administrators can read reported content, dismiss reports, remove messages or suspend non-admin accounts. There is no comprehensive administrative action audit ledger or appeal workflow in this version.

## Security and scaling boundaries

Unsafe browser requests enforce an Origin allowlist; cookies use SameSite and production Secure flags. Non-browser clients without Origin still need valid authentication. nginx includes HTTPS-deployment-compatible CSP and body/rate limits. The built-in per-IP limiter is per process; configure a shared edge limit across hosts. JWT secrets, database URLs and SMTP credentials come from environment variables. Validation/logging excludes raw request bodies and SQL parameter values.

The database is the source of truth. PostgreSQL LISTEN/NOTIFY is appropriate for this deployment baseline, but worker count increases database fan-out. A slow socket can delay a broker consumer up to the send timeout. Large archives require query/retention planning: substring search is not indexed full-text search, inbox unread counts can be costly, long visible histories are not virtualized and reconnect catch-up is bounded. Offset-based directories can shift while membership/activity changes; refresh returns authoritative current pages. No public concurrency/latency capacity is claimed.
