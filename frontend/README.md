# SiteShield Frontend

The React frontend for the SiteShield website security monitoring platform.

## Tech Stack

- **Framework**: React 19 + Vite
- **Styling**: Tailwind CSS
- **Routing**: React Router DOM v7
- **Charts**: Chart.js (`react-chartjs-2`)
- **Icons & Badges**: Custom SVG & Tailwind components

## Development Setup

### Prerequisites

- Node.js 20+ (or Node 22 LTS)
- npm 10+

### Installation & Run

```bash
# Install dependencies cleanly
npm ci

# Start the Vite development server (default http://localhost:5173)
npm run dev

# Run lint checks
npm run lint

# Build production bundle
npm run build
```

## Environment Variables

Configure `.env` or set in environment:

| Variable | Default | Description |
|---|---|---|
| `VITE_API_URL` | `http://127.0.0.1:8000` | Backend API base URL |
