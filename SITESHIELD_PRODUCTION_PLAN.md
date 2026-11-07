# SiteShield — Production Build Plan for the Antigravity Agent

> **Audience:** an autonomous coding agent (Google Antigravity IDE) working in this repository.
> **Goal:** turn SiteShield from a working portfolio prototype into a production-grade, genuinely useful website-security monitoring product, with a modern, polished UI.
> **How to use this file:** read sections 0–3 in full before touching code. Then execute the phases in section 5 **in order**. Each phase lists tasks, files, and acceptance criteria. A phase is done only when all of its acceptance criteria pass.

---

## Table of contents

0. [Agent operating rules](#0-agent-operating-rules)
1. [Product vision: what "useful, not a gimmick" means here](#1-product-vision)
2. [Non-negotiable invariants](#2-non-negotiable-invariants)
3. [Current-state audit (what exists, what is broken)](#3-current-state-audit)
4. [Target architecture](#4-target-architecture)
5. [Phased execution plan](#5-phased-execution-plan)
   - [Phase 0 — Repo hygiene and quick bug fixes](#phase-0--repo-hygiene-and-quick-bug-fixes)
   - [Phase 1 — Harden the platform itself (SSRF, IDOR, auth, secrets)](#phase-1--harden-the-platform-itself)
   - [Phase 2 — Data model, migrations, API v1](#phase-2--data-model-migrations-api-v1)
   - [Phase 3 — Scanner engine v2 (accuracy and depth)](#phase-3--scanner-engine-v2)
   - [Phase 4 — Remediation knowledge base (the core of usefulness)](#phase-4--remediation-knowledge-base)
   - [Phase 5 — Monitoring, findings lifecycle, alerts](#phase-5--monitoring-findings-lifecycle-alerts)
   - [Phase 6 — Frontend foundation and design system](#phase-6--frontend-foundation-and-design-system)
   - [Phase 7 — Frontend pages and flows](#phase-7--frontend-pages-and-flows)
   - [Phase 8 — Public and developer features](#phase-8--public-and-developer-features)
   - [Phase 9 — Production operations (Docker, CI/CD, observability, deploy)](#phase-9--production-operations)
   - [Phase 10 — Optional extensions](#phase-10--optional-extensions)
6. [Testing strategy](#6-testing-strategy)
7. [Launch checklist / definition of done](#7-launch-checklist)
8. [Appendices](#8-appendices)

---

## 0. Agent operating rules

1. **Work in phases, one branch per phase.** Follow the repo's existing convention: `feature/<short-name>` branched from `main`, conventional commits (`feat:`, `fix:`, `refactor:`, `test:`, `chore:`, `docs:`), one PR per phase (or per large sub-phase). Never commit directly to `main`.
2. **Establish a baseline first.** Before Phase 0, run the existing test suite (`cd backend && pytest -v`) and the frontend build (`cd frontend && npm ci && npm run build && npm run lint`). Record the results in the PR description. Do not "fix" a failing baseline by deleting or skipping tests.
3. **Keep the app runnable at the end of every phase.** `docker compose up --build` must bring up a working stack after each phase.
4. **Tests come with code.** Every backend change ships with pytest tests. Every new frontend component with logic ships with a Vitest test. Scanner changes ship with fixture-based tests that don't need the network.
5. **No fake content.** No fake testimonials, customer logos, "10,000+ sites scanned" counters, fake pricing tiers, or lorem ipsum in shipped UI. Use real data, honest empty states, or clearly labelled examples ("Example report").
6. **Ask before destructive or irreversible actions:** dropping tables or columns that hold user data, force-pushing, rotating production secrets, deleting files outside the scope of a task.
7. **Update the docs as you go.** At the end of every phase, update `README.md` (setup, features) and append a dated entry to `PROGRESS.md` in its existing style.
8. **Stay inside the tech stack below** unless a task explicitly allows a new dependency. Pin exact versions in lockfiles.
9. **When something in this plan conflicts with reality in the code** (a file has moved, a library API changed), prefer the code's reality, keep the intent of the task, and note the deviation in the PR description.

---

## 1. Product vision

### 1.1 One-line pitch

**SiteShield tells website owners exactly what is weak in their site's public security configuration, how to fix it on *their* stack, and warns them the moment something regresses or is about to expire.**

### 1.2 Target users

| Persona | Need | What they get from SiteShield |
|---|---|---|
| **Indie dev / small-business site owner** | "Is my site configured safely? I don't know what HSTS is." | Plain-language findings, copy-paste fixes for Nginx/Apache/Cloudflare/Vercel/Netlify, an A–F grade they can improve. |
| **Freelancer / agency** managing 5–50 client sites | One place to watch every client domain; proof of work for clients. | Multi-domain dashboard, scheduled scans, certificate-expiry alerts, branded PDF reports, "what changed" diffs. |
| **Developer / DevOps** | Catch regressions before users do. | API keys, a CI check that fails a deploy if the grade drops, webhook/Slack alerts. |

### 1.3 What makes it useful rather than a gimmick

A one-off "your grade is C" page is a gimmick. The product becomes useful when it delivers these six things. Every phase below serves at least one of them:

1. **Accurate findings.** Checks inspect header *values* and real configuration quality, not just "is a header present". False positives destroy trust, so prefer marking a check *inconclusive* over guessing.
2. **Actionable remediation.** Every finding explains why it matters, how severe it is, and gives a copy-paste fix for the user's platform, plus a one-line command to verify the fix.
3. **Prioritisation.** A "Top fixes" list ranked by score impact and effort ("Add HSTS: +7 points, 5 minutes").
4. **Continuous monitoring with meaningful alerts.** Certificate expiry warnings, grade-drop alerts, new high-severity findings, and site-unreachable notices, without spamming.
5. **Change tracking.** Each finding has a lifecycle (first seen → resolved), and users can diff any two scans to see exactly what changed.
6. **Sharing and integration.** PDF reports, shareable result links, status badges, and an API/CI integration.

### 1.4 Non-goals (do not build these)

- No active attacks of any kind: no vulnerability exploitation, fuzzing, brute force, port scanning beyond 80/443, or crawling.
- No fake "AI security score", no gamified fluff, no dark patterns.
- No billing or payments in this plan. The product is free; the architecture leaves room for plans later (see Phase 10).

---

## 2. Non-negotiable invariants

These are already true in the codebase (or must become true). **Never regress them.** Add tests that lock each one in.

| # | Invariant | Where it lives today |
|---|---|---|
| I-1 | **Tenant isolation:** every query for user-owned data filters by `owner_id == current_user.id` (or joins through an owned parent). A foreign id returns **404**, not 403. | `backend/app/domains/router.py`, `backend/app/scanner/router.py` |
| I-2 | **Passive and defensive only.** Scanners make only ordinary requests a browser or resolver would make (HTTP GET/HEAD, TLS handshake, DNS queries) to the target's ports 80/443. | `backend/app/scanner/*` |
| I-3 | **Unreachable ≠ finding.** If SiteShield can't measure something, the category or check is `unreachable` / `inconclusive` and is **excluded** from scoring, with the weights re-normalised. Only a measured problem lowers the score. | `backend/app/scanner/tasks.py`, `dns_scan.py` (CAA) |
| I-4 | **Secrets never leave the backend.** Password hashes, tokens, API key hashes, and webhook secrets never appear in API responses or logs. Output schemas are explicit allow-lists. | `backend/app/schemas.py` (`UserOut`) |
| I-5 | **Pure scanner functions.** Scanners take a target and return a result dict/model. They contain no DB or web-framework code, which keeps them unit-testable. | `backend/app/scanner/*.py` |
| I-6 | **Cookie values are never stored or displayed.** Only cookie names and attributes are kept. | new in Phase 3 |
| I-7 | **Scoring is versioned.** Every scan stores the `scoring_version` that produced it, so historical grades stay interpretable after algorithm changes. | new in Phase 2/3 |
| I-8 | **SiteShield must score an A on itself.** The deployed frontend and API must pass every check SiteShield runs. | new in Phase 9 |

---

## 3. Current-state audit

### 3.1 What exists and works

- **Backend:** FastAPI app with JWT auth (bcrypt + PyJWT), domain CRUD with owner scoping, Celery + Redis async scans, Celery beat scheduled sweeps, PostgreSQL via SQLAlchemy 2.0 (`psycopg` 3), ReportLab PDF reports.
- **Scanners (4 categories):** HTTP headers (presence of 6 headers), TLS (certificate validity, expiry, negotiated protocol), DNS (SPF/DMARC/CAA presence), cookies (Secure/HttpOnly/SameSite substring checks). Weighted scoring 35/30/20/15 with re-normalisation for unreachable categories.
- **Frontend:** React 19 + Vite + Tailwind 3, React Router 7, auth context, dashboard with domain cards, domain detail page with history, a Chart.js trend chart, PDF download, monitoring toggle, and a dark/light theme.
- **Ops:** Dockerfiles, docker-compose (redis, postgres, backend, worker, beat, frontend/nginx), and a GitHub Actions workflow running pytest.
- **Tests:** 6 API tests (health, signup/login, duplicate signup, auth required, add/list, IDOR) and 2 cookie-scanner tests.

### 3.2 Defects and gaps, ranked by severity

> Line numbers refer to the code at commit `d55e498`.

#### Critical (security of the platform itself)

| ID | Problem | Location | Fix phase |
|---|---|---|---|
| C-1 | **SSRF.** Users can add any URL, such as `http://localhost:8000`, `http://redis:6379`, `http://postgres:5432`, `http://169.254.169.254/latest/meta-data/` (cloud metadata) or `10.x` addresses. The worker fetches them with `follow_redirects=True`, so even a public URL can redirect to an internal one. The TLS scanner opens raw sockets to any host. | `backend/app/schemas.py:23-36` (`DomainCreate`), `scanner/headers.py`, `scanner/cookies.py`, `scanner/tls.py` | 1 |
| C-2 | **IDOR on scan status.** `GET /domains/scan-status/{task_id}` returns any Celery task result to any logged-in user who knows the task id. Results include full scan details. | `backend/app/scanner/router.py:40-56` | 1 |
| C-3 | **Hard-coded JWT secret** committed as the default. If production forgets to set `JWT_SECRET`, anyone can forge tokens. | `backend/app/config.py:8` | 1 |
| C-4 | **No rate limiting** on login, signup or scans. This allows credential stuffing, and lets the platform be used to hammer third-party sites. | all routers | 1 |
| C-5 | **PDF generation can crash on user-influenced text.** Header values, DNS TXT records and URLs are passed unescaped into ReportLab `Paragraph`, which parses mini-HTML. A `<` or `&` in a value can raise an error or inject markup. | `backend/app/reports/pdf_report.py` (all `Paragraph(...)` calls with dynamic text) | 0 |

#### High (correctness and accuracy)

| ID | Problem | Location |
|---|---|---|
| H-1 | **Cookie checks use substring matching.** `"secure" in c.lower()` matches a cookie named `insecure_mode=1`, or any value containing "secure", which gives false passes. `SameSite=None` without `Secure` is not flagged. Cookies set during redirects are ignored. | `scanner/cookies.py:42-44` |
| H-2 | **TLS scanner mis-classifies errors.** `ConnectionResetError`, `OSError` (network unreachable) and `ssl.SSLError` (handshake failure) fall into the generic `except Exception`, which returns `score: 0` without `unreachable: True`. That counts as a real 0, violating I-3. | `scanner/tls.py:29-55` |
| H-3 | **The TLS protocol check can never fail.** Python's default context refuses TLS 1.0/1.1, so a legacy-only server produces a handshake error (see H-2) rather than a "deprecated protocol" finding. The check also doesn't detect whether a modern server *also* still accepts TLS 1.0/1.1. | `scanner/tls.py:93-103` |
| H-4 | **Header checks are presence-only.** `Content-Security-Policy: default-src * 'unsafe-inline' 'unsafe-eval'` passes. So does `Strict-Transport-Security: max-age=0`, and `X-Content-Type-Options: foo`. | `scanner/headers.py` |
| H-5 | **DNS checks are presence-only and use the wrong domain.** `p=none` DMARC counts as full credit, and `+all` SPF passes. Multiple SPF records (a hard error under RFC 7208) are not detected. Subdomains (e.g. `app.example.com`) are checked as if they were the organisational domain, so DMARC/CAA lookups give wrong answers; the code only strips `www.`. DNSSEC is advertised in the README but not implemented. | `scanner/dns_scan.py` |
| H-6 | **Inconclusive checks render as failures.** `passed: null` (inconclusive CAA) shows a red ✗ in the UI. Partial-credit checks (certificate expiring soon) also show ✗. | `frontend/src/components/ScanResult.jsx:6-7` |
| H-7 | **Duplicate `DomainOut` schema.** The second definition silently overrides the first. `ScanResult` and `HeaderCheck` schemas are unused. | `backend/app/schemas.py:38, 82` |
| H-8 | **The domain title renders twice** on the detail page because of a duplicated, nested header block. | `frontend/src/pages/DomainDetail.jsx:92-121` |
| H-9 | **No migrations.** `Base.metadata.create_all()` runs at import time, so schema changes require manual `ALTER TABLE` (already happened once). | `backend/app/main.py:10` |
| H-10 | **Unbounded scan list.** `GET /domains/{id}/scans` returns every scan, JSON-decoding each one. No pagination, and no index on `scans(domain_id, created_at)`. | `scanner/router.py:59-104`, `models.py` |
| H-11 | **No task robustness.** Celery tasks have no time limits, retries or failure persistence. An unexpected exception in any scanner loses the whole scan, and the user's poll times out after 60 s with no explanation. The sweep can enqueue duplicate scans for a domain that is already scanning. | `scanner/tasks.py` |
| H-12 | **Features advertised but missing:** exposed-path checks, regression alerts (email), and DNSSEC. | `README.md` |

#### Medium (product, UX, hygiene)

| ID | Problem |
|---|---|
| M-1 | `backend/requirements.txt` is **UTF-16 LE with CRLF** and mixes dev/test and Windows-only packages (`pytest`, `colorama`) into production dependencies. |
| M-2 | Committed artefacts: `backend/celerybeat-schedule` (beat state DB) and `frontend/.vite/` (Vite cache). Unused template assets: `src/assets/react.svg`, `vite.svg`, `hero.png`, `public/icons.svg`, empty `App.css`. The favicon is the Vite logo, `<title>` is `frontend`, and `frontend/README.md` is the Vite template. |
| M-3 | JWT stored in `localStorage` (readable by any XSS). Tokens last 60 minutes with no refresh, so users are silently logged out mid-session and the client doesn't handle 401s globally. The token `sub` is the email, which breaks if the email changes. |
| M-4 | No email verification, password reset, password change, account deletion or data export. Signup reveals whether an email is registered. Login timing differs for existing vs non-existing users. No server-side password policy (only a client-side `minLength=8`). |
| M-5 | URL normalisation is weak: it doesn't lowercase or IDNA-encode hosts, accepts garbage like `https://`, and allows arbitrary paths and ports. There is no DB-level uniqueness on `(owner_id, url)`. |
| M-6 | No landing page. `/` redirects anonymous visitors straight to `/login`, so there's no way to try the product before signing up. |
| M-7 | The dashboard doesn't show each domain's latest grade or last-scan time. Users have to click into every domain. Delete has no confirmation. There's no 404 route and no error boundary. |
| M-8 | Polling isn't cancelled on unmount (state updates on unmounted components). `downloadReport` duplicates `BASE_URL` and has imports in the middle of the file (`frontend/src/api/domains.js:37-39`). |
| M-9 | Accessibility: emoji used as icons without labels, grade conveyed mostly by colour, labels not bound to inputs (`htmlFor`), the monitoring toggle has no `aria-pressed`, and scan progress has no live region. The theme flashes on load (no pre-paint script). |
| M-10 | Ops: containers run as root, single-process uvicorn, plain-text DB passwords in compose, a beat interval of 120 s in compose (fills history quickly), no structured logs, no error tracking, no readiness checks. CI tests the backend only (on Python 3.13, while docs say 3.14), with no lint, frontend build or Docker build. |
| M-11 | The PDF uses `datetime.utcnow()` (deprecated) and the 🛡 emoji entity, which Helvetica can't render (shows as a box). |

---

## 4. Target architecture

### 4.1 Stack decisions (final; do not re-litigate)

| Layer | Choice | Notes |
|---|---|---|
| Backend framework | **FastAPI** (keep), Pydantic v2, SQLAlchemy 2.0 | Move to `/api/v1` prefix. |
| DB | **PostgreSQL 16** (keep) + **Alembic** | Use `JSONB` for scan categories; SQLite only in unit tests. |
| Jobs | **Celery + Redis** (keep) | Add time limits, retries, `acks_late`, a dedicated `scans` queue, and a single beat instance. |
| Password hashing | **Argon2id via `pwdlib[argon2,bcrypt]`** | Verify existing bcrypt hashes and transparently rehash on login. |
| Rate limiting | **`slowapi`** with Redis storage | Plus a custom per-target cooldown (see 5.1.4). |
| HTTP client | **httpx** (keep) | Manual redirect handling plus the SSRF guard. |
| DNS | **dnspython** (keep) + **`tldextract`** with its bundled snapshot (offline mode) | For the organisational domain. |
| Cert parsing | **`cryptography`** | Key type and size, signature algorithm, SANs, issuer. |
| Email | SMTP via **`aiosmtplib`** or provider HTTP API (Resend/Postmark) behind an `EmailSender` interface | Console backend in dev. |
| Templates | **Jinja2** for email HTML | |
| Logging | **`structlog`** JSON logs with request IDs | |
| Errors | **Sentry** (`sentry-sdk`), enabled only if `SENTRY_DSN` is set | Frontend too (`@sentry/react`). |
| Frontend | **React 19 + Vite + TypeScript** (migrate from JS) | Keep Vite; no Next.js migration. |
| Styling | **Tailwind CSS v4** + **shadcn/ui** (Radix primitives) | CSS-variable design tokens. |
| Server state | **TanStack Query v5** | Replaces hand-rolled fetch and polling. |
| Forms | **react-hook-form + zod** | |
| Icons | **lucide-react** | Replace all emoji icons. |
| Charts | **Recharts** via shadcn `chart` component | Replace Chart.js; theme-aware. |
| Toasts | **sonner** | |
| Motion | **motion** (Framer Motion) | Subtle only; respect `prefers-reduced-motion`. |
| Dates | **date-fns** | Relative times ("3 hours ago") with absolute tooltip. |
| Testing | Backend: pytest, `respx` (httpx mocks), `pytest-cov`, `freezegun`. Frontend: Vitest + Testing Library + MSW; Playwright + `@axe-core/playwright` for e2e/a11y. | |
| Lint/format | Backend: **ruff** (lint + format), optional mypy. Frontend: ESLint (keep flat config) + Prettier + `tsc --noEmit`. | |

### 4.2 Runtime topology (production)

```
                ┌──────────────────────────────────────────────┐
 Browser ──────►│  Reverse proxy (Caddy or Nginx), TLS, HSTS   │
                │   /            → static SPA (built Vite app)  │
                │   /api/*       → FastAPI (gunicorn+uvicorn)   │
                └───────────────┬──────────────────────────────┘
                                │ same origin → no CORS in prod,
                                │ first-party httpOnly refresh cookie
                    ┌───────────▼──────────┐
                    │   FastAPI  (API v1)  │──► PostgreSQL (JSONB scans, findings)
                    └───────────┬──────────┘
                                │ enqueue (scan_jobs row + Celery task)
                         ┌──────▼──────┐
                         │    Redis    │  broker + rate-limit store + cache
                         └──────┬──────┘
           ┌────────────────────┼─────────────────────┐
     ┌─────▼──────┐      ┌──────▼──────┐       ┌──────▼───────┐
     │ worker:    │      │ worker:     │       │ beat (×1)    │
     │ scans queue│      │ notify queue│       │ due-scan     │
     │ (SSRF-safe │      │ (email,     │       │ sweep, cert  │
     │  egress)   │      │  slack, wh) │       │ expiry, digest│
     └────────────┘      └─────────────┘       └──────────────┘
```

### 4.3 Target backend layout

```
backend/
├── alembic.ini
├── migrations/                     # Alembic env + versions
├── pyproject.toml                  # ruff, pytest config
├── requirements.txt                # prod, UTF-8, pinned
├── requirements-dev.txt            # -r requirements.txt + pytest, respx, ruff, ...
└── app/
    ├── main.py                     # app factory, middleware, routers, /health, /ready
    ├── core/
    │   ├── config.py               # Settings (no secret defaults; validated)
    │   ├── logging.py              # structlog setup, request-id middleware
    │   ├── security.py             # hashing, JWT, refresh tokens, API keys
    │   ├── ratelimit.py            # slowapi limiter + target cooldown
    │   └── errors.py               # consistent error envelope
    ├── db/
    │   ├── session.py              # engine, SessionLocal, get_db
    │   └── models/                 # user.py, domain.py, scan.py, finding.py, notification.py, api_key.py
    ├── schemas/                    # pydantic models per resource
    ├── api/v1/
    │   ├── auth.py  users.py  domains.py  scans.py  findings.py
    │   ├── notifications.py  api_keys.py  public.py  badges.py  meta.py
    ├── scanner/
    │   ├── net/                    # ssrf_guard.py, http_fetch.py (shared fetch for headers+cookies)
    │   ├── checks/                 # headers.py tls.py dns.py cookies.py exposure.py transport.py
    │   ├── scoring.py              # weights, caps, grade bands, SCORING_VERSION
    │   ├── engine.py               # orchestrates checks → ScanReport (pure)
    │   └── models.py               # CheckResult, CategoryResult, ScanReport (pydantic)
    ├── knowledge/                  # remediation KB: one YAML per check_id + loader
    ├── services/                   # domain_service, scan_service, finding_service, verification, alerts
    ├── notifications/              # email.py, slack.py, webhook.py, templates/
    ├── reports/pdf_report.py
    ├── tasks/                      # celery_app.py, scan_tasks.py, monitor_tasks.py, notify_tasks.py
    └── tests/
```

### 4.4 Target frontend layout

```
frontend/src/
├── main.tsx  app/router.tsx  app/providers.tsx   # QueryClient, Theme, Auth, Toaster
├── styles/globals.css                            # Tailwind v4 + design tokens
├── lib/  api.ts (typed client)  auth.ts  format.ts  utils.ts (cn)
├── api/  hooks per resource: useDomains.ts, useScan.ts, useFindings.ts ...
├── components/
│   ├── ui/            # shadcn generated primitives (button, card, dialog, tabs, table, ...)
│   ├── brand/         # Logo, LogoMark
│   ├── security/      # GradeBadge, ScoreRing, CategoryBar, SeverityBadge, FindingCard,
│   │                  # RemediationTabs, CodeBlock, ScanProgress, CertificateCard, ScanDiff
│   ├── charts/        # ScoreTrendChart, Sparkline, GradeDistribution
│   └── layout/        # AppShell, Sidebar, Topbar, MobileNav, PublicHeader, Footer, PageHeader
├── pages/
│   ├── public/        # Landing, PublicScanResult, Methodology, BotInfo, Privacy, Terms, NotFound
│   ├── auth/          # Login, Signup, ForgotPassword, ResetPassword, VerifyEmail
│   └── app/           # Overview, Domains, DomainDetail/{Overview,Findings,History,Settings},
│                      # Findings, Alerts, Settings/{Profile,Security,ApiKeys,Danger}
└── test/              # vitest setup, msw handlers, fixtures (real-shaped scan JSON)
```

---

## 5. Phased execution plan

Order matters: **security first** (the platform must not become an attack proxy), then **data model**, then **scanner accuracy**, then **usefulness features**, then the **UI rebuild**, then **ops**. Phases 6–7 (frontend) can run in parallel with Phases 4–5 once the API v1 contract from Phase 2 is frozen.

---

### Phase 0 — Repo hygiene and quick bug fixes

**Branch:** `feature/hygiene-quickfixes`

#### Tasks

1. **Convert `backend/requirements.txt` to UTF-8 with LF.** Split it:
   - `requirements.txt`: runtime only (remove `pytest`, `iniconfig`, `pluggy`, `Pygments`, `colorama`; keep transitive pins produced by `pip-compile` or equivalent).
   - `requirements-dev.txt`: `-r requirements.txt` plus `pytest`, `pytest-cov`, `respx`, `freezegun`, `ruff`.
   - Update `.github/workflows/ci.yml` to install `requirements-dev.txt`.
2. **Remove committed artefacts** and ignore them: `git rm --cached backend/celerybeat-schedule frontend/.vite -r`. Add `celerybeat-schedule*` to `backend/.gitignore` and `.vite/` to `frontend/.gitignore`.
3. **Delete unused template files:** `frontend/src/App.css`, `src/assets/react.svg`, `src/assets/vite.svg`, `src/assets/hero.png`, `public/icons.svg`. Replace `public/favicon.svg` with a SiteShield shield mark (a simple SVG shield with a check). Set `<title>SiteShield — Website security monitoring</title>` and a meta description in `index.html`. Replace `frontend/README.md` with real frontend dev instructions.
4. **Fix H-8:** remove the duplicated header block in `DomainDetail.jsx` (keep one `h1` and one action group).
5. **Fix H-7:** delete the first `DomainOut` and the unused `ScanResult`/`HeaderCheck` schemas in `schemas.py`.
6. **Fix H-6 (interim):** `CheckRow` must render three states: pass (✓, green), fail (✗, red), inconclusive (`passed === null` → "–", grey, "Not scored"). Add a `partial` visual (amber) when the check reports partial credit (add `"partial": true` to the TLS expiry check when 0 < days ≤ 30).
7. **Fix C-5:** in `pdf_report.py`, wrap every dynamic string passed to `Paragraph` with `xml.sax.saxutils.escape()`. Replace `datetime.utcnow()` with `datetime.now(timezone.utc)`. Remove the `&#128737;` emoji from the header (draw a vector shield with the canvas, or use plain text).
8. **Fix M-8:** in `frontend/src/api/domains.js`, move imports to the top and reuse a single exported `BASE_URL` from `client.js`.
9. Add `.editorconfig` (UTF-8, LF, final newline) and a root `Makefile` (or `justfile`) with `make dev`, `make test`, `make lint`, `make fmt`.

#### Acceptance criteria

- `pip install -r backend/requirements-dev.txt` works on Linux. `file backend/requirements.txt` reports UTF-8/ASCII.
- `pytest` passes. A new test, `test_pdf_report_escapes_markup`, generates a report for a scan whose header value contains `<script>&` without raising.
- Detail page shows the domain name exactly once. An inconclusive check renders grey, not red.
- `git ls-files | grep -E "celerybeat|\.vite"` returns nothing.

---

### Phase 1 — Harden the platform itself

**Branch:** `feature/platform-hardening`

#### 1.1 SSRF guard (fixes C-1) — `app/scanner/net/ssrf_guard.py`

Implement a single egress policy that **every** scanner network call goes through.

```python
import ipaddress, socket

ALLOWED_PORTS = {80, 443}

class UnsafeTargetError(Exception):
    """Target resolves to a non-public address or uses a disallowed port/scheme."""

def _is_public(ip: ipaddress._BaseAddress) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast and not ip.is_reserved

def resolve_public(host: str, port: int) -> list[str]:
    if port not in ALLOWED_PORTS:
        raise UnsafeTargetError(f"Port {port} is not allowed")
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise  # caller maps to "unreachable"
    addrs = sorted({info[4][0] for info in infos})
    if not addrs or not all(_is_public(ipaddress.ip_address(a)) for a in addrs):
        raise UnsafeTargetError("Target resolves to a non-public address")
    return addrs
```

Rules:

- **Validate at input time** (domain create, public scan) and **again at scan time** (DNS can change).
- **Redirects:** set `follow_redirects=False` and follow manually, up to 5 hops. Validate the scheme (`http`/`https` only), port and resolved IPs of **every hop**.
- **Post-connect verification:** after each request, read the peer address via `response.extensions["network_stream"].get_extra_info("server_addr")` and reject the response if that IP is not public. This defeats DNS rebinding between the check and the connection.
- TLS scanner: resolve with `resolve_public`, then `socket.create_connection((ip, 443))` with `server_hostname=host` for SNI and verification.
- Reject hosts that are bare IP literals, `localhost`, single-label names (`redis`, `postgres`), and names ending in `.local`, `.internal`, `.localhost`, `.home.arpa`.
- Cap the response body read at 1 MB (stream and stop). Use a 10 s total timeout per request.
- Use the User-Agent `SiteShieldBot/2.0 (+https://<public-host>/bot)`.

#### 1.2 Shared HTTP fetch — `app/scanner/net/http_fetch.py`

The headers and cookie scanners currently fetch the same URL twice. Create `fetch_target(url) -> FetchResult` that performs one SSRF-safe GET (with manual redirects) and returns: the redirect chain (url, status, headers per hop), final URL, final headers (as a multi-dict), all `Set-Cookie` headers across hops, peer IP, timing, and a truncated body (for exposure/security.txt checks only). Both scanners consume this result. **This also preserves I-5:** the fetch happens in the engine, and the check functions stay pure functions of `FetchResult`.

#### 1.3 Scan job ownership (fixes C-2)

- New table `scan_jobs` (see 5.2.1). `POST /api/v1/domains/{id}/scans` creates a `ScanJob` row (status `queued`, `requested_by_user_id`) and passes its UUID to Celery.
- `GET /api/v1/scan-jobs/{job_id}` reads the **DB row**, joined to the domain, filtered by owner. It never calls `AsyncResult` with a user-supplied id.
- The worker updates `scan_jobs.status`, `progress` (per-category state), `error`, `started_at`, `finished_at` and `scan_id`.

#### 1.4 Rate limiting and abuse prevention (fixes C-4)

| Endpoint | Limit (key) |
|---|---|
| `POST /auth/login` | 5/min and 20/hour per IP; 10/hour per email |
| `POST /auth/signup` | 5/hour per IP |
| `POST /auth/forgot-password` | 3/hour per email, 10/hour per IP |
| `POST /public/scans` (anonymous) | 5/hour per IP |
| `POST /domains/{id}/scans` | 30/hour per user |
| API-key scans | 60/hour per key |

- **Per-target cooldown (protects third parties):** any target hostname is scanned at most once per 5 minutes across the whole platform. If a fresh result exists, return it (`"cached": true`) instead of rescanning. Implement with a Redis key `scan:cooldown:<hostname>`.
- **Opt-out list:** table `scan_opt_outs(hostname)`. Scans of opted-out hostnames are refused with a clear message. The `/bot` page explains how a site owner can request opt-out (contact email from settings).
- Return `429` with a `Retry-After` header. The frontend shows a friendly toast with the wait time.

#### 1.5 Auth hardening (fixes C-3, M-3, M-4)

1. **Config:** `jwt_secret` has **no default**. Settings validation fails at startup if it is missing or shorter than 32 bytes when `ENV=production`. Add `ENV` (`development`/`test`/`production`), `PUBLIC_BASE_URL`, `COOKIE_DOMAIN`, `EMAIL_FROM`, SMTP settings and `SENTRY_DSN`. Provide `backend/.env.example` with every variable documented and no real secrets.
2. **Tokens:**
   - Access token: JWT, 15 minutes, `sub = str(user.id)`, plus `type: "access"`. Returned in the JSON body and kept **in memory** on the frontend (not localStorage).
   - Refresh token: random 256-bit opaque token, stored **hashed** (SHA-256) in `refresh_tokens`. Sent as an `httpOnly; Secure; SameSite=Lax; Path=/api/v1/auth` cookie, 30 days. **Rotate on every refresh**; if a revoked token is reused, revoke the user's whole token family.
   - `POST /auth/refresh` and `POST /auth/logout` (revokes the current refresh token). Add "log out all sessions" in settings.
   - CSRF: refresh/logout are cookie-authenticated, so require a custom header (`X-Requested-With: SiteShield`) and check `Origin` against `PUBLIC_BASE_URL`.
3. **Passwords:** Argon2id via `pwdlib`; verify legacy bcrypt and rehash on successful login. Server-side policy: 10–128 characters, reject the top 10k common passwords (bundle a list file). Show a strength meter in the UI.
4. **Enumeration and timing:** signup returns the same response whether or not the email exists (send "you already have an account" email instead). Login always runs a hash verification, against a dummy hash when the user doesn't exist.
5. **Email verification:** a signed single-use token (stored hashed, 24 h expiry). Unverified users can log in and run on-demand scans, but cannot enable monitoring or alerts until verified. Show a persistent banner.
6. **Password reset:** request → email link (token hashed, 30 min, single use) → set new password → revoke all refresh tokens.
7. **Account management:** change email (re-verify), change password, delete account (typed confirmation; cascades), and export data (JSON of domains, scans, findings).

#### 1.6 Security headers on the API

Add middleware setting `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` on authenticated responses, and a strict CSP of `default-src 'none'; frame-ancestors 'none'` on JSON responses. In production, disable `/docs` and `/openapi.json` or put them behind auth (configurable).

#### Acceptance criteria

- New tests in `tests/test_ssrf.py` cover: `localhost`, `127.0.0.1`, `[::1]`, `10.0.0.5`, `169.254.169.254`, `redis`, `metadata.google.internal`, a hostname whose mock DNS returns a private IP, a public URL that 302-redirects to `http://127.0.0.1`, port `:6379`, `file://` and `gopher://` schemes. All are rejected at input or scan time without any socket connection to the internal address. Use monkeypatched `getaddrinfo` and `respx`.
- User B gets 404 for user A's scan job id.
- The app refuses to start with `ENV=production` and no `JWT_SECRET`.
- The 6th login attempt within a minute gets 429.
- Refresh rotation works; reuse of an old refresh token revokes the whole family (tested).
- Existing bcrypt users can still log in and are rehashed to Argon2 (tested).

---

### Phase 2 — Data model, migrations, API v1

**Branch:** `feature/data-model-v1`

#### 2.1 Alembic

1. Add Alembic. Create migration `0001_baseline` matching the **current** production schema exactly (users, domains with `monitoring_enabled`, scans with `results_json` Text). Document `alembic stamp 0001_baseline` for existing databases.
2. Remove `Base.metadata.create_all()` from `main.py`. The backend container entrypoint runs `alembic upgrade head` before starting gunicorn. Tests use `create_all` on SQLite or, preferably, run migrations against a Postgres service in CI.

#### 2.2 Schema (migration `0002_v1_schema`)

```text
users
  id PK, email CITEXT UNIQUE NOT NULL, password_hash, email_verified_at NULL,
  display_name NULL, timezone DEFAULT 'UTC', is_active DEFAULT true,
  last_login_at NULL, created_at, updated_at

refresh_tokens
  id PK, user_id FK→users ON DELETE CASCADE, family_id UUID, token_hash UNIQUE,
  created_at, expires_at, revoked_at NULL, user_agent, ip

email_tokens
  id PK, user_id FK, purpose ENUM('verify_email','reset_password','change_email'),
  token_hash UNIQUE, payload JSONB NULL, expires_at, used_at NULL, created_at

domains
  id PK, owner_id FK→users ON DELETE CASCADE,
  hostname VARCHAR(253) NOT NULL       -- lowercased, IDNA/punycode, no port
  display_url VARCHAR(512) NOT NULL    -- canonical https://hostname
  label VARCHAR(100) NULL              -- user nickname, e.g. "Client: Acme shop"
  verification_token VARCHAR(64), verified_at NULL, verification_method NULL,
  last_verification_check_at NULL,
  monitoring_schedule ENUM('off','daily','weekly') DEFAULT 'off',
  next_scan_at TIMESTAMPTZ NULL,
  latest_scan_id FK→scans NULL         -- denormalised for fast dashboard
  public_badge_enabled BOOL DEFAULT false, badge_token VARCHAR(32) UNIQUE NULL,
  created_at, updated_at
  UNIQUE(owner_id, hostname)
  INDEX(next_scan_at) WHERE monitoring_schedule <> 'off'

scan_jobs
  id UUID PK, domain_id FK NULL ON DELETE CASCADE, requested_by_user_id FK NULL,
  source ENUM('manual','scheduled','public','api'), target_hostname,
  status ENUM('queued','running','succeeded','failed') , progress JSONB,
  error TEXT NULL, celery_task_id, scan_id FK NULL,
  created_at, started_at NULL, finished_at NULL
  INDEX(domain_id, created_at DESC)

scans
  id PK, public_id UUID UNIQUE         -- unguessable share id
  domain_id FK NULL ON DELETE CASCADE  -- NULL for anonymous public scans
  target_hostname, final_url, grade VARCHAR(3), score SMALLINT,
  scoring_version SMALLINT NOT NULL,
  categories JSONB NOT NULL,           -- full structured report
  summary JSONB                        -- counts by severity, top issues
  duration_ms INT, is_shared BOOL DEFAULT false, expires_at NULL,
  created_at
  INDEX(domain_id, created_at DESC)

findings                               -- lifecycle tracking across scans
  id PK, domain_id FK ON DELETE CASCADE, check_id VARCHAR(100),
  severity ENUM('critical','high','medium','low','info'),
  status ENUM('open','resolved','accepted_risk'),
  evidence JSONB, first_seen_scan_id FK, last_seen_scan_id FK, resolved_scan_id FK NULL,
  first_seen_at, last_seen_at, resolved_at NULL, note TEXT NULL
  UNIQUE(domain_id, check_id) WHERE status <> 'resolved'
  INDEX(domain_id, status)

notification_channels
  id PK, user_id FK, type ENUM('email','slack','webhook'), name,
  config JSONB (encrypted secret fields with Fernet key from settings),
  is_verified, is_enabled, created_at

alert_preferences (1:1 users, optional per-domain override table later)
  user_id PK FK, grade_drop BOOL DEFAULT true, new_high_or_critical BOOL DEFAULT true,
  cert_expiry_days INT[] DEFAULT '{30,14,7,1}', unreachable BOOL DEFAULT true,
  weekly_digest BOOL DEFAULT true

notifications
  id PK, user_id FK, domain_id FK NULL, channel_id FK NULL, kind, payload JSONB,
  dedupe_key UNIQUE, status ENUM('pending','sent','failed'), error NULL,
  created_at, sent_at NULL

api_keys
  id PK, user_id FK, name, prefix VARCHAR(12), key_hash UNIQUE,
  scopes TEXT[] DEFAULT '{scans:read,scans:write}', last_used_at NULL,
  created_at, revoked_at NULL

scan_opt_outs
  hostname PK, reason, created_at
```

**Data migration in `0002`:**

- `domains.hostname` ← parsed, lowercased host from `url`; `display_url` ← `https://<hostname>`; `monitoring_schedule` ← `'daily'` if `monitoring_enabled` else `'off'`. Drop `monitoring_enabled`. On duplicate `(owner_id, hostname)` keep the oldest row and re-point its scans.
- `scans.categories` ← `results_json` parsed **only** when it is a dict with category keys. Legacy flat-list scans get `{"legacy": true}` and `scoring_version = 0`. Assign `scoring_version = 1` to the existing 4-category scans and generate a `public_id` for every row. Drop `results_json`.
- Set `domains.latest_scan_id`.

#### 2.3 API v1 contract

All routes live under `/api/v1`. Errors use one envelope: `{"error": {"code": "domain_not_found", "message": "Domain not found", "details": {...}}}`. List endpoints are cursor-paginated: `?limit=20&cursor=<opaque>` → `{"items": [...], "next_cursor": "..."}`. Timestamps are ISO-8601 with an offset (UTC). This removes the old `+"Z"` problem permanently.

| Method & path | Purpose |
|---|---|
| `POST /auth/signup` · `POST /auth/login` · `POST /auth/refresh` · `POST /auth/logout` · `POST /auth/logout-all` | Session lifecycle |
| `POST /auth/verify-email` · `POST /auth/resend-verification` · `POST /auth/forgot-password` · `POST /auth/reset-password` | Email flows |
| `GET /users/me` · `PATCH /users/me` · `POST /users/me/password` · `DELETE /users/me` · `GET /users/me/export` | Account |
| `GET /domains?search=&grade=&schedule=&sort=` | List **with latest scan summary and a 10-point sparkline** per domain |
| `POST /domains` (single) · `POST /domains/bulk` (≤ 50 hostnames, returns per-row result) | Add |
| `GET /domains/{id}` · `PATCH /domains/{id}` (label, schedule, badge) · `DELETE /domains/{id}` | Manage |
| `POST /domains/{id}/verify` (method: `dns_txt` \| `http_file` \| `meta_tag`) · `GET /domains/{id}/verification` | Ownership verification |
| `POST /domains/{id}/scans` → `202 {job}` | Start a scan |
| `GET /scan-jobs/{job_id}` | Job status and live per-category progress |
| `GET /domains/{id}/scans?cursor=` | History (summary only, no full categories) |
| `GET /scans/{scan_id}` | Full report (owner-scoped) |
| `GET /scans/{a}/diff/{b}` | Structured diff: score delta, findings added/resolved, changed values |
| `POST /scans/{scan_id}/share` · `DELETE /scans/{scan_id}/share` | Toggle a public share link |
| `GET /domains/{id}/report.pdf?scan_id=` | PDF report |
| `GET /findings?status=open&severity=&domain_id=` | Cross-domain findings, sorted by score impact |
| `PATCH /findings/{id}` (status `accepted_risk` + note, or reopen) | Triage |
| `GET /overview` | Dashboard KPIs, top fixes, recent activity, certs expiring |
| `GET/POST/PATCH/DELETE /notification-channels` · `POST /notification-channels/{id}/test` | Alert channels |
| `GET/PUT /alert-preferences` · `GET /notifications?cursor=` | Alert rules and history |
| `GET/POST/DELETE /api-keys` | API keys (secret shown once) |
| `POST /public/scans` (anonymous, rate limited) · `GET /public/scans/{public_id}` | Instant scan and share page |
| `GET /public/badge/{badge_token}.svg` | Status badge |
| `GET /meta/checks` | The full catalogue of checks and remediation (for the Methodology page) |
| `GET /health` (liveness) · `GET /ready` (DB + Redis reachable) | Ops |

Generate a **typed TypeScript client** from the OpenAPI schema (`openapi-typescript` → `frontend/src/lib/api-types.ts`). Add an npm script `gen:api` and a CI check that the generated file is up to date.

#### Acceptance criteria

- `alembic upgrade head` from an empty DB and from a DB at `0001_baseline` (seeded with legacy and v1 scans) both succeed. A migration test covers this.
- Every v1 route has at least one happy-path and one authorisation test (foreign user → 404).
- The dashboard list endpoint returns 50 domains with summaries in **≤ 3 SQL queries** (assert with a query-count fixture).

---

### Phase 3 — Scanner engine v2

**Branch:** `feature/scanner-v2`

#### 3.1 Result model (`app/scanner/models.py`)

```python
class CheckResult(BaseModel):
    check_id: str                 # stable id, e.g. "headers.csp.unsafe_inline" — joins to the KB
    category: Literal["transport","headers","cookies","dns","exposure"]
    status: Literal["pass","partial","fail","inconclusive","info"]
    severity: Literal["critical","high","medium","low","info"]   # severity if not passing
    weight: int                   # max points within its category
    points: float                 # awarded points (0..weight); ignored if inconclusive/info
    title: str                    # short, human: "HSTS max-age is too short"
    detail: str                   # what we observed, plain language
    evidence: dict = {}           # raw observed values (header value, record text, days_left…)

class CategoryResult(BaseModel):
    category: str
    status: Literal["measured","unreachable","skipped"]
    score: int | None             # 0–100 normalised over non-inconclusive checks
    checks: list[CheckResult]
    error: str | None = None

class ScanReport(BaseModel):
    scoring_version: int
    target_hostname: str
    final_url: str | None
    grade: str                    # A+..F or "N/A"
    score: int | None
    caps_applied: list[str]       # e.g. ["critical:transport.cert.expired"]
    categories: dict[str, CategoryResult]
    duration_ms: int
```

The engine runs the checks **concurrently** (a thread pool, or asyncio with `httpx.AsyncClient`), each with its own timeout. It reports per-category progress to `scan_jobs.progress` so the UI can show real progress. An exception inside one check marks **that check** `inconclusive` with `error` and is logged to Sentry. It never fails the whole scan.

#### 3.2 Categories and checks (SCORING_VERSION = 2)

Category weights (re-normalised over measured categories, invariant I-3):

| Category | Weight | Notes |
|---|---|---|
| Transport & TLS | 30 | merges the old TLS category + HTTPS enforcement |
| HTTP security headers | 30 | value-quality checks |
| DNS & email security | 15 | |
| Cookies | 10 | `status=skipped` with score 100 if no cookies are set |
| Exposure | 15 | security.txt for all; sensitive-file probes only for **verified** domains; otherwise `skipped` and excluded |

**Grade bands:** `A+ ≥ 97 with no medium-or-worse findings`, `A ≥ 90`, `B ≥ 75`, `C ≥ 60`, `D ≥ 40`, `E ≥ 20`, `F < 20`, `N/A` if nothing could be measured.

**Grade caps** (like SSL Labs; makes grades honest). After computing the score, apply the lowest applicable cap:

| Condition | Max grade |
|---|---|
| Certificate invalid, expired or hostname mismatch | **F** |
| Exposed `.git/` or `.env` (verified domains only) | **F** |
| Site doesn't redirect HTTP → HTTPS **and** has no HSTS | **C** |
| TLS 1.0 or 1.1 still accepted | **B** |
| Certificate expires in < 7 days | **C** |

Record applied caps in `caps_applied` and show them in the UI ("Grade capped at C because…").

##### Transport & TLS (`checks/tls.py`, `checks/transport.py`)

| check_id | What | Scoring |
|---|---|---|
| `transport.https.available` | TLS handshake on 443 succeeds | 0 → see caps |
| `transport.cert.trusted` | Chain verifies against certifi/system store | critical if fail |
| `transport.cert.hostname` | Hostname matches the SANs | critical if fail |
| `transport.cert.expiry` | days_left > 30 pass; 14–30 partial (60%); 1–13 fail (high); ≤ 0 critical | weight 20 |
| `transport.cert.key_strength` | RSA ≥ 2048 or EC ≥ 256 (parse with `cryptography`) | medium |
| `transport.cert.signature` | Not SHA-1/MD5 | high |
| `transport.tls.legacy_disabled` | Attempt separate handshakes pinned to TLS 1.0 and 1.1 (`ctx.minimum_version = ctx.maximum_version = TLSVersion.TLSv1`, `ctx.set_ciphers("DEFAULT:@SECLEVEL=0")`). Accepted → fail (high). If the local OpenSSL can't even offer that version → `inconclusive`, **not** pass. | weight 15 |
| `transport.tls.v1_3` | TLS 1.3 supported | low; partial credit |
| `transport.http.redirects_to_https` | `http://host/` final hop is `https://` on the same registrable domain | high |
| `transport.hsts.preload_ready` | (info) HSTS has `max-age ≥ 31536000; includeSubDomains; preload` | info, not scored |

Return evidence the UI needs for a **certificate card**: issuer, subject/SANs (first 10), not_before/not_after, days_left, key type/size, protocol versions accepted.

Error mapping (fixes H-2): DNS failure, connection refused or timeout, or `UnsafeTargetError` → category `unreachable`. A handshake that fails because the server only speaks legacy protocols is detected by the legacy probes and reported as a finding.

##### HTTP security headers (`checks/headers.py`) — parse values (fixes H-4)

| check_id | Pass | Partial | Fail |
|---|---|---|---|
| `headers.hsts` | `max-age ≥ 15552000` (180 d) | `max-age` 1 d–180 d | missing, `max-age=0`, or malformed |
| `headers.csp.present` | `Content-Security-Policy` present | only `-Report-Only` present | missing |
| `headers.csp.script_safety` | `script-src` (or `default-src` fallback) has no `'unsafe-inline'` (unless a nonce/hash is also present, which neutralises it in CSP2+), no `'unsafe-eval'`, no `*`, `http:`, `https:` or `data:` wildcards | one weakness | two or more |
| `headers.csp.object_src` | `object-src 'none'` (or `default-src 'none'`) | — | missing (low) |
| `headers.csp.base_uri` | `base-uri` set | — | missing (low) |
| `headers.framing` | `X-Frame-Options: DENY/SAMEORIGIN` **or** CSP `frame-ancestors` | — | neither (medium) |
| `headers.xcto` | exactly `nosniff` | — | missing or wrong |
| `headers.referrer_policy` | `no-referrer`, `same-origin`, `strict-origin`, `strict-origin-when-cross-origin` | `origin`, `origin-when-cross-origin` | missing, `unsafe-url`, `no-referrer-when-downgrade` |
| `headers.permissions_policy` | present and non-empty | — | missing (low) |
| `headers.coop` | `Cross-Origin-Opener-Policy: same-origin` | `same-origin-allow-popups` | missing (low weight) |
| `headers.info_leak` | no version numbers in `Server`, no `X-Powered-By`, no `X-AspNet-Version` | — | leak present (low) |

Write a small, well-tested CSP parser (`directive → list[source]`, case-insensitive directive names, handles multiple policies separated by commas). Evaluate headers on the **final** response, and also check HSTS on the first HTTPS hop.

##### Cookies (`checks/cookies.py`) — parse properly (fixes H-1)

- Collect `Set-Cookie` from **every hop** of the redirect chain.
- Parse each header: the first `name=value` pair before `;`, then attributes split on `;`, trimmed, with attribute names compared case-insensitively. **Discard values immediately** (I-6).
- Per-cookie evidence (shown as a table in the UI): name, Secure, HttpOnly, SameSite (`Strict`/`Lax`/`None`/missing), Path, Domain, persistent vs session, `__Host-`/`__Secure-` prefix.
- Checks: `cookies.secure` (all cookies over HTTPS have Secure), `cookies.httponly` (all cookies that *look like sessions* — name matches `sess|sid|auth|token|jwt|login` or has no Expires — are HttpOnly; other cookies → info only), `cookies.samesite` (explicit SameSite on all), `cookies.samesite_none_without_secure` (high), `cookies.prefix_rules` (`__Host-` must be Secure, Path=/, no Domain).
- Score proportionally (e.g. 3/4 cookies Secure → 75% of that check's weight) instead of all-or-nothing, and state the count in `detail`.

##### DNS & email (`checks/dns.py`) — fixes H-5

- Compute the **organisational domain** with `tldextract.TLDExtract(suffix_list_urls=())` (offline, bundled snapshot). Query email records on the org domain. Note "checked on example.com" in `detail` when the scanned host is a subdomain.
- `dns.spf.present`; `dns.spf.single` (more than one `v=spf1` record → fail, high); `dns.spf.policy` (`-all` pass, `~all` partial, `?all`/`+all`/no `all` → fail). Optional `dns.spf.lookup_count` (> 10 DNS-querying mechanisms → medium).
- `dns.dmarc.present`; `dns.dmarc.policy` (`p=reject` pass, `p=quarantine` partial 75%, `p=none` partial 25% with "monitoring only" wording); `dns.dmarc.reporting` (`rua=` present, info).
- **Non-sending domains:** if the org domain has **no MX**, recommend `v=spf1 -all` + `p=reject` (a parked/no-mail pattern) in the remediation text. Don't score MX itself.
- `dns.caa`: climb from the host up to the org domain (RFC 8659 tree-climbing). Keep the existing "query failed → inconclusive" behaviour.
- `dns.dnssec` (low weight): the org domain has a DS record at the parent **and** DNSKEY records. A failed query → inconclusive.
- Use explicit resolvers configurable via settings (default `1.1.1.1`, `8.8.8.8`), lifetime 5 s per query, and cache per scan.

##### Exposure (`checks/exposure.py`)

- **All domains:** `exposure.security_txt`, a GET to `/.well-known/security.txt`. Pass if it returns 200, `text/plain`, contains `Contact:` and an unexpired `Expires:` (RFC 9116). Missing → low severity. Expired → medium.
- **Verified domains only** (respects the owner-only spirit of the ethics statement): a fixed, small list of GETs with strict content signatures to avoid soft-404 false positives:
  - `/.git/HEAD` → body matches `^ref: refs/` → **critical**
  - `/.env` → `text/plain`-ish, not HTML, ≥ 2 lines matching `^[A-Z_][A-Z0-9_]*=` → **critical**
  - `/.DS_Store` → starts with bytes `\x00\x00\x00\x01Bud1` → medium
  - `/server-status` → contains `Apache Server Status` → medium
  - Before the probes, request a random path (`/siteshield-<uuid>`). If it returns 200 with the same body length as a probe, treat that probe as a soft 404 (pass).
  - Max 6 requests per scan, sequential, 5 s timeout each. Never follow links, never crawl.
- Unverified domains: category `skipped` with a CTA "Verify ownership to enable exposure checks".

#### 3.3 Scoring (`app/scanner/scoring.py`)

- `SCORING_VERSION = 2` constant. Category score = `sum(points) / sum(weight of non-inconclusive, non-info checks) * 100`. Overall = weighted mean over `measured` categories. Then apply caps, then the band.
- Expose `score_impact(check)`: how many overall points fixing this check would gain, given current category weights. The "Top fixes" ranking uses this.
- **Golden tests:** `tests/scanner/golden/*.json` fixtures (fake fetch results, DNS answers, cert info) → expected `ScanReport`. Include at least: a perfect site (A+), a bare site (F), an expired cert (cap F), a CSP with `unsafe-inline` and a nonce (no penalty), `p=none` DMARC, a subdomain using org-domain DMARC, all categories unreachable (N/A), CAA inconclusive, and a cookie named `insecure=1` without the Secure flag (must **fail**).

#### 3.4 Celery hardening (fixes H-11)

- `task_acks_late=True`, `worker_prefetch_multiplier=1`, `task_time_limit=90`, `task_soft_time_limit=75`, `result_expires=3600`, separate queues `scans` and `notify`, `--max-tasks-per-child=200`.
- `run_scan(job_id)` is `bind=True`, with `autoretry_for=(OperationalError,)` for DB blips only (never retry scans on target errors). On soft time limit, persist partial results with the timed-out categories marked unreachable.
- **Dedupe:** do not enqueue if the domain has a `queued` or `running` job younger than 5 minutes. Return the existing job instead.
- After persisting a scan: update `domains.latest_scan_id`, run the findings lifecycle (Phase 5), and enqueue notification evaluation.

#### Acceptance criteria

- All golden tests pass, and the network is fully mocked (no real DNS/HTTP in unit tests). Mark the opt-in real-network smoke tests with `@pytest.mark.network`; CI skips them.
- A manual smoke run against `github.com`, `expired.badssl.com`, `tls-v1-0.badssl.com:1010` (the port is blocked by policy, so expect **unreachable** — this verifies the guard), `example.com` and a subdomain (`docs.github.com`) produces sensible output. Record the results in the PR.
- Scanning never takes longer than 30 s at p95 in local tests.

---

### Phase 4 — Remediation knowledge base

**Branch:** `feature/remediation-kb`

This is the single biggest lever for usefulness. Every `check_id` the engine can emit must have a KB entry.

#### 4.1 Format — one YAML file per check in `backend/app/knowledge/checks/`

```yaml
id: headers.hsts
title: Enforce HTTPS with HTTP Strict-Transport-Security
category: headers
severity_if_failed: high
effort: low            # low (<15 min) | medium (<2 h) | high
summary: >
  HSTS tells browsers to only ever connect to your site over HTTPS, which
  blocks protocol-downgrade and cookie-hijacking attacks on public Wi-Fi.
why_it_matters: >
  Without HSTS, the first request a visitor makes can be intercepted and
  redirected to a fake HTTP version of your site.
how_to_fix:
  - Make sure every page and subdomain already works over HTTPS.
  - Add the header below with a short max-age (e.g. 300) first, confirm nothing breaks,
    then raise it to one year.
snippets:
  nginx: |
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
  apache: |
    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"
  caddy: |
    header Strict-Transport-Security "max-age=31536000; includeSubDomains"
  cloudflare: |
    Dashboard → SSL/TLS → Edge Certificates → HTTP Strict Transport Security (HSTS) → Enable.
  vercel: |
    // vercel.json
    { "headers": [ { "source": "/(.*)", "headers": [
      { "key": "Strict-Transport-Security", "value": "max-age=31536000; includeSubDomains" } ] } ] }
  netlify: |
    # _headers
    /*
      Strict-Transport-Security: max-age=31536000; includeSubDomains
  express: |
    // npm i helmet
    app.use(helmet.hsts({ maxAge: 31536000, includeSubDomains: true }));
  nextjs: |
    // next.config.js
    module.exports = { async headers() { return [{ source: '/:path*', headers: [
      { key: 'Strict-Transport-Security', value: 'max-age=31536000; includeSubDomains' } ] }] } };
  iis: |
    <!-- web.config → system.webServer -->
    <httpProtocol><customHeaders>
      <add name="Strict-Transport-Security" value="max-age=31536000; includeSubDomains" />
    </customHeaders></httpProtocol>
verify: curl -sI https://YOUR-DOMAIN | grep -i strict-transport-security
pitfalls:
  - includeSubDomains breaks any subdomain that is still HTTP-only.
  - Only add `preload` once you're sure; removal from browser preload lists takes months.
references:
  - title: MDN — Strict-Transport-Security
    url: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Strict-Transport-Security
  - title: OWASP HTTP Headers Cheat Sheet
    url: https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html
```

Rules:

- Load and validate all files with a Pydantic model at startup (fail fast on a schema error).
- **Test:** `test_every_check_has_kb_entry` iterates over a registry of all check ids the engine can emit and asserts each has a KB entry with at least `nginx`, `apache`, `cloudflare` (where applicable) and `verify`.
- Snippets must be **correct and conservative**. CSP snippets start with a `Content-Security-Policy-Report-Only` rollout recommendation, never a policy that would break sites if pasted blindly.
- DNS entries give the record type, host and value (e.g. `TXT  _dmarc  v=DMARC1; p=quarantine; rua=mailto:dmarc@YOUR-DOMAIN`) plus registrar-agnostic steps.
- Snippets use the placeholder `YOUR-DOMAIN`. The frontend substitutes the actual hostname.
- Writing style: plain English, second person, no fear-mongering, at most 2 sentences for the summary.

#### 4.2 Platform detection (makes snippets personal)

Using the fetch result, infer a likely platform: the `Server` header (`nginx`, `Apache`, `cloudflare`, `Vercel`, `Netlify`), `x-vercel-id`, `x-nf-request-id`, `cf-ray`, `x-powered-by: Express` / `Next.js`. Store it as `evidence.platform_guess` with a confidence level. The UI pre-selects that tab in `RemediationTabs` ("Looks like you're on Cloudflare"), and the user can switch tabs. Users can also set a preferred platform per domain in Settings.

#### Acceptance criteria

- `GET /meta/checks` returns the full catalogue. KB coverage test passes. Each finding returned by `GET /scans/{id}` embeds (or references) its KB entry.

---

### Phase 5 — Monitoring, findings lifecycle, alerts

**Branch:** `feature/monitoring-alerts`

#### 5.1 Ownership verification

- `verification_token`: 32 random hex chars, generated when the domain is added.
- Methods (any one passes):
  1. **DNS TXT** at `_siteshield.<hostname>` with value `siteshield-verification=<token>`
  2. **HTTP file** `https://<hostname>/.well-known/siteshield-verification.txt` containing the token
  3. **Meta tag** `<meta name="siteshield-verification" content="<token>">` on the home page
- Re-check weekly. After 3 consecutive failures, clear `verified_at` and notify the owner.
- **What verification unlocks:** daily scheduling (unverified domains are limited to weekly), exposure probes, public badge, and a "Verified owner" stamp on PDFs. On-demand scans work for everyone.

#### 5.2 Scheduling

- Beat runs `enqueue_due_scans` every 5 minutes: `SELECT … FROM domains WHERE monitoring_schedule <> 'off' AND next_scan_at <= now() ORDER BY next_scan_at LIMIT 200 FOR UPDATE SKIP LOCKED`. Enqueue each, then set `next_scan_at = now() + interval + random jitter (0–30 min)`.
- Production default interval: daily = 24 h, weekly = 7 d. Remove the 120 s interval from compose (use `SCAN_SWEEP_SECONDS=300` for the sweep cadence only).
- Separate beat jobs: `verify_domains_weekly`, `send_weekly_digests` (Monday 08:00 in the user's timezone), `purge_expired_public_scans` (daily).

#### 5.3 Findings lifecycle (`services/finding_service.py`)

After each scan of a domain:

- For each non-passing, non-inconclusive check: upsert an `open` finding (`first_seen` on create, update `last_seen`, `evidence`, `severity`).
- For each open finding whose check now **passes**: mark it `resolved` (`resolved_scan_id`, `resolved_at`).
- Inconclusive results **don't** resolve or open findings (I-3).
- `accepted_risk` findings stay accepted while they keep failing. They are hidden from "Top fixes" but **still count in the score** (honesty). If they get fixed, they become `resolved`.

#### 5.4 Alerts (`services/alerts.py`, `tasks/notify_tasks.py`)

| Alert | Trigger | Dedupe key |
|---|---|---|
| Grade dropped | New grade is lower than the previous scan's (same scoring_version) | `grade_drop:{domain}:{scan}` |
| New high/critical finding | A finding with severity ≥ high is created | `finding:{finding_id}` |
| Certificate expiring | `days_left` crosses 30/14/7/1 (configurable) | `cert:{domain}:{not_after}:{threshold}` |
| Site unreachable | 2 consecutive scheduled scans with all categories unreachable | `unreachable:{domain}:{date}` |
| Recovered | Grade back to the previous level or better / site reachable again | `recover:{domain}:{scan}` |
| Weekly digest | Monday: per-domain grade, changes this week, top 3 fixes | `digest:{user}:{iso_week}` |

- Channels: **email** (default, to the verified address), **Slack incoming webhook**, **generic webhook** (JSON body, `X-SiteShield-Signature: sha256=<HMAC>` header using a per-channel secret, 3 retries with exponential backoff).
- Webhook and Slack URLs go through the SSRF guard (443 only, public IPs).
- Email templates (Jinja2, responsive, light/dark friendly, plain-text alternative): verification, password reset, alert, digest. Every email has a footer with "Manage alerts" and a one-click unsubscribe (signed link, RFC 8058 `List-Unsubscribe-Post`).
- Never send more than 10 alert emails per user per day. Collapse the excess into the digest.

#### 5.5 Scan diff (`GET /scans/{a}/diff/{b}`)

Returns: score/grade delta, category deltas, `findings_added`, `findings_resolved`, `changed_evidence` (e.g. `headers.csp` value before/after, cert `not_after` before/after). It refuses to compare across different `scoring_version`s unless `?force=1` is passed, in which case it warns.

#### Acceptance criteria

- Tests cover: verification via each method (mocked), schedule picks only due domains, jitter applied, no double enqueue, lifecycle open→resolved, accepted_risk persistence, every alert trigger and its dedupe, webhook HMAC signature, unsubscribe link.
- Dev uses a console email backend that prints emails. A Mailpit container in compose shows emails at `http://localhost:8025`.

---

### Phase 6 — Frontend foundation and design system

**Branch:** `feature/frontend-foundation`

#### 6.1 Tooling migration

1. Convert to **TypeScript** (`tsconfig` strict). Rename files `.jsx → .tsx`, starting with leaf components. Use path alias `@/` → `src/`.
2. Upgrade to **Tailwind v4** (`@tailwindcss/vite` plugin; remove `postcss.config.js`/`tailwind.config.js` in favour of CSS-first config) and initialise **shadcn/ui**. Add components: `button card badge input label textarea select checkbox switch tabs table dialog alert-dialog dropdown-menu sheet tooltip popover command skeleton separator progress sonner chart avatar breadcrumb pagination scroll-area`.
3. Add TanStack Query, react-hook-form, zod, lucide-react, sonner, motion, date-fns, recharts (via shadcn chart). Remove `chart.js` and `react-chartjs-2`.
4. Typed API client (`src/lib/api.ts`) using the generated OpenAPI types:
   - Keeps the access token **in memory**. On 401, calls `/auth/refresh` once (single-flight), retries the request, and on failure clears auth and redirects to `/login?next=...`.
   - Sends `credentials: "include"` for auth routes and `X-Requested-With: SiteShield`.
   - Normalises the error envelope into `ApiError { code, message, status, details }`.
5. Polling via `useQuery({ refetchInterval: (q) => isTerminal(q.state.data) ? false : 1500 })`. It cancels automatically on unmount (fixes M-8).
6. Add a global `ErrorBoundary` with a friendly fallback, a `NotFound` route, and route-level code splitting (`lazy()`).

#### 6.2 Design language

**Personality:** calm, precise, trustworthy, like a well-made developer tool (think Linear/Vercel/Stripe dashboards), not "hacker green on black". Security information is stressful, so the UI should reduce anxiety: clear hierarchy, plenty of whitespace, colour reserved for meaning.

**Brand:** keep emerald as the brand colour for continuity, refined, with a deep slate-navy neutral palette.

**Design tokens** — define in `src/styles/globals.css` as CSS variables (OKLCH), mapped to Tailwind via `@theme inline`. Both themes are required, and system preference is the default.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--background` | `oklch(0.985 0.002 247)` | `oklch(0.145 0.015 260)` | page |
| `--surface` (card) | `oklch(1 0 0)` | `oklch(0.185 0.018 260)` | cards, panels |
| `--surface-muted` | `oklch(0.967 0.004 247)` | `oklch(0.22 0.018 260)` | table stripes, code bg |
| `--border` | `oklch(0.92 0.006 247)` | `oklch(0.28 0.02 260)` | |
| `--foreground` | `oklch(0.21 0.03 265)` | `oklch(0.96 0.005 247)` | primary text |
| `--muted-foreground` | `oklch(0.50 0.03 257)` | `oklch(0.70 0.02 257)` | secondary text (≥ 4.5:1 on surface) |
| `--primary` | `oklch(0.60 0.15 163)` (emerald-600) | `oklch(0.70 0.15 163)` | primary actions, focus ring |
| `--primary-foreground` | white | `oklch(0.18 0.03 163)` | |
| `--ring` | = primary | = primary | focus-visible ring 2px + 2px offset |

**Semantic colours** (both themes; always paired with an icon and text, never colour alone):

| Meaning | Hue | Token prefix |
|---|---|---|
| Pass / success | emerald | `--success` |
| Partial / warning | amber | `--warning` |
| Fail / danger | red | `--danger` |
| Inconclusive / info | slate or sky | `--info` |
| Severity critical/high/medium/low/info | red-700 / orange-600 / amber-500 / sky-600 / slate-500 | `--sev-*` |

**Grade palette** (badge = tinted background + strong text + 1px ring in the same hue; the solid fill is only for the large ScoreRing):

| Grade | Light bg / text | Dark bg / text |
|---|---|---|
| A+, A | emerald-100 / emerald-800 | emerald-500/15 / emerald-300 |
| B | lime-100 / lime-800 | lime-500/15 / lime-300 |
| C | yellow-100 / yellow-800 | yellow-500/15 / yellow-300 |
| D | orange-100 / orange-800 | orange-500/15 / orange-300 |
| E, F | red-100 / red-800 | red-500/15 / red-300 |
| N/A | slate-100 / slate-600 | slate-500/15 / slate-300 |

Verify every pair with a contrast checker (≥ 4.5:1 for text) and record the result in the PR.

**Typography:**

- UI: **Inter Variable** (self-hosted via `@fontsource-variable/inter`; no Google Fonts call, which also keeps CSP strict). Enable `font-feature-settings: "cv11", "ss01"` and tabular numbers (`tabular-nums`) for scores and dates.
- Mono: **JetBrains Mono** (`@fontsource-variable/jetbrains-mono`) for header values, DNS records, code snippets and hostnames in tables.
- Scale: 12 / 13 / 14 (body) / 16 / 20 / 24 / 30 / 36 / 48 (landing hero). Line height 1.5 for body, 1.2 for headings. Headings `font-semibold`, letter-spacing `-0.01em` to `-0.02em` at large sizes.

**Spacing and shape:** 4 px base grid. Card padding 20–24 px. Radius: `--radius: 0.75rem` (cards), 0.5rem (inputs/buttons), full (badges/pills). Shadows: barely-there in light mode (`0 1px 2px rgb(0 0 0 / 0.04), 0 1px 3px rgb(0 0 0 / 0.06)`); in dark mode use border plus a subtle lighter surface instead of shadows.

**Motion:** 150–200 ms ease-out for hovers and expands, 250 ms for page and section entrance (fade + 4 px rise), a ScoreRing count-up of 600 ms. Disable all non-essential motion under `prefers-reduced-motion`. No parallax, no confetti.

**Iconography:** lucide-react, 16 px inline / 20 px in nav, `stroke-width: 1.75`. Category icons: Transport `Lock`, Headers `FileCode2`, Cookies `Cookie`, DNS `Globe`, Exposure `ScanEye`. Status: `CheckCircle2`, `AlertTriangle`, `XCircle`, `MinusCircle`, `Info`.

**Theme:** a three-way toggle (Light / Dark / System) in the user menu and the public header. An inline script in `index.html` sets the `dark` class **before first paint** from localStorage or `prefers-color-scheme`, which fixes the flash (M-9).

#### 6.3 Core security components (`components/security/`)

Build these first, each with a Vitest test and a stories-like demo route (`/dev/components`, dev-only):

| Component | Spec |
|---|---|
| `GradeBadge` | Sizes sm/md/lg. Shows the letter; `aria-label="Grade B, 82 out of 100"`. Optional score suffix. |
| `ScoreRing` | SVG radial gauge 0–100, stroke in the grade hue, letter + score in the centre, animated count-up, track in `--border`. Sizes 96/144/192 px. |
| `CategoryBar` | Icon + name + horizontal bar + `82/100`, or a "Not measured" pill when unreachable/skipped, with a tooltip explaining why. |
| `SeverityBadge` | Critical / High / Medium / Low / Info pill with icon. |
| `CheckStatusIcon` | pass/partial/fail/inconclusive/info with an accessible label. |
| `FindingCard` | Collapsed: severity, title, domain (in cross-domain views), "+N pts" impact, effort chip, first-seen relative time. Expanded: what we found (evidence in a mono block), why it matters, `RemediationTabs`, verify command, references, actions (Copy fix, Re-scan, Accept risk…). |
| `RemediationTabs` | Tabs per platform with the detected one pre-selected; `CodeBlock` with copy button (toast "Copied"), `YOUR-DOMAIN` replaced by the real hostname. |
| `CodeBlock` | Mono, `surface-muted` background, horizontal scroll, copy button, optional language label. No heavy syntax-highlighting dependency (or use `shiki` lazily loaded only on detail pages). |
| `ScanProgress` | A vertical list of the 5 categories, each with a status: waiting (dot), running (spinner), done (score), unreachable (grey). Driven by `scan_jobs.progress`. Has `aria-live="polite"`. Shows elapsed time. |
| `CertificateCard` | Issuer, valid-until with days-left meter (green > 30, amber 14–30, red < 14), SANs list, key type/size, protocols accepted. |
| `ScanDiff` | Two columns, "Before → After": score delta chip (`+8`), a list of resolved findings (green, strikethrough title) and new findings (red), and changed values with an inline diff. |
| `Sparkline` | 10-point mini line chart (Recharts, no axes), coloured by trend. |

#### Acceptance criteria

- `npm run typecheck`, `npm run lint`, `npm run test` and `npm run build` all pass.
- The `/dev/components` page renders all components in both themes with fixture data. Screenshots are attached to the PR.
- No emoji are used as UI icons anywhere in `src/`.

---

### Phase 7 — Frontend pages and flows

**Branch:** `feature/frontend-pages` (split into several PRs if large)

#### 7.1 Information architecture

```
Public (PublicHeader + Footer)          App (AppShell: Sidebar + Topbar)
/                Landing                /app                 Overview
/scan/:publicId  Public scan result     /app/domains         Domains
/methodology     How scoring works      /app/domains/:id     Domain (tabs: overview|findings|history|settings)
/bot             Scanner info + opt-out /app/findings        All findings
/privacy /terms                         /app/alerts          Channels, rules, history
/login /signup /forgot-password         /app/settings/*      Profile | Security | API keys | Danger zone
/reset-password /verify-email           *                    NotFound
```

Logged-in users who visit `/` see the landing page with a "Go to dashboard" button (no forced redirect). `/login?next=` returns users to the page they came from.

#### 7.2 Landing page (`/`) — the product is the hero

```
┌──────────────────────────────────────────────────────────────────────┐
│ [shield] SiteShield     Methodology  Scanner info     Log in [Sign up]│
├──────────────────────────────────────────────────────────────────────┤
│        Know exactly how secure your website's setup is —              │
│        and how to fix it.                                             │
│   Free, passive check of HTTPS, security headers, cookies & email DNS │
│   ┌───────────────────────────────────────────┐ ┌────────────┐        │
│   │ yourdomain.com                            │ │ Scan free →│        │
│   └───────────────────────────────────────────┘ └────────────┘        │
│   No signup needed · Takes ~15 seconds · Read-only checks             │
├──────────────────────────────────────────────────────────────────────┤
│  What we check (5 cards with lucide icons, 1–2 lines each, link to    │
│  methodology anchors)                                                 │
├──────────────────────────────────────────────────────────────────────┤
│  "Example report" — a real ScanReport component rendered from a       │
│  static fixture, clearly labelled EXAMPLE, showing ScoreRing,         │
│  category bars and one expanded FindingCard with an nginx snippet     │
├──────────────────────────────────────────────────────────────────────┤
│  Monitoring in 3 steps: Add domains → We re-scan on schedule →        │
│  You get alerted on regressions & expiring certificates               │
├──────────────────────────────────────────────────────────────────────┤
│  Built responsibly: passive-only, rate-limited, opt-out, open method  │
├──────────────────────────────────────────────────────────────────────┤
│  FAQ (accordion: Is it safe to scan? Do you store cookie values? …)  │
├──────────────────────────────────────────────────────────────────────┤
│  Footer: Methodology · Scanner info · Privacy · Terms · GitHub        │
└──────────────────────────────────────────────────────────────────────┘
```

- Hero background: a very subtle radial gradient of `--primary` at 6–8% opacity behind the input, plus a faint dot grid (CSS only). No stock illustrations.
- The scan input accepts a URL or bare domain, trims `https://` and paths, and validates client-side with zod (a hostname regex plus the same blocklist as the backend). On submit → `POST /public/scans` → navigate to `/scan/:publicId` showing `ScanProgress`, then the result.
- SEO: use React 19 native `<title>`/`<meta>` hoisting per page, Open Graph and Twitter card tags, a static OG image (`public/og.png`, 1200×630), `robots.txt`, and `sitemap.xml` for public pages. Public scan result pages are `noindex`.

#### 7.3 Public scan result (`/scan/:publicId`)

- While running: `ScanProgress`, centred, with the hostname at the top.
- Done: the same report layout as the authenticated Domain Overview, but read-only and limited to the top 5 findings with remediation (the rest are collapsed with a count). A sticky CTA reads: "Monitor this site and get alerts → Create free account". On signup, the domain is pre-added and the scan is linked.
- Banner: "Results are public via this link and expire in 30 days." Buttons: Copy link, Re-scan (respects cooldown, showing the remaining time).

#### 7.4 Auth pages

- Split layout on desktop: form on the left (max-w-sm), and on the right a calm brand panel with 3 value bullets and a small rendered `ScoreRing` example. Mobile shows the form only.
- react-hook-form + zod; labels bound with `htmlFor`; inline errors under fields; a show/hide password button; a password strength meter on signup; caps-lock warning; submit button with spinner; `autocomplete` attributes (`email`, `current-password`, `new-password`).
- After signup: an "Check your inbox" screen with a resend button (60 s cooldown) and a "Continue to dashboard" link (the unverified banner appears in the app).

#### 7.5 App shell

- **Sidebar** (240 px, collapsible to 64 px icon rail, a `Sheet` drawer on mobile): Logo; Overview, Domains, Findings (count badge of open high/critical), Alerts; separator; Settings; Methodology (external-ish link). The active item has a `--surface-muted` background and a 2 px primary indicator.
- **Topbar:** breadcrumb, global search / command palette (`⌘K` via shadcn `command`: jump to domain, "Add domain", "Scan <domain>", switch theme), a "+ Add domain" primary button, and the user menu (theme toggle, settings, log out).
- Content max width 1200 px, centred, 24–32 px padding. Each page uses a `PageHeader` (title, description, actions).
- Toasts bottom-right (sonner). Confirm destructive actions with `AlertDialog`.

#### 7.6 Overview (`/app`)

```
PageHeader: "Overview"   [Scan all monitored]  [+ Add domain]
┌─KPI──────┬─KPI──────┬─KPI──────────┬─KPI──────────────┬─KPI─────────────┐
│ Domains 12│ Monitored 9│ Average score 81 (B)│ Open high/critical 4│ Certs expiring <30d 1│
└───────────┴──────────┴──────────────┴──────────────────┴─────────────────┘
┌─ Top fixes (ranked by score impact) ───────────────┐ ┌─ Grade distribution ─┐
│ [High] Add HSTS on shop.acme.com    +7 pts · 5 min │ │ bar: A▇▇▇ B▇▇ C▇ F▇  │
│ [High] DMARC policy is "none" — blog.acme.com +5   │ └──────────────────────┘
│ ... (5 items, "View all findings →")               │ ┌─ Recent activity ────┐
└────────────────────────────────────────────────────┘ │ ✓ cert renewed …     │
                                                       │ ↓ grade B→C …        │
                                                       └──────────────────────┘
```

- KPI tiles: big tabular number, label, optional delta vs last week ("▲ 4"). Each tile links to a filtered view.
- **Empty state** (no domains): a centred illustration made from lucide icons in a soft circle, the headline "Add your first domain", one sentence, an input plus button, and "or try a free scan" with an example (`github.com`).

#### 7.7 Domains (`/app/domains`)

- shadcn data **table**: Domain (favicon via `https://<host>/favicon.ico` with fallback initial, hostname in mono, label below), Grade (`GradeBadge`), Score + `Sparkline`, Open issues (severity dots with counts), Last scan (relative; tooltip absolute), Monitoring (schedule pill: Off / Weekly / Daily; next scan time in tooltip), Verified (check or "Verify" link), and a row actions menu (Scan now, View report, Download PDF, Settings, Delete).
- Toolbar: search, filters (grade, monitoring, verified), sort, and "Add domain" (dialog with **Single** and **Bulk** tabs; bulk accepts pasted lines or a CSV upload and shows per-row validation results).
- Row click → domain detail. A row that is scanning shows an inline progress pill.
- Mobile: the table collapses to cards.

#### 7.8 Domain detail (`/app/domains/:id`)

Header: favicon + hostname (mono, large) + label, verified badge, `GradeBadge` lg, last scanned relative time; actions: **Scan now** (primary; becomes `ScanProgress` popover while running), Download PDF, Share, ⋯ (settings, delete).

**Tab: Overview**
- Left: `ScoreRing` lg + grade-cap notice if any ("Capped at C: site doesn't force HTTPS").
- Right: 5 `CategoryBar`s.
- Below: "Top issues on this domain" (top 3 `FindingCard`s collapsed), `CertificateCard`, a mini trend chart (last 30 scans) and "What changed since last scan" (compact `ScanDiff`).

**Tab: Findings**
- Segmented control: Open (default) | Resolved | Accepted risk. Grouped by severity with sticky group headers. `FindingCard` list with expand/collapse-all.
- Passing checks are collapsed in a "Passed checks (14)" section at the bottom, so users see what's already good. This is positive reinforcement, not clutter.

**Tab: History**
- `ScoreTrendChart` (Recharts area chart, grade-band background stripes A/B/C… at low opacity, a vertical dashed marker labelled "Scoring updated" where `scoring_version` changes, tooltip with grade/score/date).
- Paginated scan table: date, grade, score, delta, source (manual / scheduled / API), actions (View, Compare). Select two rows → **Compare** → `ScanDiff` in a full-width sheet.

**Tab: Settings**
- Label; Monitoring schedule (radio cards: Off / Weekly / Daily; Daily disabled with tooltip if unverified); preferred platform for snippets; alert overrides; ownership verification panel (3 method tabs with copyable values and a "Check now" button with live result); public badge toggle with copyable Markdown/HTML embed code; **Danger zone**: delete domain (type the hostname to confirm).

#### 7.9 Findings (`/app/findings`)

Cross-domain list with filters (severity, category, domain, status), sorted by score impact by default. Grouping toggle: by domain / by check ("CSP missing on 4 domains" → expand to see the domains). Grouping by check is very useful for agencies.

#### 7.10 Alerts (`/app/alerts`)

- **Channels** card list: Email (default, verified address), "+ Add Slack", "+ Add webhook" (dialog; shows the signing secret once; "Send test" button with result toast).
- **Rules:** switches for each alert type with short descriptions; checkbox chips for certificate thresholds (30/14/7/1); weekly digest toggle with a preview link.
- **History:** a table of sent notifications (time, kind, domain, channel, status).

#### 7.11 Settings

Profile (name, email change flow, timezone), Security (change password, active sessions list with "revoke"/"log out everywhere"), API keys (create → secret shown once in a copyable field with warning; list with prefix, last used, revoke), Data (export JSON), Danger zone (delete account).

#### 7.12 Methodology (`/methodology`) and Scanner info (`/bot`)

- Methodology renders `GET /meta/checks`: every category, its weight, every check with pass/partial/fail criteria, the grade bands and caps. Transparency builds trust; this page is also good for SEO.
- Bot page: what the scanner does and doesn't do, its User-Agent, request volume limits, source IP ranges (if static), and how to opt out.

#### 7.13 UX quality bar (applies to every page)

- **Loading:** skeletons shaped like the final content (no spinner-only pages). Optimistic updates for toggles, with rollback and a toast on failure.
- **Errors:** inline field errors, a toast for action errors, and a full-page error state with Retry for failed queries. Never show raw stack traces or JSON.
- **Empty states:** every list has one, with a clear next action.
- **Copy:** sentence case, plain language, specific numbers ("Expires in 12 days", not "Expiring soon"). Use "Not measured" instead of "Error" for unreachable categories.
- **Time:** relative ("2 h ago") with an absolute local-time tooltip; the user's timezone from settings.
- **Accessibility (WCAG 2.2 AA):** full keyboard navigation, visible focus ring, skip-to-content link, `aria-live` for scan progress and toasts, a 44×44 px minimum touch target on mobile, meaning never conveyed by colour alone, and `axe` checks with zero serious/critical violations.
- **Responsive:** design at 375, 768, 1280 and 1536 px. The sidebar becomes a drawer below 1024 px. Tables become cards below 768 px. No horizontal page scroll.
- **Performance:** landing route JS ≤ 180 KB gzipped; lazy-load app routes and charts; self-hosted fonts with `font-display: swap`. Lighthouse (mobile) on landing ≥ 95 for Performance, Accessibility, Best Practices and SEO.

#### Acceptance criteria

- Playwright e2e flows pass: anonymous instant scan → result → signup with pre-added domain; signup → verify (via Mailpit API) → add domain → scan → see findings → copy a fix → accept risk → shows in Accepted tab; enable monitoring requires verification; compare two scans; delete domain; log out / refresh session.
- `@axe-core/playwright` runs on every page in both themes with zero serious/critical issues.
- Screenshots of every page in light and dark at 375 px and 1280 px are attached to the PR.

---

### Phase 8 — Public and developer features

**Branch:** `feature/public-dev`

1. **Instant public scan** — backend done in Phase 2; finish here: `purge_expired_public_scans`, a cooldown message in the UI, and linking the scan to an account on signup.
2. **Share links** for authenticated scans (`POST /scans/{id}/share`). The public page hides the domain owner's identity; the owner can revoke.
3. **Status badge** — `GET /public/badge/{token}.svg`: a shields-style SVG `SiteShield | A` in the grade colour, `Cache-Control: max-age=3600`. Only for verified domains with the badge enabled. Provide Markdown and HTML snippets in domain settings.
4. **API keys + CI usage:**
   - `Authorization: Bearer ss_live_<prefix>_<secret>`; store a hash (SHA-256 of the full key) and show the prefix in the UI.
   - Endpoints usable with keys: `POST /domains/{id}/scans`, `GET /scan-jobs/{id}`, `GET /scans/{id}`, `GET /domains`.
   - Add `docs/ci.md` with a GitHub Actions example that starts a scan after deploy, polls, and fails if the grade is below a threshold:

     ```yaml
     - name: SiteShield gate
       env: { SITESHIELD_KEY: "${{ secrets.SITESHIELD_KEY }}", DOMAIN_ID: "42", MIN_SCORE: "75" }
       run: |
         JOB=$(curl -fsS -X POST -H "Authorization: Bearer $SITESHIELD_KEY" \
           https://YOUR-SITESHIELD-HOST/api/v1/domains/$DOMAIN_ID/scans | jq -r .id)
         for i in $(seq 1 30); do
           R=$(curl -fsS -H "Authorization: Bearer $SITESHIELD_KEY" \
             https://YOUR-SITESHIELD-HOST/api/v1/scan-jobs/$JOB)
           S=$(echo "$R" | jq -r .status)
           [ "$S" = succeeded ] && break; [ "$S" = failed ] && exit 1; sleep 3
         done
         SCORE=$(echo "$R" | jq -r .scan.score)
         echo "SiteShield score: $SCORE"; [ "$SCORE" -ge "$MIN_SCORE" ]
     ```
5. **PDF report v2:** cover summary (grade ring, score, date, verified-owner stamp), an executive summary paragraph generated from the data ("3 high-severity issues; fixing HSTS and DMARC would raise the grade to B"), category breakdown, findings with remediation for the user's preferred platform, certificate details, and a history chart (render a small line chart with ReportLab graphics). Optional "white-label" text field (agency name) in user settings, printed in the header. All text escaped (C-5).

#### Acceptance criteria

- Badge SVG validates and renders; the public share page works logged-out; the CI snippet works against a local stack (document the test in the PR); PDF snapshot tests (text extraction with `pypdf`) assert key sections exist.

---

### Phase 9 — Production operations

**Branch:** `feature/prod-ops`

#### 9.1 Containers

- **Backend Dockerfile:** multi-stage (builder with wheels → slim runtime), non-root `app` user, `HEALTHCHECK` on `/health`, entrypoint script: `alembic upgrade head` (only when `RUN_MIGRATIONS=1`, so only one service runs it) then `gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY:-2} --bind 0.0.0.0:8000 --access-logfile -`. Add `--proxy-headers`/`forwarded_allow_ips` so client IPs are correct for rate limiting behind the proxy.
- **Worker:** `celery -A app.tasks.celery_app worker -Q scans,notify -c ${WORKER_CONCURRENCY:-4} --max-tasks-per-child=200`. **Beat:** exactly one replica, with its schedule file in `/tmp`.
- **Frontend:** `npm ci` (not `npm install`), build, then serve with nginx (non-root `nginx-unprivileged` image).
- **Frontend nginx security headers** (dogfooding, I-8):

  ```nginx
  add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
  add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'; upgrade-insecure-requests" always;
  add_header X-Content-Type-Options "nosniff" always;
  add_header Referrer-Policy "strict-origin-when-cross-origin" always;
  add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=()" always;
  add_header Cross-Origin-Opener-Policy "same-origin" always;
  server_tokens off;
  ```

  The inline theme script in `index.html` needs a CSP hash (`'sha256-…'`) added to `script-src`. Compute it at build time with a small Vite plugin, or move the script to a file. `style-src 'unsafe-inline'` is only needed if Recharts/Radix inject inline styles. Test, and tighten if possible. Proxy `/api/` to the backend in the same nginx, so the app is same-origin (`location /api/ { proxy_pass http://backend:8000; ... }`). Serve `/.well-known/security.txt` for SiteShield itself.
- **docker-compose.yml** (dev): add Mailpit, read all secrets from `.env` (with `.env.example` committed), add healthchecks for every service, and drop the hard-coded `dns:` overrides unless they're needed (document why if kept). Add `docker-compose.prod.yml` as a reference production layout (proxy, no exposed DB/Redis ports, restart policies, resource limits).

#### 9.2 Observability

- structlog JSON logs with `request_id` (middleware sets/propagates `X-Request-ID`), `user_id`, and `scan_job_id` in worker logs. Never log tokens, passwords, cookie headers or API keys (add a redaction processor, with a test).
- Sentry on backend, worker and frontend (DSN optional), with release tagged by git SHA.
- `/ready` checks DB and Redis. Optional Prometheus `/metrics` (scan duration histogram, scans by status, queue depth).

#### 9.3 CI/CD (`.github/workflows/`)

- `ci.yml` on PR and push to `main`:
  - **backend:** Python 3.13 (match the Dockerfile), `ruff check`, `ruff format --check`, `pytest --cov=app --cov-fail-under=80` with a **Postgres 16 service** and Redis service, plus `alembic upgrade head` on an empty DB and a check that `alembic check` shows no pending autogenerate diff.
  - **frontend:** Node 20 LTS (match the Dockerfile; or 22 for both), `npm ci`, `gen:api` drift check, `typecheck`, `lint`, `test`, `build`, bundle-size check.
  - **e2e:** `docker compose up -d --build`, then Playwright + axe tests, uploading the report and traces on failure.
  - **docker:** build all images (cache with `docker/build-push-action`).
- `deploy.yml` on push to `main` after CI passes: push images to GHCR and trigger a Render/Railway/Fly deploy hook (secret). Run migrations in a release step.
- Dependabot for pip, npm, GitHub Actions and Docker. CodeQL for Python and JS.

#### 9.4 Deployment target

Pick **one** and document it in `docs/deploy.md`. Recommended: **Render** (matches the README) — web service (backend), background workers (worker, beat ×1), static site or web service (frontend nginx), managed Postgres, managed Redis (Key Value). Alternative: one VPS with `docker-compose.prod.yml` + Caddy (automatic HTTPS). Requirements in either case: daily Postgres backups with a documented restore test, secrets only in the platform's secret store, and a custom domain with HTTPS.

#### Acceptance criteria

- A fresh clone → `cp .env.example .env` → `docker compose up --build` gives a working stack with Mailpit.
- CI is green. Deployed staging URL works. **Scanning SiteShield's own production domain returns A or A+** (I-8), and the result is recorded in `README.md` with a badge.

---

### Phase 10 — Optional extensions

Only start these after the launch checklist (section 7) passes.

1. **Dependency CVE check** (from the README roadmap): upload or paste `package-lock.json`, `requirements.txt` or `poetry.lock`, or connect a public GitHub repo → query the **OSV.dev** batch API → list vulnerable packages with severity and fixed versions. Store the results as a separate "Dependencies" panel, kept out of the website grade.
2. **Teams/workspaces:** an `organizations` table, membership roles (owner/admin/member/viewer), domains owned by the org, and invitations by email. Migrate the `owner_id` scoping to `org_id` with the same 404 semantics.
3. **More checks:** mixed content on the home page (HTML parse of `http://` subresources), Subresource Integrity on third-party scripts, `Cross-Origin-Resource-Policy`, MTA-STS/TLS-RPT for email, and BIMI (info).
4. **i18n:** extract UI strings with `i18next`; KB entries get translations.
5. **Plans/billing:** only if needed; keep the free tier generous and honest.

---

## 6. Testing strategy

| Layer | Tooling | Must cover |
|---|---|---|
| Scanner units | pytest + fixtures (no network) | Each check's pass/partial/fail/inconclusive, CSP parser, cookie parser, SPF/DMARC parsers, org-domain extraction, scoring + caps (golden files) |
| Network policy | pytest + monkeypatched `getaddrinfo` + respx | All SSRF cases in Phase 1, redirect hop validation, post-connect peer check |
| API | pytest + TestClient + Postgres (CI) | Every route: happy path, validation error, unauthenticated 401, foreign-tenant 404, rate-limit 429 |
| Tasks | pytest with `task_always_eager` | Job lifecycle, dedupe, partial results on timeout, findings lifecycle, alert dedupe |
| Migrations | pytest | Upgrade from empty and from seeded `0001_baseline` |
| Frontend units | Vitest + Testing Library + MSW | Components in section 6.3, API client refresh logic, form validation |
| E2E | Playwright | Flows in Phase 7 acceptance, both themes, mobile viewport |
| A11y | @axe-core/playwright | Every route |
| Real-world smoke | `pytest -m network` (manual/nightly) | A small allow-listed set of public test hosts (badssl.com subdomains, github.com, example.com) |

Coverage gates: backend ≥ 80% overall, and ≥ 95% for `scanner/` and `core/security.py`.

---

## 7. Launch checklist

**Security**
- [ ] SSRF test suite passes; manual attempt to scan `http://localhost`, `169.254.169.254` and a redirect-to-internal URL is refused.
- [ ] No secrets in the repo (`gitleaks` or GitHub secret scanning clean); the JWT secret has no default; `.env.example` only.
- [ ] Rate limits active; per-target cooldown active; opt-out works.
- [ ] Refresh tokens are httpOnly/Secure/SameSite; the access token is never in localStorage.
- [ ] SiteShield scores **A/A+** on itself.

**Correctness**
- [ ] Golden scoring tests pass; the KB covers every check id.
- [ ] Unreachable/inconclusive never lowers a score (tests).
- [ ] Legacy scans render (shown as "Legacy scan — limited detail"), and the trend chart marks scoring-version changes.

**Product**
- [ ] Anonymous instant scan → result → signup conversion flow works.
- [ ] Every finding shows why it matters, a platform snippet and a verify command.
- [ ] Monitoring + certificate-expiry + grade-drop alerts deliver by email (and Slack/webhook if configured), with dedupe and unsubscribe.
- [ ] PDF report is legible and correct; the share link and badge work.

**UX**
- [ ] Both themes are polished; there's no theme flash.
- [ ] axe: zero serious/critical issues; keyboard-only run-through of the main flows.
- [ ] Lighthouse mobile ≥ 95 on landing; app routes load in < 2 s on a mid-range device with a fast-3G throttle after the first visit.
- [ ] Every list has an empty state and every query has an error state.

**Ops**
- [ ] CI green (lint, types, tests, e2e, docker build). Deploy pipeline works. Migrations run once per release.
- [ ] Backups configured and restore tested; Sentry receiving events; `/ready` wired to platform health checks.
- [ ] README rewritten (live URL, screenshots, setup, architecture); PROGRESS.md updated; `docs/deploy.md`, `docs/ci.md`, `SECURITY.md` (vulnerability reporting contact), `/privacy` and `/terms` pages present.

---

## 8. Appendices

### A. Environment variables (`backend/.env.example`)

```dotenv
ENV=development                     # development | test | production
PUBLIC_BASE_URL=http://localhost:8080
DATABASE_URL=postgresql+psycopg://siteshield:CHANGE_ME@postgres:5432/siteshield
REDIS_URL=redis://redis:6379/0
JWT_SECRET=                         # required; >= 32 random bytes (python -c "import secrets;print(secrets.token_urlsafe(48))")
ACCESS_TOKEN_MINUTES=15
REFRESH_TOKEN_DAYS=30
COOKIE_SECURE=false                 # true in production
FERNET_KEY=                         # for encrypting webhook secrets
CORS_ORIGINS=http://localhost:5173  # dev only; prod is same-origin
EMAIL_BACKEND=console               # console | smtp | resend
EMAIL_FROM="SiteShield <alerts@example.com>"
SMTP_HOST=mailpit
SMTP_PORT=1025
SMTP_USER=
SMTP_PASSWORD=
SCAN_SWEEP_SECONDS=300
DNS_RESOLVERS=1.1.1.1,8.8.8.8
SCANNER_USER_AGENT="SiteShieldBot/2.0 (+http://localhost:8080/bot)"
OPT_OUT_CONTACT=abuse@example.com
SENTRY_DSN=
DOCS_ENABLED=true                   # false in production
```

### B. Mapping of old → new code

| Today | Becomes |
|---|---|
| `app/config.py` | `app/core/config.py` (validated, no secret defaults) |
| `app/database.py` | `app/db/session.py` |
| `app/models.py` | `app/db/models/*.py` |
| `app/schemas.py` | `app/schemas/*.py` |
| `app/auth/*` | `app/core/security.py` + `app/api/v1/auth.py` + `users.py` |
| `app/domains/router.py` | `app/api/v1/domains.py` + `services/domain_service.py` |
| `app/scanner/router.py` | `app/api/v1/scans.py` (+ `scan-jobs`, `report.pdf`) |
| `app/scanner/{headers,tls,dns_scan,cookies}.py` | `app/scanner/checks/*.py` (pure functions over `FetchResult` / DNS / TLS probes) |
| `app/scanner/tasks.py` | `app/tasks/scan_tasks.py` + `app/scanner/engine.py` + `scoring.py` |
| `app/celery_app.py` | `app/tasks/celery_app.py` |
| `frontend/src/api/*.js` | `frontend/src/lib/api.ts` + `src/api/use*.ts` hooks |
| `context/AuthContext.jsx` | `lib/auth.ts` (in-memory token, refresh single-flight) + provider |
| `components/ScanResult.jsx` | `components/security/*` (ScoreRing, CategoryBar, FindingCard, …) |
| `components/ScoreTrendChart.jsx` (Chart.js) | `components/charts/ScoreTrendChart.tsx` (Recharts) |
| `pages/Dashboard.jsx` | `pages/app/Overview.tsx` + `pages/app/Domains.tsx` |
| `pages/DomainDetail.jsx` | `pages/app/DomainDetail/*` (tabbed) |

### C. Microcopy reference

| Situation | Write | Don't write |
|---|---|---|
| Category couldn't be measured | "Not measured — we couldn't connect to port 443. This doesn't affect your grade." | "Error", "Failed" |
| Inconclusive check | "Couldn't determine (DNS query timed out). Not counted." | red ✗ |
| Partial | "HSTS is set, but max-age is 1 day. Raise it to at least 6 months." | "Weak HSTS!!" |
| Grade cap | "Grade capped at C because the site doesn't redirect HTTP to HTTPS." | "Penalty applied" |
| Empty findings | "No open issues. Nice work — we'll keep watching." | (blank) |
| Rate limited | "You can scan this site again in 3 minutes." | "429 Too Many Requests" |
| Delete domain | "Delete shop.acme.com? This removes 37 scans and stops monitoring. Type the domain to confirm." | "Are you sure?" |

### D. Commit and PR template for the agent

```
<type>(<scope>): <imperative summary>

Why: <problem or audit ID, e.g. C-1 SSRF>
What: <bullet list of changes>
Tests: <new/updated tests>
Screens: <for UI changes, before/after in both themes>
Docs: <README/PROGRESS updates>
```

PR description sections: **Summary**, **Audit items addressed** (IDs from section 3.2), **Acceptance criteria** (checklist copied from the phase, ticked), **Testing done** (commands + results), **Screenshots**, **Follow-ups**.

---

*End of plan. Start with section 0, rule 2 (baseline), then Phase 0.*
