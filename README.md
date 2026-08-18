# PropAgent Market Intelligence Engine — V0.3 UI

This is the same Railway + PostgreSQL project with a business-facing UI added to the existing FastAPI service.

Main dashboard: `/`
Developer API docs: `/docs`

New supporting API endpoints:
- `GET /dashboard/summary`
- `GET /meta/options`

Existing endpoints remain:
- `GET /health`
- `POST /ingest/dld`
- `GET /analytics/areas`
- `POST /valuation`

To update the current GitHub/Railway project, upload/replace:
- `main.py`
- `models.py`
- `index.html`
- `styles.css`
- `app.js`
- `README.md`

No new Railway project, database, domain, or DATABASE_URL is required.
