from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, Index, UniqueConstraint
)
from app.database import Base

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    source = Column(String(50), nullable=False, default="DLD")
    transaction_number = Column(String(100), nullable=False)
    instance_date = Column(DateTime, nullable=False)

    group_en = Column(String(100))
    procedure_en = Column(String(100))
    is_offplan = Column(Boolean)
    is_freehold = Column(Boolean)
    usage_en = Column(String(100))

    area_en = Column(String(255), index=True)
    master_project_en = Column(String(255), index=True)
    project_en = Column(String(255), index=True)

    property_type_en = Column(String(100), index=True)
    property_subtype_en = Column(String(100), index=True)

    transaction_value = Column(Float, nullable=False)
    procedure_area_sqm = Column(Float, nullable=False)
    actual_area_sqm = Column(Float)
    rooms = Column(Integer, index=True)
    parking = Column(String(50))

    nearest_metro_en = Column(String(255))
    nearest_mall_en = Column(String(255))
    nearest_landmark_en = Column(String(255))

    total_buyer = Column(Integer)
    total_seller = Column(Integer)

    price_per_sqm = Column(Float, index=True)
    price_per_sqft = Column(Float, index=True)

    __table_args__ = (
        UniqueConstraint(
            "source", "transaction_number", "instance_date",
            name="uq_transaction_source_number_date"
        ),
        Index(
            "ix_comparable_search",
            "area_en", "project_en", "property_subtype_en",
            "rooms", "instance_date"
        ),
    )
