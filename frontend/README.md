# CoffeeNchat frontend

See the root README for the full local API/database setup. Node 24 is the supported tested baseline.

- `npm ci`
- `npm run dev` — Vite at 127.0.0.1:5173, proxying `/api` and WebSockets to 127.0.0.1:8000.
- `npm run lint`
- `npm run build` — strict TypeScript plus Vite production bundle.
- `npx playwright install chromium` then `npm run test:e2e` — requires the disposable local backend/Vite environment; creates synthetic accounts.

Production uses the provided nginx configuration for deep-link fallback and API/WebSocket proxying. `vite preview` only previews static build output and is not a replacement for that production API proxy. Authentication uses cookies; only appearance preference is stored in localStorage. UI drafts/unconfirmed retries are in memory and are lost on reload. Browser tests emit screenshots/traces into the ignored `test-results` directory.
