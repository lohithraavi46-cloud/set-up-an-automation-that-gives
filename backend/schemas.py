from datetime import date
from pydantic import BaseModel, Field

class FarmerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=7, max_length=25)
    village: str = Field(min_length=2, max_length=100)
    language: str = "English"

class RegisterRequest(FarmerCreate):
    pin: str = Field(min_length=4, max_length=8, pattern=r"^\d+$")

class LoginRequest(BaseModel):
    phone: str = Field(min_length=7, max_length=25)
    pin: str = Field(min_length=4, max_length=8, pattern=r"^\d+$")

class FarmerPreferenceUpdate(BaseModel):
    language: str = Field(pattern=r"^(English|Telugu)$")

class NotificationPreferenceRequest(BaseModel):
    farmer_id: int
    permission: str = Field(pattern=r"^(granted|denied|default|unsupported)$")
    subscription: dict | None = None

class NotificationReadRequest(BaseModel):
    farmer_id: int
    alert_ids: list[int] = []
    clear_all: bool = False

class TransactionCreate(BaseModel):
    type: str = Field(pattern=r"^(IN|OUT)$")
    amount: float = Field(gt=0)
    category: str = Field(min_length=1, max_length=80)
    transaction_date: date
    crop_id: int | None = None
    field_id: int | None = None
    buyer: str | None = Field(default=None, max_length=120)
    note: str = Field(default="", max_length=1000)

class AssetUpdate(BaseModel):
    land_value: float = Field(default=0, ge=0)
    machinery_value: float = Field(default=0, ge=0)
    livestock_value: float = Field(default=0, ge=0)
    crop_value: float = Field(default=0, ge=0)
    farm_cash: float = Field(default=0, ge=0)

class FieldFinanceUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    area_acres: float = Field(gt=0)
    location: str = Field(min_length=1, max_length=150)
    ownership: str = Field(default="Owned", pattern=r"^(Owned|Leased)$")
    notes: str = Field(default="", max_length=1000)

class FinancialGoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    target_amount: float = Field(gt=0)

class CropCreate(BaseModel):
    farmer_id: int
    field_id: int
    name: str
    variety: str
    area_acres: float = Field(gt=0)
    planting_date: date
    expected_harvest_date: date | None = None

class CropUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    variety: str | None = Field(default=None, min_length=1, max_length=80)
    field_name: str | None = Field(default=None, min_length=1, max_length=100)
    area_acres: float | None = Field(default=None, gt=0)
    planting_date: date | None = None
    expected_harvest_date: date | None = None
    actual_harvest_date: date | None = None
    actual_yield_kg: float | None = Field(default=None, ge=0)
    health_status: str | None = None
    market_status: str | None = None
    harvest_quantity_kg: float | None = Field(default=None, ge=0)
    storage_status: str | None = None
    selling_status: str | None = None
    notes: str | None = Field(default=None, max_length=2000)
    asking_price_per_kg: float | None = Field(default=None, ge=0)
    expected_selling_date: date | None = None
    quality_grade: str | None = Field(default=None, max_length=80)
    market_notes: str | None = Field(default=None, max_length=2000)

class DiagnoseRequest(BaseModel):
    crop_id: int
    image_reference: str | None = None
    farmer_notes: str = ""
    simulated_confidence: float | None = Field(default=None, ge=0, le=1)

class MatchRequest(BaseModel):
    crop: str
    quantity_kg: float = Field(gt=0)
    destination: str | None = None
    pickup_date: date | None = None

class SellStoreRequest(BaseModel):
    quantity_kg: float = Field(gt=0)
    current_price_per_kg: float = Field(ge=0)
    future_price_per_kg: float = Field(ge=0)
    storage_cost_per_kg_day: float = Field(ge=0)
    transport_cost: float = Field(ge=0)
    duration_days: int = Field(ge=0, le=365)

class ExpertRequestCreate(BaseModel):
    crop_id: int
    image_reference: str | None = None
    diagnosis: str
    confidence: float = Field(ge=0, le=1)
    farmer_notes: str = ""
