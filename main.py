from fastapi import FastAPI
from app.database import Base, engine
from app.routers import ingestion, analytics, valuation

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="PropAgent Market Intelligence Engine",
    version="0.1.0",
    description=(
        "DLD ingestion, market analytics, comparable search and explainable "
        "property valuation engine."
    ),
)

app.include_router(ingestion.router)
app.include_router(analytics.router)
app.include_router(valuation.router)

@app.get("/health")
def health():
    return {"status": "ok", "engine": "PropAgent Market Intelligence Engine V0"}
