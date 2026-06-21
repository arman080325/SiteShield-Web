# �progress Log

> A living, detailed record of every step taken to build **SiteShield** — a multi-tenant SaaS website security posture scanner.
> This document is the single source of truth for understanding the project from scratch. Updated daily.

---

## 📌 What is SiteShield?

SiteShield is a multi-tenant SaaS platform that audits and monitors a website's **defensive security posture**. A user signs up, adds domains they own, and the platform scans each domain for security weaknesses (HTTP security headers today; TLS, cookies, DNS, and dependency CVEs to come), assigns a weighted **A–F grade**, stores scan history, and (later) monitors on a schedule with alerts and PDF reports.

Every check is **passive and defensive** — it only inspects publicly observable configuration, the way a security-conscious admin would. It is a blue-team tool, not an attack tool.

**Tech stack:** FastAPI (Python) backend · SQLAlchemy ORM · SQLite (dev) → PostgreSQL (prod) · JWT auth · Celery + Redis (async task queue) · React + Vite + Tailwind CSS frontend · Docker · GitHub Actions (planned).

---

## 🧠 Core mental models (read this first — it makes everything click)

### The request lifecycle (FastAPI)
Every request flows: **router → dependencies → database → response**. Dependencies are reusable functions FastAPI injects automatically (e.g. the DB session, the logged-in user). Once that pattern clicks, the rest of the backend is just "more routers."

### Models vs Schemas (why there are two)
- **Models** (`models.py`) = the *database* shape (SQLAlchemy tables).
- **Schemas** (`schemas.py`) = the *API* shape (Pydantic — what JSON comes in and goes out).
Keeping them separate is exactly why we never leak `hashed_password` to a client: the output schema simply doesn't have that field.

### JWT auth flow
1. **Signup**: password is **hashed** with bcrypt (one-way — irreversible) and stored.
2. **Login**: submitted password is **verified** against the stored hash. On success, a **JWT** is issued — a signed token holding the user's email (`sub`) and an expiry (`exp`).
3. **Every later request** sends that token back. The server decodes it, checks the signature + expiry, and identifies the user. Tamper with the token → decode fails → 401.

### Multi-tenant isolation (IDOR protection)
Every query that touches user-owned data filters on `owner_id == current_user.id`. So user A can never read or delete user B's domains — even if they guess the id, the query returns nothing (404). This prevents **IDOR** (Insecure Direct Object Reference), a classic web vuln. This pattern is applied consistently on *every* domain and scan endpoint.

### Async task queue (producer → queue → worker)
The production pattern that decouples "asking for a scan" from "doing the scan":
- **Producer** (FastAPI endpoint): receives the request, drops a job on the queue, returns a `task_id` instantly (HTTP 202).
- **Queue** (Redis): a fast in-memory holding area / message broker.
- **Worker** (Celery): a *separate process* watching the queue. Grabs a job, runs the slow scan, writes the result to the DB.
- **Polling**: the frontend uses the `task_id` to ask "done yet?" until the result is ready.

Restaurant analogy: you (browser) order from the waiter (API), who pins a ticket to the kitchen rail (Redis) and immediately serves the next table. The cook (Celery worker) pulls tickets and cooks. You hold a buzzer (task_id) that lights up when ready. The waiter never freezes at your table waiting for food.

---

## 🗂️ Project structure

```
SiteShield-Web/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app, CORS, router registration, table creation
│   │   ├── config.py            # Settings loaded from .env (pydantic-settings)
│   │   ├── database.py          # SQLAlchemy engine, SessionLocal, Base, get_db dependency
│   │   ├── models.py            # User, Domain, Scan tables
│   │   ├── schemas.py           # Pydantic request/response shapes
│   │   ├── celery_app.py        # Celery instance (broker + backend = Redis)
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── security.py      # hash/verify password, create/decode JWT
│   │   │   ├── dependencies.py  # get_current_user (the auth gatekeeper)
│   │   │   └── router.py        # /auth/signup, /auth/login, /auth/me
│   │   ├── domains/
│   │   │   ├── __init__.py
│   │   │   └── router.py        # CRUD: add/list/get/delete domains (owner-scoped)
│   │   └── scanner/
│   │       ├── __init__.py
│   │       ├── headers.py       # Pure scan logic (decoupled, reusable)
│   │       ├── tasks.py         # Celery task wrapping the scan + DB persist
│   │       └── router.py        # /scan (enqueue), /scan-status, /scans
│   ├── venv/
│   ├── .env                     # secrets + config (gitignored)
│   ├── .gitignore
│   ├── requirements.txt
│   └── siteshield.db            # SQLite dev database (gitignored)
└── frontend/
    ├── src/
    │   ├── api/
    │   │   ├── client.js         # fetch wrapper: base URL, token, error normalization
    │   │   ├── auth.js           # signup/login/getMe calls
    │   │   └── domains.js        # domain + scan API calls
    │   ├── context/
    │   │   └── AuthContext.jsx   # app-wide auth state (user, login, logout)
    │   ├── components/
    │   │   ├── AuthForm.jsx      # shared login/signup form
    │   │   ├── AddDomainForm.jsx # add-domain input
    │   │   ├── DomainCard.jsx    # per-domain card + scan button + results
    │   │   ├── ScanResult.jsx    # grade badge + header checklist
    │   │   ├── GradeBadge.jsx    # colored A–F badge
    │   │   └── ProtectedRoute.jsx# redirects unauthenticated users to /login
    │   ├── pages/
    │   │   ├── Login.jsx
    │   │   ├── Signup.jsx
    │   │   └── Dashboard.jsx
    │   ├── App.jsx               # routing + theme toggle + header
    │   ├── main.jsx              # entry; wraps app in AuthProvider
    │   └── index.css             # Tailwind directives
    ├── .env                      # VITE_API_URL (gitignored)
    ├── tailwind.config.js        # darkMode: "class"
    ├── vite.config.js            # port pinned to 5173
    └── package.json
```

---

## ⚙️ Daily startup checklist (how to run the whole stack)

Four processes, each in its own terminal:

1. **Redis** (Docker): start Docker Desktop, then `docker start siteshield-redis`
2. **Backend API**: `cd backend` → `venv\Scripts\activate` → `uvicorn app.main:app --reload`
3. **Celery worker**: `cd backend` → `venv\Scripts\activate` → `celery -A app.celery_app.celery_app worker --loglevel=info --pool=solo`
4. **Frontend**: `cd frontend` → `npm run dev`

URLs: API docs → http://127.0.0.1:8000/docs · Frontend → http://localhost:5173

**Wind-down:** Ctrl+C each terminal · `docker stop siteshield-redis` · quit Docker Desktop (optional).

> ⚠️ **Windows gotcha:** the Celery worker *must* use `--pool=solo`. Celery's default forking pool doesn't work on Windows. This is the #1 Celery-on-Windows error.

---

# 📅 MONTH 1 — Foundation, Auth, Domain CRUD, Scanner, React Dashboard

## ✅ Backend Foundation

### Environment & dependencies
- Created `backend/` with a Python virtual environment (`python -m venv venv`).
- Installed: `fastapi`, `uvicorn[standard]`, `sqlalchemy`, `pydantic-settings`, `pydantic[email]`, `PyJWT`, `bcrypt`, `python-multipart`.
  - `python-multipart` is required for the OAuth2 login form (login uses form data, not JSON).

### Config (`config.py`)
- Uses `pydantic-settings` to load `.env` once at startup into a single `settings` object.
- Fields: `database_url`, `jwt_secret`, `jwt_algorithm`, `access_token_expire_minutes`, `cors_origins`, `redis_url`.
- JWT secret generated with `python -c "import secrets; print(secrets.token_hex(32))"`.

### Database (`database.py`)
- `engine` = connection to the DB. `SessionLocal` = factory for per-request sessions. `Base` = declarative base all models inherit.
- `get_db()` is a dependency that yields a session and **guarantees it closes** (even on error) via try/finally.
- Started on **SQLite** (single local file, zero setup). Switching to **PostgreSQL** for production is a one-line change in `.env` — the whole point of using an ORM.

### Models (`models.py`)
Three tables, all defined up-front so the schema is complete (no mid-build migrations):
- **User**: `id`, `email` (unique, indexed), `hashed_password`, `created_at`. Relationship → `domains`.
- **Domain**: `id`, `url`, `owner_id` (FK to users), `created_at`. Relationships → `owner`, `scans`.
- **Scan**: `id`, `domain_id` (FK), `grade`, `score`, `results_json` (full per-header breakdown stored as JSON text), `created_at`.
- `cascade="all, delete-orphan"` — deleting a user auto-deletes their domains and scans.
- All timestamps use `DateTime(timezone=True)` with `server_default=func.now()`.

### Schemas (`schemas.py`)
- `UserCreate` (signup input: email + password), `UserOut` (output — **no password field**, so it can't leak), `Token` (access_token + token_type).
- `from_attributes=True` lets Pydantic read directly from SQLAlchemy objects.

### Security (`auth/security.py`)
- `hash_password` / `verify_password` — bcrypt.
- `create_access_token` — builds a JWT with `sub` (email) + `exp` (expiry).
- `decode_access_token` — verifies signature + expiry; returns the email or None.

### Auth dependency (`auth/dependencies.py`)
- `get_current_user` — the **gatekeeper**. Pulls the token from the request header, decodes it, looks up the user, returns the `User` or raises 401. Any endpoint that adds `Depends(get_current_user)` becomes protected.

### Auth router (`auth/router.py`)
- `POST /auth/signup` — rejects duplicate emails, hashes password, creates user (201).
- `POST /auth/login` — uses `OAuth2PasswordRequestForm`; the **email goes in the `username` field** (OAuth2 standard). Verifies password, returns JWT.
- `GET /auth/me` — protected; returns the current user (proves the token works).

### App wiring (`main.py`)
- `Base.metadata.create_all` creates tables on first run.
- **CORS middleware** allows the React frontend (port 5173) to call the API (port 8000) — browsers block cross-origin calls otherwise.
- `/health` endpoint for deployment checks.

**✅ Verified:** signup → authorize → `/auth/me` all return correctly via `/docs`.

---

## ✅ Domain CRUD (`domains/router.py`)

All endpoints owner-scoped via `get_current_user`:
- `POST /domains` — add a domain. A Pydantic **validator** normalizes the URL: trims whitespace, rejects empty, prepends `https://` if no scheme, strips trailing slash. Rejects duplicates per user.
- `GET /domains` — list the current user's domains, newest first.
- `GET /domains/{id}` — fetch one owned domain (filtered by id **and** owner_id).
- `DELETE /domains/{id}` — delete one owned domain (204 No Content).

**Key security pattern:** `get_domain` and `delete_domain` filter by `id` **and** `owner_id` together — not just id. Passing another user's domain id → 404. This is the IDOR protection in action.

**✅ Verified:** add (returns normalized `https://` URL), list, get, delete all working. Multi-tenant isolation confirmed (second user sees empty list).

---

## ✅ Synchronous Header Scanner (`scanner/headers.py` + original `scanner/router.py`)

### Scan logic (`headers.py`) — kept as a **pure function** (no FastAPI, no DB)
This decoupling was deliberate — it let the scan logic later drop straight into a Celery worker untouched. Lesson: separating pure logic from the web/DB layer pays off.

Checks **6 security headers**, each weighted:
| Header | Weight | Why it matters |
|---|---|---|
| Content-Security-Policy (CSP) | 25 | Strongest defense against XSS / injection |
| Strict-Transport-Security (HSTS) | 20 | Forces HTTPS, prevents downgrade attacks |
| X-Frame-Options | 15 | Blocks clickjacking via iframes |
| X-Content-Type-Options | 15 | Stops MIME-sniffing (`nosniff`) |
| Referrer-Policy | 15 | Limits referrer info leakage |
| Permissions-Policy | 10 | Restricts browser features (camera, mic, geo) |

- Fetches the URL with `httpx` (follow redirects, 10s timeout, custom User-Agent).
- Sums weights of present headers → 0–100 score → A–F grade:
  - A ≥ 90 · B ≥ 75 · C ≥ 60 · D ≥ 40 · E ≥ 20 · F < 20
- Returns per-header detail: present/absent, value (if present), remediation advice (if absent).
- Gracefully handles unreachable sites (returns grade F + error message).

### Scan endpoint (original synchronous version)
- `POST /domains/{id}/scan` — owner-scoped, runs scan, persists a `Scan` row, returns the full breakdown.
- `GET /domains/{id}/scans` — scan history for a domain.

**✅ Verified live:** github.com scored **A (90/100)** — only missing Permissions-Policy (–10). example.com scored **F (0/100)** — bare site, no security headers. Real contrast confirms the scoring engine works.

---

## ✅ React Frontend (Month 1 dashboard)

### Stage 1 — Scaffold + Tailwind + dark/light theme
- Vite React app in `frontend/`. Tailwind v3 (`darkMode: "class"`). Port pinned to 5173 in `vite.config.js` (matches CORS whitelist).
- Theme toggle: a `dark` state adds/removes the `dark` class on `<html>`; choice saved to localStorage (survives refresh). Every color written as `light-value dark:dark-value`.

### Stage 2 — API client + Auth context (the bridge layer)
- **`api/client.js`**: a `fetch` wrapper. Attaches the JWT (`Authorization: Bearer`), handles both JSON and form-encoded bodies (login uses form data), and **normalizes FastAPI errors** (the `detail` field can be a string or a list) into a clean message. Token stored in localStorage under `siteshield_token`.
- **`api/auth.js`**: thin wrappers — `signup`, `login` (maps email → `username` field), `getMe`.
- **`context/AuthContext.jsx`**: app-wide auth state via React Context. On load, if a token exists it calls `/auth/me` to verify (clears it if expired). Exposes `user`, `isAuthenticated`, `loading`, `login`, `signup` (auto-logs-in after), `logout`. Consumed anywhere via the `useAuth()` hook.
- The `loading` flag prevents a login-screen flash on refresh while the token is being verified.

### Stage 3 — Login/Signup pages + routing + protected routes
- React Router added. Routes: `/login`, `/signup`, and a protected `/` (dashboard).
- **`AuthForm.jsx`** — shared form (mode = login/signup), shows normalized backend errors, disables button mid-request.
- **`Login.jsx` / `Signup.jsx`** — call the context functions, navigate to `/` on success.
- **`ProtectedRoute.jsx`** — shows "Loading…" while auth is being checked, then either renders the page or redirects to `/login`. This is where the `loading` flag earns its keep.
- Header shows the user's email + a "Log out" button when authenticated.

**✅ Verified:** signup → auto-login → dashboard. Logout → login. Refresh → **session persists** (token restored from localStorage, not kicked to login). This is the satisfying proof of real session handling.

### Stage 4 — Domain management + visual scan results
- **`api/domains.js`** — `listDomains`, `addDomain`, `deleteDomain`, `runScan`, `listScans`.
- **`AddDomainForm.jsx`** — add a domain; clears on success; surfaces backend errors (e.g. "Domain already added").
- **`Dashboard.jsx`** — loads domains on mount; add prepends to the list (instant UI update); delete removes from both DB and local state. Empty state when no domains.
- **`GradeBadge.jsx`** — colored A–F circle (green A → red F) with score.
- **`ScanResult.jsx`** — renders the grade badge + per-header checklist: green ✓ (present, shows value) / red ✗ (missing, shows amber advice). Handles error state.
- **`DomainCard.jsx`** — each card holds its **own** scan state (`result`, `scanning`, `error`), so scanning one domain doesn't affect others. "Scan now" button.

**✅ Verified:** add/list/delete persist across refresh. github.com renders **A (90/100)** badge + full checklist; example.com renders a low grade with red ✗ rows. The full frontend↔backend pipeline works visually.

### Minor fix logged
- Date display in `DomainCard.jsx`: changed to `new Date(domain.created_at + "Z").toLocaleDateString("en-GB")` — the `+ "Z"` marks the timestamp as UTC so it converts correctly to IST; `en-GB` gives DD/MM/YYYY.
- **TODO at PostgreSQL migration:** remove the `+ "Z"` patch — Postgres emits proper timezone offsets, so the hack becomes unnecessary (and would double-offset).

---

# 📅 MONTH 2 — Async Background Scanning (in progress)

## ✅ Redis via Docker
- Installed Docker Desktop (WSL2 backend on Windows 11). Chose Docker over WSL2-native Redis for **maximum production tooling exposure** (advances the Month 4 containerization story).
- Ran Redis as a container: `docker run -d --name siteshield-redis -p 6379:6379 redis`
  - `-d` detached · `--name` friendly name · `-p 6379:6379` maps container port to host so FastAPI reaches it at `localhost:6379` · `redis` is the image (auto-pulled from Docker Hub).
- **Verified:** `docker exec -it siteshield-redis redis-cli ping` → **PONG**.
- Daily use: `docker start siteshield-redis` (NOT `docker run` again — `run` creates, `start` wakes the existing container).

## ✅ Celery + Redis wiring
- Installed `celery` and `redis` (Python client). Added `REDIS_URL=redis://localhost:6379/0` to `.env` and `config.py`.
- **`celery_app.py`** — the Celery instance. `broker` (jobs in) and `backend` (results out) both point at Redis. `autodiscover_tasks(["app.scanner"])` finds task definitions. JSON serialization, UTC.
- **`scanner/tasks.py`** — `run_domain_scan(domain_id, url)` as a `@celery_app.task`. **Reuses the existing `scan_headers` pure function untouched** (the decoupling payoff). The worker opens its **own** `SessionLocal()` session because it's a separate process and can't use the request-scoped `get_db`.

## ✅ Endpoint rewrite (sync → async) (`scanner/router.py`)
- `POST /domains/{id}/scan` → now **enqueues**: `run_domain_scan.delay(...)` drops the job on Redis and returns `{task_id, status: "queued"}` **instantly** (HTTP **202 Accepted**, the correct async semantics).
- `GET /domains/scan-status/{task_id}` — **new polling endpoint**. Reads Celery task state (PENDING/STARTED/SUCCESS/FAILURE) and returns clean statuses (pending/running/done/failed). On success, includes the full result.
- `GET /domains/{id}/scans` — unchanged (history).

## ✅ Worker launched & full async loop verified
- Worker started: `celery -A app.celery_app.celery_app worker --loglevel=info --pool=solo`.
- Startup banner showed `run_domain_scan` registered under `[tasks]`, connected to Redis, ended with `ready.`
- **Verified end-to-end:** POSTed a scan → returned a `task_id` instantly → **watched the worker terminal pick it up live**:
  ```
  Task run_domain_scan[...] received
  HTTP Request: GET https://example.com "200 OK"
  Task run_domain_scan[...] succeeded in 0.83s: {'scan_id': 3, 'grade': 'F', 'score': 0, ...}
  ```
- This is the **producer → queue → worker** pipeline working in real time. The API never did the work — the worker did, in a separate process. **Core Month 2 architectural milestone achieved.**

### Note logged
- VS Code may show "Import could not be resolved" squiggles if the Python interpreter isn't pointed at the venv. Fix: Ctrl+Shift+P → "Python: Select Interpreter" → `backend\venv\Scripts\python.exe`. Cosmetic only — the running worker proves imports work.

---

## ⏭️ Next up (Month 2 remainder)

- [ ] **Frontend enqueue-and-poll:** rewrite "Scan now" to call the enqueue endpoint, get a `task_id`, then poll `/scan-status/{task_id}` every ~2s until "done" — showing a live "Scanning…" state. Makes the async work visible in the UI.
- [ ] **TLS/SSL scanner:** protocol versions, cipher strength, certificate expiry.
- [ ] **Cookie flag checks:** Secure, HttpOnly, SameSite.
- [ ] **DNS hygiene:** SPF, DMARC, DNSSEC records.
- [ ] **Scoring engine v2:** combine all check categories into the weighted grade.
- [ ] PR + merge the `feature/async-scanning` branch once the frontend half lands.

## 🗺️ Later (Month 3–5)
- Scheduled re-scans (Celery beat) · history/trend charts · PDF reports (ReportLab) · email alerts on regression · dependency CVE checks (OSV/NVD) · rate limiting · test suite · GitHub Actions CI/CD · SQLite→PostgreSQL migration · live deployment (Render/Railway) · UI polish pass (dark cinematic).

---

## 🔁 Git workflow (the rhythm followed for every feature)

```
git checkout main && git pull          # start fresh
git checkout -b feature/<name>          # BRANCH FIRST (before writing code)
# ... build + test ...
git add . && git commit -m "feat: ..."  # commit on the branch
git push -u origin feature/<name>
# open PR on GitHub → review description → Merge → Delete branch
git checkout main && git pull           # sync local
git branch -d feature/<name>            # clean up
```

**Lesson learned:** always create the branch *before* writing code, so commits have somewhere of their own to land. (Early on, a commit went straight to `main` because the branch was created after the work — harmless on a solo repo, but the correct order avoids it.)

**Branches so far:** `feature/domain-crud` · `feature/header-scanner` · `feature/react-dashboard` · `feature/async-scanning` (current).

---

## 🎯 Why this project matters (interview framing)

SiteShield demonstrates, in one project:
- **System design** — pure scan logic decoupled so it moved from a sync endpoint into an async worker without a rewrite.
- **Async architecture** — real producer→queue→worker with Celery + Redis (not a toy).
- **Security awareness** — IDOR-safe ownership scoping on every endpoint, bcrypt hashing, JWT auth, defensive-only scanning.
- **Production tooling** — Docker, FastAPI, React, with a clear path to CI/CD and cloud deployment.
- **Full-stack range** — typed API backend + a polished React SPA with auth, routing, and theming.

This is the headline project for placement conversations: when asked "tell me about a project," this is the one.

---

*Last updated: end of Month 2 async-pipeline milestone. Next session: frontend enqueue-and-poll.*
