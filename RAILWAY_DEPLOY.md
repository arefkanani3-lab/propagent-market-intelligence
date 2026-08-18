# PropAgent Market Intelligence Engine — Railway Deployment

## GitHub
Create a GitHub repository and upload the CONTENTS of this folder to the repository root.

Required root files:
- Dockerfile
- requirements.txt
- railway.json
- app/

## Railway
1. New Project
2. Deploy from GitHub repo
3. Select the repository
4. Add PostgreSQL from + New > Database > PostgreSQL
5. In the backend service Variables, create:
   DATABASE_URL = reference to the PostgreSQL service DATABASE_URL
6. Settings > Networking > Generate Domain
7. Open:
   /health
   /docs

## Upload DLD data
Use Swagger:
POST /ingest/dld

## Analytics
GET /analytics/areas?lookback_days=365

## Valuation
POST /valuation
