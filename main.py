import io
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median, pstdev

import pandas as pd
from fastapi import FastAPI, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Transaction, IngestionRun
from schemas import ValuationRequest

SQM_TO_SQFT = 10.7639104167
BASE_DIR = Path(__file__).resolve().parent

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="PropAgent Market Intelligence Engine",
    version="0.3.2",
    description="DLD ingestion, market analytics, comparable search and explainable valuation."
)

COLUMN_MAP = {
    "TRANSACTION_NUMBER": "transaction_number",
    "INSTANCE_DATE": "instance_date",
    "GROUP_EN": "group_en",
    "PROCEDURE_EN": "procedure_en",
    "IS_OFFPLAN_EN": "is_offplan",
    "IS_FREE_HOLD_EN": "is_freehold",
    "USAGE_EN": "usage_en",
    "AREA_EN": "area_en",
    "PROP_TYPE_EN": "property_type_en",
    "PROP_SB_TYPE_EN": "property_subtype_en",
    "TRANS_VALUE": "transaction_value",
    "PROCEDURE_AREA": "procedure_area_sqm",
    "ACTUAL_AREA": "actual_area_sqm",
    "ROOMS_EN": "rooms",
    "PARKING": "parking",
    "NEAREST_METRO_EN": "nearest_metro_en",
    "NEAREST_MALL_EN": "nearest_mall_en",
    "NEAREST_LANDMARK_EN": "nearest_landmark_en",
    "TOTAL_BUYER": "total_buyer",
    "TOTAL_SELLER": "total_seller",
    "MASTER_PROJECT_EN": "master_project_en",
    "PROJECT_EN": "project_en",
}

REQUIRED_DLD_COLUMNS = {
    "TRANSACTION_NUMBER", "INSTANCE_DATE", "AREA_EN",
    "TRANS_VALUE", "PROCEDURE_AREA"
}

def clean_text(value):
    if pd.isna(value):
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None

def parse_rooms(value):
    if pd.isna(value):
        return None
    m = re.search(r"(\d+)", str(value))
    return int(m.group(1)) if m else None

def parse_bool(value):
    if pd.isna(value):
        return None
    text = str(value).strip().lower()
    if text in {"yes", "true", "1", "off plan", "off-plan", "free hold", "freehold"}:
        return True
    if text in {"no", "false", "0", "ready"}:
        return False
    return None

def normalize_dld_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_DLD_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required DLD columns: {sorted(missing)}")

    out = pd.DataFrame()
    for src, dst in COLUMN_MAP.items():
        if src in df.columns:
            out[dst] = df[src]

    out["instance_date"] = pd.to_datetime(out["instance_date"], errors="coerce")
    out["transaction_value"] = pd.to_numeric(out["transaction_value"], errors="coerce")
    out["procedure_area_sqm"] = pd.to_numeric(out["procedure_area_sqm"], errors="coerce")

    if "actual_area_sqm" in out:
        out["actual_area_sqm"] = pd.to_numeric(out["actual_area_sqm"], errors="coerce")

    # Keep integer-like columns nullable. Do not let pandas turn missing integers
    # into float NaN values that PostgreSQL INTEGER columns cannot accept.
    for col in ["total_buyer", "total_seller"]:
        if col in out:
            out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")

    if "rooms" in out:
        out["rooms"] = pd.Series(
            [parse_rooms(value) for value in out["rooms"]],
            index=out.index,
            dtype="Int64",
        )

    for col in [
        "transaction_number", "group_en", "procedure_en", "usage_en",
        "area_en", "master_project_en", "project_en", "property_type_en",
        "property_subtype_en", "parking", "nearest_metro_en",
        "nearest_mall_en", "nearest_landmark_en",
    ]:
        if col in out:
            out[col] = out[col].apply(clean_text)

    if "is_offplan" in out:
        out["is_offplan"] = out["is_offplan"].apply(parse_bool)
    if "is_freehold" in out:
        out["is_freehold"] = out["is_freehold"].apply(parse_bool)

    out = out[
        out["instance_date"].notna()
        & out["transaction_number"].notna()
        & (out["transaction_value"] > 0)
        & (out["procedure_area_sqm"] > 0)
    ].copy()

    out["price_per_sqm"] = out["transaction_value"] / out["procedure_area_sqm"]
    out["price_per_sqft"] = out["price_per_sqm"] / SQM_TO_SQFT

    for col in ["area_en", "master_project_en", "project_en"]:
        if col in out:
            out[col] = out[col].apply(lambda x: x.upper() if isinstance(x, str) else x)

    out["source"] = "DLD"
    return out

def read_upload(filename: str, payload: bytes) -> pd.DataFrame:
    lower = filename.lower()
    if lower.endswith(".csv"):
        return pd.read_csv(io.BytesIO(payload))
    if lower.endswith(".xlsx"):
        return pd.read_excel(io.BytesIO(payload))
    raise ValueError("Only .csv and .xlsx are supported")

def sanitize_record(record: dict) -> dict:
    """Convert pandas/numpy values into PostgreSQL-safe native Python values."""
    cleaned = {}

    for key, value in record.items():
        if hasattr(value, "item") and not isinstance(value, (str, bytes)):
            try:
                value = value.item()
            except (ValueError, AttributeError):
                pass

        try:
            if value is None or bool(pd.isna(value)):
                cleaned[key] = None
                continue
        except (TypeError, ValueError):
            pass

        if isinstance(value, float) and not math.isfinite(value):
            cleaned[key] = None
            continue

        if hasattr(value, "to_pydatetime"):
            cleaned[key] = value.to_pydatetime()
            continue

        cleaned[key] = value

    for key in ("rooms", "total_buyer", "total_seller"):
        value = cleaned.get(key)

        if value is None:
            cleaned[key] = None
            continue

        try:
            numeric = float(value)
        except (TypeError, ValueError):
            cleaned[key] = None
            continue

        if not math.isfinite(numeric):
            cleaned[key] = None
        else:
            cleaned[key] = int(numeric)

    for key, value in list(cleaned.items()):
        if isinstance(value, float) and not math.isfinite(value):
            cleaned[key] = None

    return cleaned

def ingest_dataframe(db: Session, df: pd.DataFrame, filename: str) -> dict:
    clean = normalize_dld_dataframe(df)

    existing = {
        (x.transaction_number, x.instance_date)
        for x in db.query(
            Transaction.transaction_number,
            Transaction.instance_date,
        ).all()
    }

    batch = []
    skipped = 0

    for row_number, raw_record in enumerate(
        clean.to_dict(orient="records"),
        start=1,
    ):
        record = sanitize_record(raw_record)

        # Hard guard against NaN/invalid values reaching PostgreSQL INTEGER columns.
        for integer_field in ("rooms", "total_buyer", "total_seller"):
            value = record.get(integer_field)
            if value is not None and not isinstance(value, int):
                raise ValueError(
                    f"Row {row_number}: {integer_field} is not a valid integer/NULL "
                    f"after sanitization: {value!r}"
                )

        dt = record["instance_date"]
        key = (record["transaction_number"], dt)

        if key in existing:
            skipped += 1
            continue

        batch.append(Transaction(**record))
        existing.add(key)

    try:
        if batch:
            db.add_all(batch)

        run = IngestionRun(
            filename=filename,
            uploaded_at=datetime.now(timezone.utc).replace(tzinfo=None),
            raw_rows=int(len(df)),
            valid_rows=int(len(clean)),
            inserted_rows=len(batch),
            duplicates_skipped=skipped,
            status="completed",
        )
        db.add(run)
        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "raw_rows": int(len(df)),
        "valid_rows": int(len(clean)),
        "inserted": len(batch),
        "duplicates_skipped": skipped,
        "status": "completed",
    }

def py_median(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    return median(values)

def area_summary(db: Session, lookback_days: int):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - timedelta(days=lookback_days)

    area_names = [
        x[0] for x in
        db.query(Transaction.area_en)
        .filter(Transaction.instance_date >= cutoff)
        .distinct()
        .all()
        if x[0]
    ]

    result = []
    for area in area_names:
        rows = (
            db.query(Transaction)
            .filter(
                Transaction.instance_date >= cutoff,
                Transaction.area_en == area
            )
            .all()
        )

        prices = [x.transaction_value for x in rows if x.transaction_value is not None]
        ppsf = [x.price_per_sqft for x in rows if x.price_per_sqft is not None]

        result.append({
            "area": area,
            "transactions": len(rows),
            "average_price": round(sum(prices) / len(prices), 2) if prices else None,
            "median_price": round(py_median(prices), 2) if prices else None,
            "average_ppsf": round(sum(ppsf) / len(ppsf), 2) if ppsf else None,
            "median_ppsf": round(py_median(ppsf), 2) if ppsf else None,
            "min_price": round(min(prices), 2) if prices else None,
            "max_price": round(max(prices), 2) if prices else None,
        })

    result.sort(key=lambda x: x["transactions"], reverse=True)
    return result

def _weighted_mean(values, weights):
    total = sum(weights)
    if not total:
        raise ValueError("No valid weights")
    return sum(v * w for v, w in zip(values, weights)) / total

def value_property(db: Session, req: ValuationRequest) -> dict:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - timedelta(days=req.lookback_days)

    area = req.area.strip().upper()
    project = req.project.strip().upper() if req.project else None
    subtype = req.property_subtype.strip().upper() if req.property_subtype else None

    q = db.query(Transaction).filter(
        Transaction.area_en == area,
        Transaction.instance_date >= cutoff,
        Transaction.procedure_area_sqm > 0,
        Transaction.transaction_value > 0,
    )

    if req.bedrooms is not None:
        q = q.filter(Transaction.rooms == req.bedrooms)
    if subtype:
        q = q.filter(func.upper(Transaction.property_subtype_en) == subtype)
    if project:
        q = q.filter(Transaction.project_en == project)

    candidates = q.all()
    eligible = []

    for tx in candidates:
        size_diff = abs(tx.procedure_area_sqm - req.size_sqm) / req.size_sqm
        if size_diff > req.max_size_difference:
            continue

        recency_days = max(0, (now - tx.instance_date).days)
        size_penalty = min(50.0, size_diff * 100.0)
        recency_penalty = min(25.0, recency_days / req.lookback_days * 25.0)
        similarity = max(1.0, 100.0 - size_penalty - recency_penalty)

        eligible.append({
            "tx": tx,
            "size_diff": size_diff,
            "recency_days": recency_days,
            "similarity": similarity,
        })

    if len(eligible) < 3 and project:
        fallback_req = req.model_copy(update={"project": None})
        result = value_property(db, fallback_req)
        result["methodology"] = (
            "Project sample insufficient; automatic fallback to area-level comparables. "
            + result["methodology"]
        )
        return result

    if len(eligible) < 3:
        raise ValueError(
            f"Not enough comparable transactions. Found {len(eligible)}; minimum is 3."
        )

    eligible.sort(key=lambda x: x["similarity"], reverse=True)
    selected = eligible[:req.max_comparables]

    ppsf_values = [x["tx"].price_per_sqft for x in selected]
    weights = [x["similarity"] for x in selected]

    estimated_ppsf = _weighted_mean(ppsf_values, weights)
    estimated_value = estimated_ppsf * req.size_sqm * SQM_TO_SQFT

    med_ppsf = median(ppsf_values)
    mad = median([abs(x - med_ppsf) for x in ppsf_values])
    robust_sigma = 1.4826 * mad
    relative_spread = min(
        0.25,
        max(0.03, robust_sigma / med_ppsf if med_ppsf else 0.10)
    )

    estimated_low = estimated_value * (1 - relative_spread)
    estimated_high = estimated_value * (1 + relative_spread)

    avg_similarity = sum(weights) / len(weights)
    dispersion_penalty = min(
        30.0,
        (pstdev(ppsf_values) / estimated_ppsf * 100.0)
        if len(ppsf_values) > 1 else 0.0
    )
    confidence = max(
        0.0,
        min(
            100.0,
            min(40.0, len(selected) * 4.0)
            + avg_similarity * 0.45
            - dispersion_penalty
        )
    )

    ask_delta = None
    if req.asking_price:
        ask_delta = (estimated_value - req.asking_price) / estimated_value * 100

    comps = []
    for x in selected:
        tx = x["tx"]
        comps.append({
            "transaction_number": tx.transaction_number,
            "date": tx.instance_date.isoformat(),
            "area": tx.area_en,
            "project": tx.project_en,
            "bedrooms": tx.rooms,
            "property_subtype": tx.property_subtype_en,
            "size_sqm": round(tx.procedure_area_sqm, 2),
            "transaction_value": round(tx.transaction_value, 2),
            "price_per_sqft": round(tx.price_per_sqft, 2),
            "size_difference_pct": round(x["size_diff"] * 100, 2),
            "recency_days": x["recency_days"],
            "similarity_score": round(x["similarity"], 2),
        })

    return {
        "estimated_market_value": round(estimated_value, 2),
        "estimated_low": round(estimated_low, 2),
        "estimated_high": round(estimated_high, 2),
        "estimated_ppsf": round(estimated_ppsf, 2),
        "asking_price": req.asking_price,
        "asking_vs_estimate_pct": round(ask_delta, 2) if ask_delta is not None else None,
        "comparables_count": len(selected),
        "eligible_transactions": len(eligible),
        "confidence_score": round(confidence, 2),
        "methodology": (
            "V0 comparable valuation using area, optional project/subtype, bedrooms, "
            "size tolerance and recency. Not a licensed/formal valuation."
        ),
        "comparables": comps,
    }

@app.get("/", include_in_schema=False)
def dashboard_ui():
    return FileResponse(BASE_DIR / "index.html")

@app.get("/styles.css", include_in_schema=False)
def dashboard_css():
    return FileResponse(BASE_DIR / "styles.css", media_type="text/css")

@app.get("/app.js", include_in_schema=False)
def dashboard_js():
    return FileResponse(BASE_DIR / "app.js", media_type="application/javascript")

@app.get("/health")
def health():
    return {"status": "ok", "engine": "PropAgent Market Intelligence Engine V0.3.2"}

@app.get("/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)):
    total = db.query(func.count(Transaction.id)).scalar() or 0
    areas = db.query(func.count(func.distinct(Transaction.area_en))).scalar() or 0
    projects = db.query(func.count(func.distinct(Transaction.project_en))).filter(
        Transaction.project_en.isnot(None)
    ).scalar() or 0
    avg_price = db.query(func.avg(Transaction.transaction_value)).scalar()
    avg_ppsf = db.query(func.avg(Transaction.price_per_sqft)).scalar()
    latest_tx = db.query(func.max(Transaction.instance_date)).scalar()
    latest_ingestion = db.query(func.max(IngestionRun.uploaded_at)).scalar()

    return {
        "total_transactions": int(total),
        "areas_covered": int(areas),
        "projects_covered": int(projects),
        "average_price": round(float(avg_price), 2) if avg_price else None,
        "average_ppsf": round(float(avg_ppsf), 2) if avg_ppsf else None,
        "latest_transaction_date": latest_tx.isoformat() if latest_tx else None,
        "last_ingestion_date": latest_ingestion.isoformat() if latest_ingestion else None,
    }

@app.get("/meta/options")
def meta_options(db: Session = Depends(get_db)):
    areas = sorted([x[0] for x in db.query(Transaction.area_en).distinct().all() if x[0]])
    projects = sorted([x[0] for x in db.query(Transaction.project_en).distinct().all() if x[0]])
    subtypes = sorted([x[0] for x in db.query(Transaction.property_subtype_en).distinct().all() if x[0]])
    rooms = sorted([x[0] for x in db.query(Transaction.rooms).distinct().all() if x[0] is not None])
    return {
        "areas": areas,
        "projects": projects,
        "property_subtypes": subtypes,
        "bedrooms": rooms,
    }

@app.post("/ingest/dld")
async def ingest_dld(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        payload = await file.read()
        filename = file.filename or "upload.csv"
        df = read_upload(filename, payload)
        return ingest_dataframe(db, df, filename)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except SQLAlchemyError as exc:
        db.rollback()
        original = getattr(exc, "orig", exc)
        raise HTTPException(status_code=500, detail=f"Database ingestion failed: {original}")
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")

@app.get("/analytics/areas")
def analytics_areas(
    lookback_days: int = Query(default=365, ge=30, le=3650),
    db: Session = Depends(get_db)
):
    return {
        "lookback_days": lookback_days,
        "areas": area_summary(db, lookback_days)
    }

@app.post("/valuation")
def valuation(req: ValuationRequest, db: Session = Depends(get_db)):
    try:
        return value_property(db, req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
