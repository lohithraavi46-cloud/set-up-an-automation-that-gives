from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

class Farmer(Base):
    __tablename__ = "farmers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(25), unique=True)
    village: Mapped[str] = mapped_column(String(100))
    language: Mapped[str] = mapped_column(String(12), default="English")
    pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fields: Mapped[list["Field"]] = relationship(back_populates="farmer")
    crops: Mapped[list["Crop"]] = relationship(back_populates="farmer")

class Field(Base):
    __tablename__ = "fields"
    id: Mapped[int] = mapped_column(primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id"))
    name: Mapped[str] = mapped_column(String(100))
    area_acres: Mapped[float] = mapped_column(Float)
    location: Mapped[str] = mapped_column(String(150))
    ownership: Mapped[str] = mapped_column(String(12), default="Owned")
    notes: Mapped[str] = mapped_column(Text, default="")
    farmer: Mapped["Farmer"] = relationship(back_populates="fields")
    crops: Mapped[list["Crop"]] = relationship(back_populates="field")

class Crop(Base):
    __tablename__ = "crops"
    id: Mapped[int] = mapped_column(primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id"))
    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id"))
    name: Mapped[str] = mapped_column(String(80))
    variety: Mapped[str] = mapped_column(String(80))
    area_acres: Mapped[float] = mapped_column(Float)
    planting_date: Mapped[date] = mapped_column(Date)
    expected_harvest_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    harvest_quantity_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_harvest_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_yield_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_status: Mapped[str] = mapped_column(String(40), default="Growing")
    health_status: Mapped[str] = mapped_column(String(40), default="Monitor")
    storage_status: Mapped[str] = mapped_column(String(60), default="Not arranged")
    selling_status: Mapped[str] = mapped_column(String(60), default="Not listed")
    notes: Mapped[str] = mapped_column(Text, default="")
    asking_price_per_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_selling_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    quality_grade: Mapped[str | None] = mapped_column(String(80), nullable=True)
    market_notes: Mapped[str] = mapped_column(Text, default="")
    farmer: Mapped["Farmer"] = relationship(back_populates="crops")
    field: Mapped["Field"] = relationship(back_populates="crops")
    health_history: Mapped[list["CropHealthHistory"]] = relationship(back_populates="crop", cascade="all, delete-orphan")
    diagnoses: Mapped[list["Diagnosis"]] = relationship(back_populates="crop", cascade="all, delete-orphan")
    treatments: Mapped[list["Treatment"]] = relationship(back_populates="crop", cascade="all, delete-orphan")

class CropHealthHistory(Base):
    __tablename__ = "crop_health_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id"))
    status: Mapped[str] = mapped_column(String(50))
    note: Mapped[str] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    crop: Mapped["Crop"] = relationship(back_populates="health_history")

class Diagnosis(Base):
    __tablename__ = "diagnoses"
    id: Mapped[int] = mapped_column(primary_key=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id"))
    result: Mapped[str] = mapped_column(String(120))
    confidence: Mapped[float] = mapped_column(Float)
    recommendation: Mapped[str] = mapped_column(Text)
    image_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    crop: Mapped["Crop"] = relationship(back_populates="diagnoses")

class Treatment(Base):
    __tablename__ = "treatments"
    id: Mapped[int] = mapped_column(primary_key=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id"))
    treatment: Mapped[str] = mapped_column(Text)
    scheduled_date: Mapped[date] = mapped_column(Date)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    crop: Mapped["Crop"] = relationship(back_populates="treatments")

class Buyer(Base):
    __tablename__ = "buyers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    crop: Mapped[str] = mapped_column(String(80))
    min_quantity_kg: Mapped[float] = mapped_column(Float)
    max_quantity_kg: Mapped[float] = mapped_column(Float)
    price_per_kg: Mapped[float] = mapped_column(Float)
    location: Mapped[str] = mapped_column(String(120))
    distance_km: Mapped[float] = mapped_column(Float)
    required_date: Mapped[date] = mapped_column(Date)
    quality_requirement: Mapped[str] = mapped_column(String(160))

class MarketPrice(Base):
    __tablename__ = "market_prices"
    id: Mapped[int] = mapped_column(primary_key=True)
    crop: Mapped[str] = mapped_column(String(80))
    market: Mapped[str] = mapped_column(String(100))
    price_per_kg: Mapped[float] = mapped_column(Float)
    recorded_date: Mapped[date] = mapped_column(Date)
    source_label: Mapped[str] = mapped_column(String(120), default="Demo data")

class StorageFacility(Base):
    __tablename__ = "storage_facilities"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    capacity_kg: Mapped[float] = mapped_column(Float)
    available_capacity_kg: Mapped[float] = mapped_column(Float)
    cost_per_kg_day: Mapped[float] = mapped_column(Float)
    distance_km: Mapped[float] = mapped_column(Float)
    storage_type: Mapped[str] = mapped_column(String(80))
    crops_supported: Mapped[str] = mapped_column(String(255))

class Transporter(Base):
    __tablename__ = "transporters"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    vehicle_type: Mapped[str] = mapped_column(String(80))
    capacity_kg: Mapped[float] = mapped_column(Float)
    cost: Mapped[float] = mapped_column(Float)
    location: Mapped[str] = mapped_column(String(120))
    available: Mapped[bool] = mapped_column(Boolean, default=True)

class ExpertRequest(Base):
    __tablename__ = "expert_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id"))
    image_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    diagnosis: Mapped[str] = mapped_column(String(120))
    confidence: Mapped[float] = mapped_column(Float)
    farmer_notes: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="Requested")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class WeatherAlert(Base):
    __tablename__ = "weather_alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id"))
    alert_key: Mapped[str] = mapped_column(String(160), unique=True)
    category: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(180))
    body: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    id: Mapped[int] = mapped_column(primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id"), unique=True)
    browser_permission: Mapped[str] = mapped_column(String(30), default="default")
    push_subscription: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class FarmTransaction(Base):
    __tablename__ = "farm_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id"))
    type: Mapped[str] = mapped_column(String(3))  # IN or OUT
    amount: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(80))
    transaction_date: Mapped[date] = mapped_column(Date)
    crop_id: Mapped[int | None] = mapped_column(ForeignKey("crops.id"), nullable=True)
    field_id: Mapped[int | None] = mapped_column(ForeignKey("fields.id"), nullable=True)
    buyer: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class FarmAsset(Base):
    __tablename__ = "farm_assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id"), unique=True)
    land_value: Mapped[float] = mapped_column(Float, default=0)
    machinery_value: Mapped[float] = mapped_column(Float, default=0)
    livestock_value: Mapped[float] = mapped_column(Float, default=0)
    crop_value: Mapped[float] = mapped_column(Float, default=0)
    farm_cash: Mapped[float] = mapped_column(Float, default=0)

class FinancialGoal(Base):
    __tablename__ = "financial_goals"
    id: Mapped[int] = mapped_column(primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id"))
    name: Mapped[str] = mapped_column(String(100))
    target_amount: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
