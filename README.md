# PropAgent Market Intelligence Engine — Railway Flat

Flat-layout version for GitHub web upload.

Repository root:
- main.py
- config.py
- database.py
- models.py
- schemas.py
- Dockerfile
- requirements.txt
- railway.json

No `app/` folder is required.

## API
- GET `/health`
- POST `/ingest/dld`
- GET `/analytics/areas`
- POST `/valuation`

Deploy to Railway, attach PostgreSQL, set `DATABASE_URL`, then generate a public domain.
