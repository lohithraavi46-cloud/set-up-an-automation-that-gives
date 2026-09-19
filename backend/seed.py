from datetime import date, timedelta
from sqlalchemy.orm import Session
from .models import Buyer, Crop, CropHealthHistory, Diagnosis, Farmer, Field, MarketPrice, StorageFacility, Transporter, Treatment

def seed(db: Session):
    if db.query(Farmer).first():
        return
    farmer = Farmer(name="Ravi Kumar", phone="9000000000", village="Kothapally", language="English")
    db.add(farmer); db.flush()
    field = Field(farmer_id=farmer.id, name="North field", area_acres=2.5, location="Kothapally")
    db.add(field); db.flush()
    crop = Crop(farmer_id=farmer.id, field_id=field.id, name="Tomato", variety="Arka Rakshak", area_acres=2.5, planting_date=date.today()-timedelta(days=64), expected_harvest_date=date.today()+timedelta(days=21), harvest_quantity_kg=1600, market_status="Preparing to sell", health_status="Attention")
    db.add(crop); db.flush()
    db.add_all([
        CropHealthHistory(crop_id=crop.id,status="Healthy",note="Seedlings established well."),
        CropHealthHistory(crop_id=crop.id,status="Attention",note="Leaf curl symptoms noted in a small patch."),
        Diagnosis(crop_id=crop.id,result="Possible leaf curl stress (demo assessment)",confidence=.62,recommendation="Inspect affected plants and consult an agriculture expert before any treatment.",image_reference="demo-leaf-photo.jpg"),
        Treatment(crop_id=crop.id,treatment="Inspect affected patch and record spread.",scheduled_date=date.today()+timedelta(days=1)),
        Buyer(name="Sri Lakshmi Fresh",crop="Tomato",min_quantity_kg=800,max_quantity_kg=3000,price_per_kg=24.5,location="Guntur Mandi",distance_km=18,required_date=date.today()+timedelta(days=4),quality_requirement="Sorted, mature red fruit"),
        Buyer(name="GreenBasket Retail",crop="Tomato",min_quantity_kg=500,max_quantity_kg=1500,price_per_kg=25.2,location="Vijayawada",distance_km=42,required_date=date.today()+timedelta(days=7),quality_requirement="Grade A, crate packed"),
        Buyer(name="Nellore Foods",crop="Tomato",min_quantity_kg=2000,max_quantity_kg=6000,price_per_kg=23.8,location="Nellore",distance_km=93,required_date=date.today()+timedelta(days=3),quality_requirement="Processing grade accepted"),
        MarketPrice(crop="Tomato",market="Guntur Mandi",price_per_kg=24.0,recorded_date=date.today(),source_label="Demo scenario — not live market data"),
        MarketPrice(crop="Tomato",market="Vijayawada Market",price_per_kg=25.0,recorded_date=date.today(),source_label="Demo scenario — not live market data"),
        MarketPrice(crop="Chilli",market="Guntur Mandi",price_per_kg=110.0,recorded_date=date.today(),source_label="Demo scenario — not live market data"),
        StorageFacility(name="Kothapally Pack & Cool",capacity_kg=15000,available_capacity_kg=4200,cost_per_kg_day=.18,distance_km=5.5,storage_type="Pre-cooling",crops_supported="Tomato, Chilli, Mango"),
        StorageFacility(name="Guntur Fresh Hub",capacity_kg=50000,available_capacity_kg=18000,cost_per_kg_day=.25,distance_km=19,crops_supported="Tomato, Chilli, Onion",storage_type="Cold storage"),
        StorageFacility(name="Village Dry Store",capacity_kg=8000,available_capacity_kg=900,cost_per_kg_day=.08,distance_km=2,crops_supported="Onion, Grain",storage_type="Dry storage"),
        Transporter(name="Sai Farm Transport",vehicle_type="Mini truck",capacity_kg=2000,cost=1700,location="Kothapally",available=True),
        Transporter(name="Mandi Connect",vehicle_type="Pickup",capacity_kg=1000,cost=1050,location="Guntur",available=True),
        Transporter(name="Green Haulage",vehicle_type="Medium truck",capacity_kg=5000,cost=3400,location="Vijayawada",available=False)
    ])
    db.commit()
