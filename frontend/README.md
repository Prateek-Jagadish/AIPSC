# UPSC Intelligence — Frontend

React + Vite dashboard for the UPSC Intelligence System.

## Setup

```bash
cd frontend
npm install
npm run dev        # → http://localhost:3000
```

Backend must be running at `localhost:8000` (proxied via Vite).

## Pages

| Route        | Page              |
|--------------|-------------------|
| `/`          | Dashboard — daily briefing, stats, quick actions |
| `/chat`      | Ask & Learn — full query interface with RAG responses |
| `/upload`    | Upload documents — drag & drop PDFs |
| `/newspaper` | Daily Briefing — upload newspaper, see CA cards |
| `/analytics` | Analytics — weakness gaps, PYQ trends, CA coverage |
| `/revision`  | Revision — weekly/monthly cheat sheets |
| `/visuals`   | Maps & Visuals — image gallery with AI captions |

## Stack

- React 18 + Vite
- React Router v6
- Tailwind CSS
- Recharts (charts)
- React Dropzone (file uploads)
- Lucide React (icons)
- Axios (API calls)
- Crimson Pro + DM Sans + JetBrains Mono (fonts)
