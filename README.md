# Rythu Sodara

Rythu Sodara is a mobile-first, full-stack MVP helping small farmers move from crop care to sale: **Crop → Diagnose → Guidance → Harvest → Market → Buyer → Storage/Logistics → Sale**.

All crop-health results, prices, buyers, weather placeholders, and recommendations are clearly labelled **demo scenarios**. They are not live market data, guaranteed predictions, or professional agronomy advice.

Crop-image screening is different: it is wired to the public ONNX model from BiernyVR/crop-disease-classifier. The model downloads from Hugging Face on the first submitted image and runs locally with ONNX Runtime. It remains a screening aid, not a treatment prescription or a guaranteed diagnosis.

## Architecture

- backend/ — FastAPI REST service, SQLAlchemy models, Pydantic validation and demo seeding.
- agribridge.db — SQLite database created automatically at startup.
- index.html, styles.css, app.js — framework-free responsive dashboard. The frontend uses fetch() to call the API and localStorage for offline pending actions.

## Setup (Windows PowerShell)

Use two terminals in this folder.

**Terminal 1 — backend**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```

If PowerShell blocks activation, run the command without activating:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 — frontend**

```powershell
npm.cmd start
```

Open http://localhost:3000. API documentation is available at http://localhost:8000/docs.

No login is required in demo mode. Seeded farmer: **Ravi Kumar**, crop: **Tomato / Arka Rakshak**.

## REST API

- GET /api/health
- GET /api/weather?lat=...&lon=...&farmer_id=...
- GET /api/notifications?farmer_id=...
- POST /api/notifications/read
- POST /api/notifications/subscribe
- POST /api/auth/register, POST /api/auth/login
- POST /api/farmers, GET /api/farmers/{id}
- PUT /api/farmers/{id}/preferences
- POST /api/crops, GET /api/crops, GET /api/crops/{id}, PUT /api/crops/{id}
- POST /api/diagnose, GET /api/diagnosis/{crop_id}
- GET /api/decisions/{crop_id}
- GET /api/market/prices
- GET /api/buyers, POST /api/buyers/match
- POST /api/sell-vs-store
- GET /api/storage, POST /api/storage/match
- GET /api/storage/nearby?lat=...&lon=...&radius_km=25
- GET /api/storage/geocode?query=Village%20or%20City
- GET /api/logistics, POST /api/logistics/match
- POST /api/expert-review, GET /api/expert-review

## Nine innovations included

1. **Crop passport:** linked farmer, field, crop, health, diagnosis and treatment history timeline.
2. **Decision engine:** transparent action, reason, urgency, confidence and listed input assumptions.
3. **Sell vs store:** computes gross values, costs, estimated net result and difference.
4. **Buyer matching:** scores crop, quantity, distance and offer compatibility with reasons.
5. **Storage matching:** considers crop support, capacity, cost and distance.
6. **Logistics matching:** filters available vehicles by carrying capacity.
7. **Today’s action dashboard:** farmer-friendly action cards, health, harvest, market and sale alerts.
8. **Offline first:** failed diagnosis/expert actions are saved to localStorage and automatically retried online.
9. **AI to human expert:** lower-confidence local model assessments explain uncertainty and create an expert-review request.

## Future integration

Use environment variable AGRIBRIDGE_DATABASE_URL to replace SQLite with a production database. External weather, market, diagnosis, maps and communication providers can be implemented behind the existing FastAPI endpoints. Do not add provider keys to source files.

Useful future integrations, intentionally not included yet: SMS/WhatsApp OTP verification for login, live weather forecasts and alerts, official mandi price feeds, verified buyer directories, real-time cold-storage capacity/booking feeds, and transporter availability/payment systems.

## Real Weather + Notifications

The Weather page requests location only after the farmer selects **Use my farm location**. It calls the free Open-Meteo forecast API through FastAPI and shows current conditions, a 10-day rain outlook, a cautious Rain Window summary, and an irrigation planning advisory tied to the selected crop.

Weather results are cached locally after a successful refresh. If connectivity drops, the app displays the last saved result with an explicit warning that it may be outdated. The app refreshes weather when connectivity returns and every 30 minutes while the Weather view is in use.

Weather alerts are deduplicated by forecast event and stored in SQLite. Browser notification permission is requested only from the **Enable weather notifications** button. A service worker is included for persistent mobile-compatible notification display and click-to-open Weather behavior.

Browser notifications and service workers require localhost during development or HTTPS after deployment. The app records browser permission and is structured for Push API subscriptions, but true background push while the app is closed requires a VAPID key and a server-side push delivery service; that is intentionally not configured.

## Nearby storage discovery

The Storage page has two distinct sections:

- **Nearby real storage:** Uses browser location (or village/city search) and OpenStreetMap Overpass data to find mapped warehouses within 5, 10, 25, or 50 km. Returned information is limited to what OpenStreetMap provides: name, warehouse type, distance, mapped address, coordinates, and an OpenStreetMap link.
- **Rythu Sodara matched storage:** Uses the existing database records to show capacity, cost, distance, and crop/quantity match reasons.

OpenStreetMap is community-maintained. A facility may be unnamed, missing, incorrectly tagged, or not operational. The app intentionally does **not** infer capacity, prices, availability, cold-chain capability, or booking status for real-world OpenStreetMap entries.

## Storage testing

With the backend running:

```powershell
curl.exe http://localhost:8000/api/storage
curl.exe -X POST http://localhost:8000/api/storage/match -H "Content-Type: application/json" --data-raw '{"crop":"Tomato","quantity_kg":1600}'
curl.exe "http://localhost:8000/api/storage/nearby?lat=16.2915&lon=80.4541&radius_km=25"
```

In the browser, open **Storage**, select **Use my location**, grant the browser permission, select a radius, and select **Search nearby storage**. If permission is declined, enter a village or city and select **Search nearby storage** instead.
