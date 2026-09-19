import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("AGRIBRIDGE_DATABASE_URL", "sqlite:///./agribridge.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def run_migrations():
    """Small additive SQLite migration for the MVP without removing existing data."""
    if not DATABASE_URL.startswith("sqlite"):
        return
    additions = {
        "farmers": ["pin_hash VARCHAR(255)"],
        "fields": ["ownership VARCHAR(12) DEFAULT 'Owned'", "notes TEXT DEFAULT ''"],
        "crops": [
            "actual_harvest_date DATE", "actual_yield_kg FLOAT",
            "storage_status VARCHAR(60) DEFAULT 'Not arranged'",
            "selling_status VARCHAR(60) DEFAULT 'Not listed'",
            "notes TEXT DEFAULT ''", "asking_price_per_kg FLOAT",
            "expected_selling_date DATE", "quality_grade VARCHAR(80)",
            "market_notes TEXT DEFAULT ''",
        ],
        "weather_alerts": [],
        "notification_preferences": [],
    }
    with engine.begin() as connection:
        for table, columns in additions.items():
            existing = {row[1] for row in connection.execute(text(f"PRAGMA table_info({table})"))}
            for definition in columns:
                column = definition.split()[0]
                if column not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {definition}"))
