import math
import requests
import base64
import hashlib
import hmac
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from fastapi import Depends, FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import json
import numpy as np
import onnxruntime as ort
from PIL import Image
from huggingface_hub import hf_hub_download
from .database import Base, engine, get_db, run_migrations
from .models import Buyer, Crop, CropHealthHistory, Diagnosis, ExpertRequest, FarmAsset, FarmTransaction, Farmer, Field, FinancialGoal, MarketPrice, NotificationPreference, StorageFacility, Transporter, WeatherAlert
from .schemas import AssetUpdate, CropCreate, CropUpdate, DiagnoseRequest, ExpertRequestCreate, FarmerCreate, FarmerPreferenceUpdate, FieldFinanceUpdate, FinancialGoalCreate, LoginRequest, MatchRequest, NotificationPreferenceRequest, NotificationReadRequest, RegisterRequest, SellStoreRequest, TransactionCreate
from .seed import seed
from .services.disease_model import analyze_image

UPLOAD_DIRECTORY = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIRECTORY.mkdir(exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    run_migrations()
    with next(get_db()) as db:
        seed(db)
        # Existing demo farmer remains usable after authentication is added.
        demo_farmer = db.query(Farmer).filter_by(phone="9000000000").first()
        if demo_farmer and not demo_farmer.pin_hash:
            demo_farmer.pin_hash = hash_pin("1234")
            db.commit()
    yield

app = FastAPI(title="Rythu Sodara API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

def crop_dict(c: Crop):
    age = (date.today() - c.planting_date).days
    return {"id":c.id,"farmer_id":c.farmer_id,"field_id":c.field_id,"field_name":c.field.name if c.field else "","name":c.name,"variety":c.variety,"area_acres":c.area_acres,"planting_date":str(c.planting_date),"crop_age_days":age,"expected_harvest_date":str(c.expected_harvest_date) if c.expected_harvest_date else None,"actual_harvest_date":str(c.actual_harvest_date) if c.actual_harvest_date else None,"harvest_quantity_kg":c.harvest_quantity_kg,"actual_yield_kg":c.actual_yield_kg,"market_status":c.market_status,"health_status":c.health_status,"storage_status":c.storage_status,"selling_status":c.selling_status,"notes":c.notes,"asking_price_per_kg":c.asking_price_per_kg,"expected_selling_date":str(c.expected_selling_date) if c.expected_selling_date else None,"quality_grade":c.quality_grade,"market_notes":c.market_notes}

def hash_pin(pin: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 310_000)
    return base64.b64encode(salt + digest).decode()

def pin_matches(pin: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        raw = base64.b64decode(stored.encode())
        return hmac.compare_digest(raw[16:], hashlib.pbkdf2_hmac("sha256", pin.encode(), raw[:16], 310_000))
    except (ValueError, TypeError):
        return False

def farmer_payload(farmer: Farmer) -> dict:
    return {"id": farmer.id, "name": farmer.name, "phone": farmer.phone, "village": farmer.village, "language": farmer.language}

@app.get("/api/health")
def health(): return {"status":"ok","mode":"mixed-data","message":"Rythu Sodara API is ready"}

@app.post("/api/farmers", status_code=201)
def create_farmer(payload: FarmerCreate, db: Session=Depends(get_db)):
    if db.query(Farmer).filter_by(phone=payload.phone).first(): raise HTTPException(409,"Phone number already exists")
    farmer=Farmer(**payload.model_dump()); db.add(farmer); db.commit(); db.refresh(farmer); return {"id":farmer.id, **payload.model_dump()}

@app.post("/api/auth/register", status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(Farmer).filter_by(phone=payload.phone).first():
        raise HTTPException(409, "This mobile number is already registered.")
    farmer = Farmer(name=payload.name, phone=payload.phone, village=payload.village, language=payload.language, pin_hash=hash_pin(payload.pin))
    db.add(farmer); db.flush()
    field = Field(farmer_id=farmer.id, name="My field", area_acres=.01, location=payload.village)
    db.add(field); db.flush()
    crop = Crop(farmer_id=farmer.id, field_id=field.id, name="My crop", variety="Not set", area_acres=.01, planting_date=date.today(), market_status="Setup needed", health_status="Not recorded", notes="Update this crop passport with your field details.")
    db.add(crop); db.commit(); db.refresh(farmer)
    return {"farmer": farmer_payload(farmer), "message": "Account created. Update your crop passport to begin."}

@app.post("/api/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    farmer = db.query(Farmer).filter_by(phone=payload.phone).first()
    if not farmer or not pin_matches(payload.pin, farmer.pin_hash):
        raise HTTPException(401, "Mobile number or PIN is incorrect.")
    return {"farmer": farmer_payload(farmer)}

@app.get("/api/farmers/{farmer_id}")
def get_farmer(farmer_id:int, db:Session=Depends(get_db)):
    f=db.get(Farmer,farmer_id)
    if not f: raise HTTPException(404,"Farmer not found")
    return {"id":f.id,"name":f.name,"village":f.village,"language":f.language,"fields":[{"id":x.id,"name":x.name,"area_acres":x.area_acres} for x in f.fields]}

@app.put("/api/farmers/{farmer_id}/preferences")
def update_farmer_preferences(farmer_id: int, payload: FarmerPreferenceUpdate, db: Session = Depends(get_db)):
    farmer = db.get(Farmer, farmer_id)
    if not farmer:
        raise HTTPException(404, "Farmer not found")
    farmer.language = payload.language
    db.commit()
    return farmer_payload(farmer)

@app.post("/api/crops",status_code=201)
def create_crop(payload:CropCreate,db:Session=Depends(get_db)):
    if not db.get(Farmer,payload.farmer_id) or not db.get(Field,payload.field_id): raise HTTPException(400,"Valid farmer and field are required")
    c=Crop(**payload.model_dump()); db.add(c); db.commit(); db.refresh(c); return crop_dict(c)

@app.get("/api/crops")
def list_crops(farmer_id: int | None = None, db:Session=Depends(get_db)):
    query = db.query(Crop)
    if farmer_id is not None:
        query = query.filter_by(farmer_id=farmer_id)
    return [crop_dict(c) for c in query.all()]

@app.get("/api/crops/{crop_id}")
def get_crop(crop_id:int,db:Session=Depends(get_db)):
    c=db.get(Crop,crop_id)
    if not c: raise HTTPException(404,"Crop not found")
    out=crop_dict(c)
    events = [
        {"date":str(c.planting_date),"type":"Planted","status":"Crop passport","note":f"{c.name} · {c.variety}"},
        *[{"date":str(h.recorded_at.date()),"type":"Health update","status":h.status,"note":h.note} for h in c.health_history],
        *[{"date":str(d.created_at.date()),"type":"Diagnosis","status":f"{d.confidence:.0%} confidence","note":d.result} for d in c.diagnoses],
        *[{"date":str(t.scheduled_date),"type":"Care / treatment","status":"Completed" if t.completed else "Planned","note":t.treatment} for t in c.treatments],
    ]
    if c.actual_harvest_date:
        events.append({"date":str(c.actual_harvest_date),"type":"Harvest","status":"Recorded","note":f"Actual yield: {c.actual_yield_kg or 0} kg"})
    out["passport"] = sorted(events, key=lambda event: event["date"], reverse=True)
    return out

@app.put("/api/crops/{crop_id}")
def update_crop(crop_id:int,payload:CropUpdate,db:Session=Depends(get_db)):
    c=db.get(Crop,crop_id)
    if not c: raise HTTPException(404,"Crop not found")
    values = payload.model_dump(exclude_none=True)
    field_name = values.pop("field_name", None)
    if field_name:
        c.field.name = field_name
    for k,v in values.items(): setattr(c,k,v)
    db.commit(); db.refresh(c); return crop_dict(c)

@app.post("/api/diagnose",status_code=201)
def diagnose(payload:DiagnoseRequest,db:Session=Depends(get_db)):
    c=db.get(Crop,payload.crop_id)
    if not c: raise HTTPException(404,"Crop not found")
    confidence=payload.simulated_confidence if payload.simulated_confidence is not None else .62
    result="Possible leaf curl stress (demo assessment)"
    recommendation="Inspect spread, record photos, and obtain expert advice before applying any crop protection product."
    d=Diagnosis(crop_id=c.id,result=result,confidence=confidence,recommendation=recommendation,image_reference=payload.image_reference); db.add(d); db.commit(); db.refresh(d)
    return {"id":d.id,"diagnosis":result,"confidence":confidence,"recommended_action":recommendation,"expert_review_recommended":confidence<.75,"disclaimer":"Demo assessment only — not a guaranteed disease diagnosis."}

@app.post("/api/diagnose/upload", status_code=201)
async def diagnose_uploaded_image(
    crop_id: int = Form(...),
    image: UploadFile = File(...),
    farmer_notes: str = Form(""),
    db: Session = Depends(get_db),
):
    """Run the configured local ONNX classifier over an uploaded crop image."""
    crop = db.get(Crop, crop_id)
    if not crop:
        raise HTTPException(404, "Crop not found")
    if image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(415, "Upload a JPG, PNG, or WebP image.")
    suffix = Path(image.filename or "crop.jpg").suffix.lower() or ".jpg"
    saved_name = f"{uuid4().hex}{suffix}"
    saved_path = UPLOAD_DIRECTORY / saved_name
    content = await image.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "Image must be 10 MB or smaller.")
    saved_path.write_bytes(content)
    try:
        result = analyze_image(saved_path)
    except Exception as error:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(503, f"Crop model is unavailable: {error}") from error
    confidence = result["confidence"]
    recommendation = (
        "The model confidence is high enough to review the label and inspect affected plants."
        if confidence >= .75
        else "The model is uncertain. Inspect the crop and request an agriculture expert review before treatment."
    )
    diagnosis = Diagnosis(
        crop_id=crop.id,
        result=result["diagnosis"],
        confidence=confidence,
        recommendation=recommendation,
        image_reference=saved_name,
    )
    db.add(diagnosis)
    db.commit()
    db.refresh(diagnosis)
    return {
        "id": diagnosis.id,
        "diagnosis": result["diagnosis"],
        "confidence": confidence,
        "top_predictions": result["top_predictions"],
        "recommended_action": recommendation,
        "expert_review_recommended": confidence < .75,
        "model": result["model"],
        "disclaimer": "Model output is a screening aid, not a guaranteed disease diagnosis or treatment prescription.",
    }

@app.get("/api/diagnosis/{crop_id}")
def diagnosis(crop_id:int,db:Session=Depends(get_db)):
    items=db.query(Diagnosis).filter_by(crop_id=crop_id).order_by(Diagnosis.created_at.desc()).all()
    return [{"id":d.id,"diagnosis":d.result,"confidence":d.confidence,"recommended_action":d.recommendation,"created_at":str(d.created_at)} for d in items]

@app.get("/api/decisions/{crop_id}")
def decision(crop_id:int,db:Session=Depends(get_db)):
    c=db.get(Crop,crop_id)
    if not c: raise HTTPException(404,"Crop not found")
    latest=db.query(Diagnosis).filter_by(crop_id=c.id).order_by(Diagnosis.created_at.desc()).first()
    return {"recommended_next_action":"Request expert review and inspect the affected patch today","reason":"The crop passport has a health alert and the demo diagnosis confidence is below the expert-review threshold.","urgency":"High","confidence":.71,"inputs_used":{"crop_age_days":(date.today()-c.planting_date).days,"health":c.health_status,"diagnosis":latest.result if latest else "No diagnosis","weather":"Demo placeholder; connect a weather provider","market":"Demo scenario price data","buyer_demand":"2 matching demo buyers","storage":"Demo capacity available","logistics":"Demo vehicle availability"},"disclaimer":"This is a decision-support scenario, not a prediction or agronomy guarantee."}

@app.get("/api/market/prices")
def prices(db:Session=Depends(get_db)): return [{"crop":x.crop,"market":x.market,"price_per_kg":x.price_per_kg,"date":str(x.recorded_date),"label":x.source_label} for x in db.query(MarketPrice).all()]

@app.get("/api/weather")
def weather(lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180), farmer_id: int | None = None, db: Session = Depends(get_db)):
    """Fetch live current weather and a 10-day forecast from Open-Meteo."""
    params = {
        "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 10,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,wind_direction_10m",
        "hourly": "precipitation_probability",
        "daily": "weather_code,temperature_2m_min,temperature_2m_max,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,wind_direction_10m_dominant",
    }
    try:
        response = requests.get(OPEN_METEO_URL, params=params, timeout=18)
        response.raise_for_status()
        raw = response.json()
    except (requests.RequestException, ValueError) as error:
        raise HTTPException(502, "Weather data is temporarily unavailable. Try refresh later.") from error
    current = raw.get("current", {})
    daily = raw.get("daily", {})
    hourly = raw.get("hourly", {})
    hourly_times = hourly.get("time", [])
    hourly_rain = hourly.get("precipitation_probability", [])
    forecast = []
    for index, day in enumerate(daily.get("time", [])[:10]):
        matching = [hourly_rain[i] for i, stamp in enumerate(hourly_times) if stamp.startswith(day) and hourly_rain[i] is not None]
        code = daily["weather_code"][index]
        forecast.append({"date":day,"condition":WEATHER_CODES.get(code, "Weather update"),"icon":weather_icon(code),"min_temp_c":daily["temperature_2m_min"][index],"max_temp_c":daily["temperature_2m_max"][index],"rain_probability":daily["precipitation_probability_max"][index] if daily.get("precipitation_probability_max") else (max(matching) if matching else None),"precipitation_mm":daily["precipitation_sum"][index],"wind_speed_kmh":daily["wind_speed_10m_max"][index],"wind_direction_deg":daily["wind_direction_10m_dominant"][index]})
    crop = db.query(Crop).filter_by(farmer_id=farmer_id).first() if farmer_id else None
    advisory, alerts = weather_advisory(forecast, crop)
    if farmer_id:
        for alert in alerts: create_alert(db, farmer_id, alert["key"], alert["category"], alert["title"], alert["body"])
        db.commit()
    rain_window = next(({"date":d["date"],"rain_probability":d["rain_probability"],"precipitation_mm":d["precipitation_mm"]} for d in forecast if (d["rain_probability"] or 0) >= 50 or d["precipitation_mm"] >= 3), None)
    return {"source":"Open-Meteo","updated_at":datetime.now(timezone.utc).isoformat(),"coordinates_used":{"latitude":round(lat,3),"longitude":round(lon,3)},"current":{"temperature_c":current.get("temperature_2m"),"feels_like_c":current.get("apparent_temperature"),"humidity_percent":current.get("relative_humidity_2m"),"precipitation_mm":current.get("precipitation"),"condition":WEATHER_CODES.get(current.get("weather_code"),"Weather update"),"icon":weather_icon(current.get("weather_code",-1)),"wind_speed_kmh":current.get("wind_speed_10m"),"wind_direction_deg":current.get("wind_direction_10m"),"rain_probability":forecast[0]["rain_probability"] if forecast else None},"forecast":forecast,"rain_window":rain_window,"advisory":advisory,"forecast_disclaimer":"Weather forecast — not a guarantee."}

@app.get("/api/notifications")
def notifications(farmer_id: int, db: Session = Depends(get_db)):
    records = db.query(WeatherAlert).filter_by(farmer_id=farmer_id).order_by(WeatherAlert.created_at.desc()).limit(30).all()
    return [{"id":x.id,"category":x.category,"title":x.title,"body":x.body,"is_read":x.is_read,"created_at":x.created_at.isoformat()} for x in records]

@app.post("/api/notifications/read")
def read_notifications(payload: NotificationReadRequest, db: Session = Depends(get_db)):
    query = db.query(WeatherAlert).filter_by(farmer_id=payload.farmer_id)
    if payload.clear_all:
        query.delete(synchronize_session=False)
    elif payload.alert_ids:
        query.filter(WeatherAlert.id.in_(payload.alert_ids)).update({WeatherAlert.is_read: True}, synchronize_session=False)
    db.commit()
    return {"ok":True}

@app.post("/api/notifications/subscribe")
def notification_subscribe(payload: NotificationPreferenceRequest, db: Session = Depends(get_db)):
    record = db.query(NotificationPreference).filter_by(farmer_id=payload.farmer_id).first()
    if not record:
        record = NotificationPreference(farmer_id=payload.farmer_id)
        db.add(record)
    record.browser_permission = payload.permission
    record.push_subscription = json.dumps(payload.subscription) if payload.subscription else None
    db.commit()
    return {"ok":True,"permission":record.browser_permission,"push_configured":bool(record.push_subscription)}

def transaction_data(item: FarmTransaction) -> dict:
    return {"id":item.id,"type":item.type,"amount":item.amount,"category":item.category,"date":str(item.transaction_date),"crop_id":item.crop_id,"field_id":item.field_id,"buyer":item.buyer,"note":item.note}

@app.get("/api/finance/transactions")
def finance_transactions(farmer_id: int, type: str | None = None, crop_id: int | None = None, category: str | None = None, date_from: date | None = None, date_to: date | None = None, newest: bool = True, db: Session = Depends(get_db)):
    query = db.query(FarmTransaction).filter_by(farmer_id=farmer_id)
    if type in {"IN","OUT"}: query=query.filter_by(type=type)
    if crop_id: query=query.filter_by(crop_id=crop_id)
    if category: query=query.filter_by(category=category)
    if date_from: query=query.filter(FarmTransaction.transaction_date >= date_from)
    if date_to: query=query.filter(FarmTransaction.transaction_date <= date_to)
    order = FarmTransaction.transaction_date.desc() if newest else FarmTransaction.transaction_date.asc()
    return [transaction_data(x) for x in query.order_by(order, FarmTransaction.id.desc()).all()]

@app.post("/api/finance/transactions", status_code=201)
def add_finance_transaction(farmer_id: int, payload: TransactionCreate, db: Session = Depends(get_db)):
    if not db.get(Farmer, farmer_id): raise HTTPException(404, "Farmer not found")
    if payload.crop_id:
        crop=db.get(Crop,payload.crop_id)
        if not crop or crop.farmer_id != farmer_id: raise HTTPException(403,"Invalid crop for this farmer")
    if payload.field_id:
        field=db.get(Field,payload.field_id)
        if not field or field.farmer_id != farmer_id: raise HTTPException(403,"Invalid field for this farmer")
    item=FarmTransaction(farmer_id=farmer_id, **payload.model_dump());db.add(item);db.commit();db.refresh(item);return transaction_data(item)

@app.put("/api/finance/transactions/{transaction_id}")
def update_finance_transaction(transaction_id: int, farmer_id: int, payload: TransactionCreate, db: Session = Depends(get_db)):
    item=db.get(FarmTransaction,transaction_id)
    if not item: raise HTTPException(404,"Transaction not found")
    if item.farmer_id != farmer_id: raise HTTPException(403,"This transaction belongs to another farmer")
    for key,value in payload.model_dump().items():setattr(item,key,value)
    db.commit();db.refresh(item);return transaction_data(item)

@app.delete("/api/finance/transactions/{transaction_id}", status_code=204)
def delete_finance_transaction(transaction_id: int, farmer_id: int, db: Session = Depends(get_db)):
    item=db.get(FarmTransaction,transaction_id)
    if not item: raise HTTPException(404,"Transaction not found")
    if item.farmer_id != farmer_id: raise HTTPException(403,"This transaction belongs to another farmer")
    db.delete(item);db.commit()

@app.get("/api/finance/summary")
def finance_summary(farmer_id:int, db:Session=Depends(get_db)):
    items=db.query(FarmTransaction).filter_by(farmer_id=farmer_id).all()
    income=sum(x.amount for x in items if x.type=="IN"); expenses=sum(x.amount for x in items if x.type=="OUT")
    largest=max((x for x in items if x.type=="OUT"),key=lambda x:x.amount,default=None)
    crops=db.query(Crop).filter_by(farmer_id=farmer_id).all(); profits=[]
    for crop in crops:
        crop_items=[x for x in items if x.crop_id==crop.id]; crop_income=sum(x.amount for x in crop_items if x.type=="IN"); crop_expenses=sum(x.amount for x in crop_items if x.type=="OUT")
        profits.append({"crop_id":crop.id,"crop":crop.name,"investment":crop_expenses,"income":crop_income,"expenses":crop_expenses,"net_profit":crop_income-crop_expenses,"transaction_count":len(crop_items)})
    highest=max(profits,key=lambda x:x["income"],default=None)
    return {"total_income":income,"total_expenses":expenses,"total_investment":expenses,"net_cash_flow":income-expenses,"largest_expense_category":largest.category if largest else None,"highest_income_crop":highest["crop"] if highest and highest["income"] else None,"crop_profit":profits,"transaction_count":len(items),"label":"Farmer-entered actual values; profit may be incomplete until all costs and income are recorded."}

@app.get("/api/finance/assets")
def get_assets(farmer_id:int,db:Session=Depends(get_db)):
    asset=db.query(FarmAsset).filter_by(farmer_id=farmer_id).first()
    values={key:getattr(asset,key) if asset else 0 for key in ["land_value","machinery_value","livestock_value","crop_value","farm_cash"]}
    return {**values,"estimated_total":sum(values.values()),"label":"Farmer-entered estimate"}

@app.put("/api/finance/assets")
def update_assets(farmer_id:int,payload:AssetUpdate,db:Session=Depends(get_db)):
    asset=db.query(FarmAsset).filter_by(farmer_id=farmer_id).first()
    if not asset: asset=FarmAsset(farmer_id=farmer_id);db.add(asset)
    for key,value in payload.model_dump().items():setattr(asset,key,value)
    db.commit();return get_assets(farmer_id,db)

@app.get("/api/finance/land")
def land_records(farmer_id:int,db:Session=Depends(get_db)):
    fields=db.query(Field).filter_by(farmer_id=farmer_id).all()
    return [{"id":f.id,"name":f.name,"area_acres":f.area_acres,"location":f.location,"ownership":f.ownership,"notes":f.notes,"crops":[c.name for c in f.crops]} for f in fields]

@app.post("/api/finance/land", status_code=201)
def add_land(farmer_id: int, payload: FieldFinanceUpdate, db: Session = Depends(get_db)):
    if not db.get(Farmer, farmer_id): raise HTTPException(404, "Farmer not found")
    field = Field(farmer_id=farmer_id, **payload.model_dump()); db.add(field); db.commit(); db.refresh(field)
    return {"id":field.id,"name":field.name,"area_acres":field.area_acres,"location":field.location,"ownership":field.ownership,"notes":field.notes,"crops":[]}

@app.put("/api/finance/land/{field_id}")
def update_land(field_id: int, farmer_id: int, payload: FieldFinanceUpdate, db: Session = Depends(get_db)):
    field=db.get(Field, field_id)
    if not field: raise HTTPException(404, "Field not found")
    if field.farmer_id != farmer_id: raise HTTPException(403, "This field belongs to another farmer")
    for key,value in payload.model_dump().items(): setattr(field,key,value)
    db.commit(); return {"id":field.id,"name":field.name,"area_acres":field.area_acres,"location":field.location,"ownership":field.ownership,"notes":field.notes,"crops":[c.name for c in field.crops]}

@app.get("/api/finance/goals")
def finance_goals(farmer_id: int, db: Session = Depends(get_db)):
    cash=sum(x.amount if x.type=="IN" else -x.amount for x in db.query(FarmTransaction).filter_by(farmer_id=farmer_id).all())
    return [{"id":g.id,"name":g.name,"target_amount":g.target_amount,"progress_amount":max(0,cash)} for g in db.query(FinancialGoal).filter_by(farmer_id=farmer_id).all()]

@app.post("/api/finance/goals", status_code=201)
def add_finance_goal(farmer_id: int, payload: FinancialGoalCreate, db: Session = Depends(get_db)):
    if not db.get(Farmer, farmer_id): raise HTTPException(404, "Farmer not found")
    goal=FinancialGoal(farmer_id=farmer_id, **payload.model_dump()); db.add(goal); db.commit(); db.refresh(goal)
    return {"id":goal.id,"name":goal.name,"target_amount":goal.target_amount}

@app.delete("/api/finance/goals/{goal_id}", status_code=204)
def delete_finance_goal(goal_id: int, farmer_id: int, db: Session = Depends(get_db)):
    goal=db.get(FinancialGoal,goal_id)
    if not goal: raise HTTPException(404,"Goal not found")
    if goal.farmer_id != farmer_id: raise HTTPException(403,"This goal belongs to another farmer")
    db.delete(goal);db.commit()

@app.get("/api/buyers")
def buyers(db:Session=Depends(get_db)): return [{"id":b.id,"name":b.name,"crop":b.crop,"min_quantity_kg":b.min_quantity_kg,"max_quantity_kg":b.max_quantity_kg,"price_per_kg":b.price_per_kg,"location":b.location,"distance_km":b.distance_km,"required_date":str(b.required_date),"quality_requirement":b.quality_requirement} for b in db.query(Buyer).all()]

@app.post("/api/buyers/match")
def buyer_match(payload:MatchRequest,db:Session=Depends(get_db)):
    results=[]
    for b in db.query(Buyer).filter(Buyer.crop.ilike(payload.crop)).all():
        quantity_ok=b.min_quantity_kg<=payload.quantity_kg<=b.max_quantity_kg
        score=(40 if quantity_ok else 12)+max(0,25-int(b.distance_km/4))+min(25,int(b.price_per_kg))
        reasons=[f"Crop matches {b.crop}", "Quantity is within buyer range" if quantity_ok else "Quantity is outside buyer range", f"{b.distance_km} km away", f"Demo offer ₹{b.price_per_kg}/kg"]
        results.append({"buyer":{"id":b.id,"name":b.name,"price_per_kg":b.price_per_kg,"location":b.location,"distance_km":b.distance_km,"quality_requirement":b.quality_requirement},"match_score":min(score,100),"why_matched":reasons})
    return sorted(results,key=lambda x:x["match_score"],reverse=True)

@app.post("/api/sell-vs-store")
def sell_store(p:SellStoreRequest):
    sell=p.quantity_kg*p.current_price_per_kg
    future=p.quantity_kg*p.future_price_per_kg
    storage=p.quantity_kg*p.storage_cost_per_kg_day*p.duration_days
    net=future-storage-p.transport_cost
    return {"sell_now_gross":round(sell,2),"store_scenario_gross":round(future,2),"storage_cost":round(storage,2),"transport_cost":p.transport_cost,"estimated_store_net":round(net,2),"difference":round(net-sell,2),"label":"Future price is a farmer-entered scenario/estimate, not a forecast or guarantee."}

@app.get("/api/storage")
def storage(db:Session=Depends(get_db)): return [{"id":s.id,"name":s.name,"capacity_kg":s.capacity_kg,"available_capacity_kg":s.available_capacity_kg,"cost_per_kg_day":s.cost_per_kg_day,"distance_km":s.distance_km,"storage_type":s.storage_type,"crops_supported":s.crops_supported} for s in db.query(StorageFacility).all()]

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSM_HEADERS = {"User-Agent": "RythuSodara/1.0 (farmer storage discovery)"}
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

WEATHER_CODES = {0:"Clear sky",1:"Mainly clear",2:"Partly cloudy",3:"Overcast",45:"Fog",48:"Rime fog",51:"Light drizzle",53:"Drizzle",55:"Heavy drizzle",61:"Light rain",63:"Rain",65:"Heavy rain",71:"Light snow",73:"Snow",75:"Heavy snow",80:"Rain showers",81:"Rain showers",82:"Heavy rain showers",95:"Thunderstorm",96:"Thunderstorm with hail",99:"Thunderstorm with hail"}
def weather_icon(code: int) -> str:
    if code in {61,63,65,80,81,82}: return "🌧️"
    if code in {95,96,99}: return "⛈️"
    if code in {1,2}: return "🌤️"
    if code == 0: return "☀️"
    return "☁️"

def create_alert(db: Session, farmer_id: int, alert_key: str, category: str, title: str, body: str):
    if not db.query(WeatherAlert).filter_by(alert_key=alert_key).first():
        db.add(WeatherAlert(farmer_id=farmer_id, alert_key=alert_key, category=category, title=title, body=body))

def weather_advisory(days: list[dict], crop: Crop | None) -> tuple[dict, list[dict]]:
    soon = next((day for day in days[:4] if day["rain_probability"] >= 60 or day["precipitation_mm"] >= 5), None)
    heavy = next((day for day in days[:4] if day["precipitation_mm"] >= 20), None)
    crop_name = crop.name if crop else "Your crop"
    if heavy:
        advisory = {"crop":crop_name,"level":"Caution","text":f"{crop_name}: heavier rain is currently forecast around {heavy['date']}. Check soil condition and drainage before the next irrigation."}
    elif soon:
        advisory = {"crop":crop_name,"level":"Watch","text":f"{crop_name}: rain is currently expected around {soon['date']}. Recheck soil moisture before the next irrigation."}
    else:
        advisory = {"crop":crop_name,"level":"Plan","text":f"{crop_name}: low rainfall is forecast soon. Check actual soil moisture before irrigation; forecasts are planning information."}
    alerts = []
    if soon: alerts.append({"category":"rain","title":f"Rain expected around {soon['date']}","body":f"{soon['rain_probability']}% chance, {soon['precipitation_mm']} mm forecast. Recheck irrigation before watering.","key":f"rain-{soon['date']}-{soon['rain_probability']}"})
    windy = next((day for day in days[:4] if day["wind_speed_kmh"] >= 35), None)
    if windy: alerts.append({"category":"wind","title":f"Strong wind expected {windy['date']}","body":f"Forecast wind: {windy['wind_speed_kmh']} km/h. Secure loose farm materials.","key":f"wind-{windy['date']}-{windy['wind_speed_kmh']}"})
    hot = next((day for day in days[:2] if day["max_temp_c"] >= 38), None)
    if hot: alerts.append({"category":"heat","title":f"High temperature expected {hot['date']}","body":f"Maximum temperature forecast: {hot['max_temp_c']}°C. Check crop and soil condition.","key":f"heat-{hot['date']}-{hot['max_temp_c']}"})
    return advisory, alerts

def haversine_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    earth_radius_km = 6371.0088
    phi_a, phi_b = math.radians(lat_a), math.radians(lat_b)
    delta_phi, delta_lambda = math.radians(lat_b - lat_a), math.radians(lon_b - lon_a)
    value = math.sin(delta_phi / 2) ** 2 + math.cos(phi_a) * math.cos(phi_b) * math.sin(delta_lambda / 2) ** 2
    return earth_radius_km * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))

def osm_address(tags: dict) -> str | None:
    pieces = [
        tags.get("addr:housenumber"), tags.get("addr:street"), tags.get("addr:suburb"),
        tags.get("addr:city") or tags.get("addr:village"), tags.get("addr:state"), tags.get("addr:postcode"),
    ]
    address = ", ".join(str(part) for part in pieces if part)
    return address or tags.get("addr:full") or None

def osm_storage_type(tags: dict) -> str:
    if tags.get("industrial") == "refrigerated_warehouse":
        return "Refrigerated warehouse"
    if tags.get("building:use") == "warehouse":
        return "Warehouse"
    if tags.get("industrial") == "warehouse" or tags.get("man_made") == "warehouse":
        return "Warehouse"
    return "Mapped warehouse"

@app.get("/api/storage/geocode")
def geocode_storage_search(query: str = Query(min_length=2, max_length=120)):
    """Convert a farmer-entered village or city into coordinates for nearby search."""
    try:
        response = requests.get(
            NOMINATIM_URL,
            params={"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "in"},
            headers=OSM_HEADERS,
            timeout=12,
        )
        response.raise_for_status()
        places = response.json()
    except requests.RequestException as error:
        raise HTTPException(502, "Could not search OpenStreetMap for that village or city.") from error
    if not places:
        raise HTTPException(404, "Place not found. Try a village, town, or city name with district.")
    place = places[0]
    return {"latitude": float(place["lat"]), "longitude": float(place["lon"]), "display_name": place["display_name"], "source": "OpenStreetMap"}

@app.get("/api/storage/nearby")
def nearby_storage(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    radius_km: int = Query(default=25, ge=1, le=50),
):
    """Find mapped warehouses around a farmer location using OpenStreetMap Overpass data."""
    radius_meters = radius_km * 1000
    query = f"""
    [out:json][timeout:20];
    (
      nwr(around:{radius_meters},{lat},{lon})["industrial"="refrigerated_warehouse"];
      nwr(around:{radius_meters},{lat},{lon})["building"="warehouse"];
      nwr(around:{radius_meters},{lat},{lon})["building:use"="warehouse"];
      nwr(around:{radius_meters},{lat},{lon})["industrial"="warehouse"];
      nwr(around:{radius_meters},{lat},{lon})["man_made"="warehouse"];
    );
    out center tags;
    """
    try:
        response = requests.post(OVERPASS_URL, data={"data": query}, headers=OSM_HEADERS, timeout=35)
        response.raise_for_status()
        elements = response.json().get("elements", [])
    except (requests.RequestException, ValueError) as error:
        raise HTTPException(502, "OpenStreetMap storage search is temporarily unavailable. Try again later.") from error
    facilities = []
    for element in elements:
        element_lat = element.get("lat") or element.get("center", {}).get("lat")
        element_lon = element.get("lon") or element.get("center", {}).get("lon")
        if element_lat is None or element_lon is None:
            continue
        tags = element.get("tags", {})
        facility_lat, facility_lon = float(element_lat), float(element_lon)
        distance = round(haversine_km(lat, lon, facility_lat, facility_lon), 2)
        name = tags.get("name") or tags.get("operator") or "Unnamed mapped warehouse"
        facilities.append({
            "name": name,
            "type": osm_storage_type(tags),
            "distance_km": distance,
            "latitude": facility_lat,
            "longitude": facility_lon,
            "address": osm_address(tags),
            "source": "OpenStreetMap",
            "maps_url": f"https://www.openstreetmap.org/?mlat={facility_lat}&mlon={facility_lon}#map=18/{facility_lat}/{facility_lon}",
        })
    # Elements may carry more than one selected tag. De-duplicate and retain nearest entries.
    unique = {(item["latitude"], item["longitude"], item["name"]): item for item in facilities}
    return sorted(unique.values(), key=lambda item: item["distance_km"])[:30]

@app.post("/api/storage/match")
def storage_match(p:MatchRequest,db:Session=Depends(get_db)):
    matches=[]
    for s in db.query(StorageFacility).all():
        crop_ok=p.crop.lower() in s.crops_supported.lower(); capacity_ok=s.available_capacity_kg>=p.quantity_kg
        if crop_ok and capacity_ok: matches.append({"facility":s.name,"available_capacity_kg":s.available_capacity_kg,"cost_per_kg_day":s.cost_per_kg_day,"distance_km":s.distance_km,"score":round(100-s.distance_km-s.cost_per_kg_day*20),"reason":f"Supports {p.crop}, has enough capacity, and is {s.distance_km} km away."})
    return sorted(matches,key=lambda x:x["score"],reverse=True)

@app.get("/api/logistics")
def logistics(db:Session=Depends(get_db)): return [{"id":t.id,"name":t.name,"vehicle_type":t.vehicle_type,"capacity_kg":t.capacity_kg,"cost":t.cost,"location":t.location,"available":t.available} for t in db.query(Transporter).all()]

@app.post("/api/logistics/match")
def logistics_match(p:MatchRequest,db:Session=Depends(get_db)):
    return [{"name":t.name,"vehicle_type":t.vehicle_type,"capacity_kg":t.capacity_kg,"cost":t.cost,"score":min(100,70+int((t.capacity_kg-p.quantity_kg)/100)),"reason":"Available and capacity meets requested quantity."} for t in db.query(Transporter).filter_by(available=True).all() if t.capacity_kg>=p.quantity_kg]

@app.post("/api/expert-review",status_code=201)
def expert_request(p:ExpertRequestCreate,db:Session=Depends(get_db)):
    if not db.get(Crop,p.crop_id): raise HTTPException(404,"Crop not found")
    r=ExpertRequest(**p.model_dump());db.add(r);db.commit();db.refresh(r);return {"id":r.id,"status":r.status,"message":"Expert review request created in demo mode."}

@app.get("/api/expert-review")
def expert_requests(db:Session=Depends(get_db)): return [{"id":r.id,"crop_id":r.crop_id,"diagnosis":r.diagnosis,"confidence":r.confidence,"notes":r.farmer_notes,"status":r.status,"created_at":str(r.created_at)} for r in db.query(ExpertRequest).order_by(ExpertRequest.created_at.desc()).all()]
