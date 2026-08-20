# Anomaly Detection Backend

FastAPI backend for personalized anomaly detection in sequential data.

## Setup (first time)

```bash
# 1. Start PostgreSQL (from project root, one level up)
cd ..
docker-compose up -d
cd backend

# 2. Create Python virtual env
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# 3. Install dependencies (TensorFlow is heavy — grab a coffee)
pip install --upgrade pip
pip install -r requirements.txt

# 4. Copy env template and edit
copy .env.example .env      # Windows
# or: cp .env.example .env  # Mac/Linux
# then open .env and fill in JWT_SECRET and SMTP_* if you want emails

# 5. Run DB migrations
alembic upgrade head

# 6. Start the server
uvicorn app.main:app --reload --port 3000
```

Server runs at http://localhost:3000
Swagger docs at http://localhost:3000/docs
Postman collection: `postman_collection.json` in this folder.

## Endpoints (verify order in Postman)

1. `POST /auth/register` — create a user
2. `POST /auth/login` — get JWT token (save to `{{token}}` variable in Postman)
3. `POST /upload` (multipart, file field) — upload CSV, returns dataset_id + profile
4. `POST /train/{dataset_id}` — starts training (async, returns immediately)
5. `GET /models` — list your trained models with status
6. `POST /predict/{model_id}` (multipart, file field) — predict on new CSV
7. `GET /anomalies?model_id=...` — list detected anomalies
8. `PATCH /anomalies/{event_id}` — label as confirmed / false_positive / resolved
9. `GET /settings/threshold/{model_id}` — read current threshold
10. `PATCH /settings/threshold/{model_id}` — recalibrate with new z-multiplier

Every endpoint except `/auth/*` and `/health` requires `Authorization: Bearer <token>`.

## Run tests

```bash
pytest tests/ -v
```
