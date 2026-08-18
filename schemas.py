from typing import Optional
from pydantic import BaseModel, Field

class ValuationRequest(BaseModel):
    area: str
    project: Optional[str] = None
    property_subtype: Optional[str] = None
    bedrooms: Optional[int] = Field(default=None, ge=0, le=20)
    size_sqm: float = Field(gt=0)
    asking_price: Optional[float] = Field(default=None, gt=0)
    lookback_days: int = Field(default=365, ge=30, le=3650)
    max_size_difference: float = Field(default=0.35, gt=0, le=1.0)
    max_comparables: int = Field(default=10, ge=3, le=30)

class ComparableOut(BaseModel):
    transaction_number: str
    date: str
    area: Optional[str]
    project: Optional[str]
    bedrooms: Optional[int]
    property_subtype: Optional[str]
    size_sqm: float
    transaction_value: float
    price_per_sqft: float
    size_difference_pct: float
    recency_days: int
    similarity_score: float

class ValuationResponse(BaseModel):
    estimated_market_value: float
    estimated_low: float
    estimated_high: float
    estimated_ppsf: float
    asking_price: Optional[float]
    asking_vs_estimate_pct: Optional[float]
    comparables_count: int
    eligible_transactions: int
    confidence_score: float
    methodology: str
    comparables: list[ComparableOut]
