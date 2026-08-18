import os
os.environ["DATABASE_URL"] = "sqlite:///./demo.db"

import pandas as pd
from app.database import Base, engine, SessionLocal
from app.services.ingestion import ingest_dataframe
from app.services.analytics import area_summary
from app.services.valuation import value_property
from app.schemas import ValuationRequest

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

df = pd.read_csv("sample_data/transactions-2026-08-18.csv")
db = SessionLocal()

print("INGEST:")
print(ingest_dataframe(db, df))

print("\nTOP AREAS:")
for row in area_summary(db, 365)[:5]:
    print(row)

print("\nVALUATION:")
request = ValuationRequest(
    area="JUMEIRAH VILLAGE CIRCLE",
    bedrooms=3,
    size_sqm=160,
    asking_price=3_000_000,
    lookback_days=365,
    max_size_difference=0.35,
    max_comparables=10,
)
result = value_property(db, request)
print({k: v for k, v in result.items() if k != "comparables"})
print("\nTOP 3 COMPS:")
for comp in result["comparables"][:3]:
    print(comp)

db.close()
