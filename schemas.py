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
