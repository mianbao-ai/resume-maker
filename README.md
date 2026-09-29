# Resume Maker

A local-first, open-source resume builder with a decoupled frontend and backend. The frontend is built with React, Vite, and TypeScript, while the backend uses FastAPI and SQLite.

## Features

- Resume optimization chat on the left and a live A4 preview on the right
- Click-to-edit content directly in the preview, with entry reordering and deletion
- Professional and minimal layouts with six accent colors
- Profile, work experience, projects, education, and skills sections
- Automatic browser storage with no account or cloud service required
- FastAPI REST API backed by SQLite persistence
- Native browser printing and PDF export
- Sample content, completion guidance, and a responsive interface

## Getting Started

### 1. Start the backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API documentation is available at <http://localhost:8000/docs>.

### 2. Start the frontend

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

Visit <http://localhost:5173>. The development server proxies `/api` requests to FastAPI.

## Project Structure

```text
.
├── backend/              # FastAPI API, SQLite data layer, and tests
│   ├── app/
│   └── tests/
└── frontend/             # React + Vite single-page application
    └── src/
        ├── components/
        ├── api.ts
        ├── types.ts
        └── styles.css
```

## Configuration

Set `VITE_API_URL` to configure the backend URL for a production frontend build:

```bash
VITE_API_URL=https://api.example.com npm run build
```

Backend environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `RESUME_DB_PATH` | `backend/data/resumes.db` | Path to the SQLite database file |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated list of allowed frontend origins |

## Testing

```bash
cd backend && pytest
cd frontend && npm run build
```

## License

MIT

## Resume Agent backend

The open-source backend now includes the full Resume Agent feature under
`backend/app/resume_agent`, synced from the website subtree. Its API follows the
same session, goal, patch, proposal, chat stream, and export protocol as the
website Agent:

- `POST /api/resume-agent/sessions`
- `GET /api/resume-agent/sessions/{id}`
- `PUT /api/resume-agent/sessions/{id}/goal`
- `PATCH /api/resume-agent/sessions/{id}/document`
- `POST /api/resume-agent/sessions/{id}/chat/stream`
- `POST /api/resume-agent/sessions/{id}/export/docx`
- `POST /api/resume-agent/sessions/{id}/export/pdf`

The website publishes the complete feature as the `resume-maker` subtree branch.
Future updates can be pulled here without copying files manually:

```bash
WEBSITE_REPO=../website ./scripts/sync_resume_agent.sh
```

The script refreshes the subtree source and runs `git subtree pull`; review and
commit the resulting backend subtree update together with frontend changes.
