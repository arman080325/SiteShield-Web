# 🛡️ SiteShield

**A multi-tenant SaaS platform that audits and continuously monitors website security posture.**

SiteShield scans any domain for defensive security weaknesses — TLS configuration, HTTP security headers, cookie flags, DNS hygiene, and exposed sensitive paths — then grades it, tracks the score over time, and alerts you when your posture regresses.

Think `securityheaders.com` + `SSL Labs` + dependency-CVE checks, rebuilt as a real account-based product with background scanning, scheduled monitoring, and automated reporting.

<!-- TODO: add a live demo link once deployed -->
🔗 **Live demo:** _coming soon_  
<!-- TODO: replace with a real dashboard screenshot once Month 1 ships -->
<!-- ![SiteShield dashboard](docs/screenshot.png) -->

---

## Why SiteShield

Most site owners have no idea their security headers are missing, their TLS is misconfigured, or their `.env` is publicly reachable — until it's exploited. SiteShield turns a scattered set of manual checks into a single, continuous, account-based monitoring platform with a clear A–F grade and a history of how that grade changes over time.

Every check is **passive and defensive** — SiteShield inspects publicly observable configuration, the same way a security-conscious admin would. It is a blue-team tool, not an attack tool.

---

## ✨ Features

- 🔐 **Secure multi-tenant accounts** — JWT authentication, bcrypt-hashed passwords, per-user data isolation
- 🌐 **Domain management** — add, track, and manage multiple domains per account
- 🛡️ **Security posture scanning** — HTTP security headers, TLS/SSL configuration, cookie flags, DNS records (SPF/DMARC/DNSSEC), and exposed-path checks
- 📊 **Severity scoring** — every scan produces a weighted score and an A–F grade
- 📈 **Historical tracking** — see how a domain's posture trends across scans over time
- ⏱️ **Scheduled re-scans** — automated background monitoring without manual triggers
- 🚨 **Regression alerts** — get notified the moment a domain's grade drops
- 📄 **PDF reports** — clean, shareable security reports per scan

---

## 🧰 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React, Tailwind CSS, Chart.js |
| **Backend** | FastAPI (Python), Pydantic |
| **Database** | PostgreSQL (SQLite in development) |
| **Async / Jobs** | Celery + Redis (background scans, scheduling) |
| **Auth** | JWT, bcrypt |
| **Reporting** | ReportLab |
| **DevOps** | Docker, GitHub Actions (CI/CD) |
| **Deployment** | Render / Railway |

---

## 🏗️ Architecture

```
React (dashboard)  ──►  FastAPI (REST API)  ──►  PostgreSQL
                              │
                              ▼
                     Redis queue ──► Celery workers (scanners)
                              │
                              ▼
                   Scheduled re-scans + alerting
```

The API stays responsive by offloading every scan to background workers via a Redis-backed queue, so scans never block requests. A scheduler triggers periodic re-scans and fires alerts on score regressions.

---

## 🚀 Getting Started

> Full setup instructions will expand as the project grows.

### Prerequisites
- Python 3.11+
- Node.js 18+
- (Later) Redis and PostgreSQL

### Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
uvicorn app.main:app --reload
```
API docs available at `http://127.0.0.1:8000/docs`.

### Frontend
```bash
cd frontend
npm install
npm run dev
```

---

## 🗺️ Roadmap

- [ ] **Core & Auth** — JWT signup/login, domain CRUD, first synchronous header scan, React dashboard
- [ ] **Async scanning** — background workers, TLS + cookie + DNS checks, scoring engine
- [ ] **Monitoring** — scheduled re-scans, history charts, PDF reports, email alerts
- [ ] **Dependency CVEs** — `package.json` / `requirements.txt` vulnerability lookup
- [ ] **Production** — rate limiting, test suite, Dockerization, CI/CD, live deployment

---

## 🔒 Security & Ethics

SiteShield performs only **passive, non-intrusive** analysis of publicly observable configuration. It does not exploit, attack, brute-force, or attempt unauthorized access to any system. It is intended for auditing domains you own or are authorized to assess.

---

## 📬 Contact

**Arman Ahemad Khan**  
<!-- TODO: confirm/replace links -->
[LinkedIn](https://linkedin.com/in/arman-ahemad-khan) · [GitHub](https://github.com/arman080325)

---

<sub>SiteShield is an independent, educational full-stack security project built from scratch.</sub>