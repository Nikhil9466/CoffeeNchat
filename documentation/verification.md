# Verification and delivery limits — 2026-09-26

This is a tested **core chat implementation**, not a claim that every optional feature in the design reference exists or that the service is certified for public production. The original input ZIP was preserved. Work was performed in an isolated extracted copy; no user production database was used, and no commits, pushes or external deployments were made.

## Branding verification

The renamed CoffeeNchat source passed the complete 24-test backend suite (20.197 seconds), the three Chromium workflows (15.9 seconds), ESLint and the strict production build. Source text was checked for old app/personal-project names. Desktop and mobile previews show the running app with illustrative sample conversations; no demo credentials or database are included.

## Checks completed locally

| Check | Result |
|---|---|
| Backend unit/integration/migration suite | 24 tests passed: 8 unit, 13 integration, 3 migration |
| Browser workflows | 3 Playwright tests passed in Chromium |
| Additional admin browser smoke | Real counters/directory loaded; admin logout redirected to login; no browser runtime errors |
| TypeScript strict + Vite build | Passed |
| ESLint | Passed |
| Python Ruff F rules and formatting check | Passed |
| Python production dependency resolution | Exact pins resolved successfully with pip dry-run on Python 3.12/Linux |
| npm dependency audit during lock update | 0 known vulnerabilities reported; not a comprehensive security audit |
| PostgreSQL dump/restore exercise | Custom-format dump restored into a separate temporary database; migration revision and row counts matched across all 11 tables |
| Compose/workflow configuration | YAML parsed; Docker/remote CI execution not performed |

The backend suite ran against PostgreSQL 16 and **two independent Uvicorn processes**. It covers public/private response filtering; direct/group boundaries; concurrent direct creation; newest/older message pages; search; duplicate-safe message retries; private attachments; saved messages/reports; moderation; Origin checks; self-only profile edits; session revocation; password changes; anonymized account deletion; invalid socket payloads; member removal; concurrent last-administrator departures; single-use password reset; account suspension; listener termination/reconnect/resync; and idle socket expiry.

The browser suite covers registration, live exchanges between independent accounts, saving/unsaving, search, files, group creation, profile update, logout, 390px mobile navigation, layout overflow, light appearance, landing/login layouts and a lost-response simulation after the server commits a message. Retrying that unconfirmed send produces exactly one persisted/displayed message after reload. Visual screenshots were inspected for desktop chat, mobile chat, landing, profile and administration.

Migration tests cover fresh creation and repeat migration, adopting a representative unversioned legacy schema while preserving IDs/content/password hashes, and refusal of case-insensitive email collisions without deleting the accounts. They do not prove every possible customized legacy database will migrate. No automatic history merges or ownership reassignment are performed.

The database restoration drill did not establish full database-plus-upload consistency or a disaster recovery RPO/RTO. Follow the operations guide for a complete deployment-specific restore exercise.

## Explicitly remaining outside this release

- Voice/video calls, screen sharing and their signaling/TURN infrastructure.
- Google/GitHub OAuth, email ownership verification and invitation-only registration.
- Full user presence, tasks, avatar editing, group activity charts, reactions and rich inline media previews.
- Push notifications when the browser is closed, mobile native apps, persistent offline drafts/outbox and end-to-end encryption.
- Multi-host object storage, antivirus/quarantine, account storage quotas, indexed full-text search and message-list virtualization.
- Comprehensive admin audit trail, retention/privacy policy implementation and moderation appeals.
- Actual SMTP provider delivery, Docker startup, TLS/reverse-proxy deployment and remote CI runs.
- Independent penetration testing, sustained large-load measurement and an established concurrency/capacity limit.

## Behaviors operators/users should know

- Group invitees see existing history. Administrators can inspect reported message content. Server operators control the database; this is not end-to-end encrypted messaging.
- Deleting a message creates a tombstone; files previously uploaded remain in the Files tab. Account deletion anonymizes shared history rather than erasing it. Group deletion removes database records; orphaned disk files require the explicit cleanup command after its grace period.
- Ordinary sessions expire after 30 minutes by default; remembering a browser gives 30 days. Password changes revoke all sessions. There is no refresh-token flow.
- Read checks in groups mean at least one other participant has read through the message. “Connected” is transport status. Browser notifications contain no message text and require an open tab.
- Unconfirmed retries and drafts live only in page memory. If a response is lost, use Retry with the retained client ID; reloading loses that pending ID. A dismissal control lets the user clear a stuck retry after checking history.
- History/search, directory, files and saved-message queries are bounded. Offset views can shift during concurrent changes; long histories are not virtualized. Broker queues/recovery are bounded; no unlimited/offline-delivery capacity is promised.

## Operational acceptance before public use

Configure your own credentials, exact origins and HTTPS. Verify the supplied container configuration in your environment; this machine lacked Docker daemon access and Compose. Test SMTP with controlled accounts if enabled. Back up and restore both the database and uploads, then exercise representative downloads. Review deployment-level rate limits, body limits, disk quota/retention and monitoring. Test the actual expected load before setting a capacity target.
