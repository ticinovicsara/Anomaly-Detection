# Anomaly Detection System

A web application for **personalized anomaly detection in sequential data** — built as part of the thesis _"Development of a Modular System for Personalized Anomaly Detection in Sequential Data."_

Most anomaly detectors apply one global threshold to every entity they monitor, implicitly assuming "normal" means the same thing for everyone. It usually doesn't: a heart rate range that's unremarkable for one patient can be a warning sign for another. This system calibrates a **personalized threshold** (`ε = μ + 3σ`) per **Subject** — the entity being monitored (a patient, a card, a server) — from that Subject's own data, and automatically picks between Isolation Forest and an LSTM Autoencoder based on the statistical shape of whatever CSV is uploaded, without any domain-specific code.

## Core ideas

- **`User` vs `Subject`.** A `User` is just a login. A `Subject` is what personalization is calibrated for. One `User` can own many Subjects (e.g. a doctor tracking 30 patients) — each gets its own model and its own threshold, never blended together.
- **Automatic model selection.** A data profiler extracts autocorrelation, dominant frequency (FFT), and stationarity (ADF) from an upload; a transparent rule-based router picks Isolation Forest or an LSTM Autoencoder and records _why_. The user never chooses an algorithm (an "Advanced mode" escape hatch exists for manual override/comparison).
- **Dataset-agnostic by design.** The ML core (`backend/app/ml_core/`) never knows what dataset it's looking at — MIT-BIH ECG records, Credit Card Fraud, Yahoo S5, or an arbitrary CSV all go through the same profiler → router → train → calibrate pipeline.
- **Optional supervised evaluation.** If a CSV has a binary ground-truth anomaly column, marking it at upload time yields real precision/recall/F1/AU-ROC on a held-out test split, evaluated at the model's actual production threshold — otherwise the system stays fully unsupervised, as before.

## Architecture

```mermaid
flowchart TB
    subgraph presentation["Presentation — React 18 + TypeScript + Vite"]
        UI["Subjects · Upload · Models · Anomalies\nExperiments · Model Diagnostics · Settings"]
    end

    subgraph application["Application — FastAPI"]
        API["Routers: auth · upload · train · predict\nanomalies · subjects · experiments · settings"]
        SVC["Services: training · dataset_splitter\nexperiments · subjects · prediction"]
    end

    subgraph ml["ML core — no FastAPI/DB dependency"]
        PROF["Data profiler\n(autocorr, FFT, ADF)"]
        ROUTER["Model router\n(rule-based)"]
        MODELS["Isolation Forest\nLSTM Autoencoder"]
        THR["Threshold calibration\nε = μ + zσ"]
        EVAL["Evaluation\n(precision/recall/F1/AUC)"]
    end

    subgraph infra["Infrastructure"]
        PG[("PostgreSQL 16")]
        FS[("File storage\nmodels/scalers/CSVs")]
    end

    UI -- "HTTPS / REST" --> API
    API --> SVC
    SVC --> PROF --> ROUTER --> MODELS --> THR --> EVAL
    SVC --> PG
    SVC --> FS
```

**Why this split:** `ml_core/` has no dependency on FastAPI or SQLAlchemy, so it's trivially unit-testable and swappable. Background training runs as a `BackgroundTasks` job under a single-slot lock — no Redis/Celery broker needed at this scale.

## Tech stack

| Layer    | Technology                                                                                                     |
| -------- | -------------------------------------------------------------------------------------------------------------- |
| Backend  | FastAPI, SQLAlchemy, Alembic, Pydantic, JWT auth (`python-jose` + `passlib`/`bcrypt`), `slowapi` rate limiting |
| ML core  | scikit-learn (Isolation Forest), TensorFlow/Keras (LSTM Autoencoder), pandas, NumPy, SciPy, statsmodels        |
| Database | PostgreSQL 16                                                                                                  |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Recharts, `motion` (animation), Axios                                |
| Testing  | pytest (backend, 90+ tests), `tsc --noEmit` (frontend type-checking)                                           |
| Infra    | Docker, Docker Compose                                                                                         |

## Quick start

### Option A — Docker Compose (fastest)

```bash
git clone <this-repo-url>
cd Anomaly-Detection
docker compose up --build
```

That builds and starts PostgreSQL, the backend (migrations run automatically on container start), and the frontend behind nginx.

- Frontend: **http://localhost:8080**
- Backend API / Swagger docs: **http://localhost:8000/docs**

Set a real `JWT_SECRET` before running this anywhere beyond a local demo — the backend logs a startup warning if it's left at the default:

```bash
echo "JWT_SECRET=$(openssl rand -hex 32)" > .env
docker compose up --build
```

### Option B — Local dev (hot reload)

```bash
# 1. Database only
docker compose up -d db

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # edit DATABASE_URL/JWT_SECRET if needed
alembic upgrade head
uvicorn app.main:app --reload                         # http://localhost:8000

# 3. Frontend (separate terminal)
cd frontend
npm install
npm run dev                                            # http://localhost:5173
```

The frontend dev server proxies `/api/*` to the backend (see `frontend/vite.config.ts`). If port 8000 is unusable on your machine (Windows sometimes reserves it), set `VITE_BACKEND_PORT=<port>` in `frontend/.env.local` and start the backend on that port instead.

## Environment variables

Backend (`backend/.env`, see `backend/.env.example`):

| Variable             | Default                                                      | Notes                                                                                          |
| -------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| `DATABASE_URL`       | `postgresql://anomaly:anomaly_dev@localhost:5432/anomaly_db` | Use `db:5432` (not the host-mapped `5433`) when running via Docker Compose                     |
| `JWT_SECRET`         | `dev_secret_change_me`                                       | **Must** be overridden outside local dev — logged as a startup warning otherwise               |
| `JWT_ALGORITHM`      | `HS256`                                                      |                                                                                                |
| `JWT_EXPIRE_MINUTES` | `1440`                                                       |                                                                                                |
| `STORAGE_PATH`       | `./models_storage`                                           | Where trained models/scalers/uploaded CSVs are persisted                                       |
| `FRONTEND_ORIGIN`    | `http://localhost:5173`                                      | CORS allow-origin                                                                              |
| `SMTP_*`             | —                                                            | Reserved for a planned notifications feature (see Status below) — not yet consumed by any code |

Frontend (`frontend/.env` / `.env.local`):

| Variable            | Default | Notes                                                                                                                |
| ------------------- | ------- | -------------------------------------------------------------------------------------------------------------------- |
| `VITE_BACKEND_PORT` | `8000`  | Dev-proxy target port only; irrelevant in the Docker Compose build (nginx proxies to the `backend` service directly) |

## Project structure

```
Anomaly-Detection/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers (auth, upload, train, predict, anomalies, subjects, experiments, settings)
│   │   ├── core/         # config, security, rate limiter
│   │   ├── db/           # SQLAlchemy models, session, Alembic migrations
│   │   ├── services/     # training, dataset_splitter, experiments, subjects, prediction
│   │   ├── ml_core/      # pure ML module -- profiler, router, models, threshold, preprocessing
│   │   └── main.py
│   ├── alembic/versions/
│   ├── scripts/          # standalone research scripts (e.g. MIT-BIH ch. 7.4 evaluation), not part of the app
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/        # Dashboard, Upload, Subjects, SubjectDetail, Models, ModelDiagnostics, Anomalies, Experiments, Settings
│   │   ├── components/, hooks/, api/, layout/, theme/
│   ├── Dockerfile
│   └── nginx.conf
└── docker-compose.yml
```

## API reference

- Interactive Swagger UI: `http://localhost:8000/docs` (or ReDoc at `/redoc`) once the backend is running
- `backend/postman_collection.json` — importable collection covering the full register → upload → train → predict → anomalies flow
- Frontend TypeScript types are generated from the backend's OpenAPI schema, not hand-maintained — see `frontend/README.md` for the regeneration workflow whenever a backend schema changes

## Running tests

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/ -q
```

```bash
cd frontend
npm install
npx tsc --noEmit   # type-check
npm run build      # production build
```

## Status

**Implemented:** auth, Subject-based data model, upload with optional dataset splitting (by ID column or time period), automatic model selection, IF + LSTM training and prediction, personalized threshold calibration with a manual z-multiplier override, the Personalization Experiment (ch. 7.4 empirical proof, plus a synthetic preset demo), Advanced mode (manual algorithm selection / comparison), optional supervised evaluation (precision/recall/F1/AU-ROC, confusion matrix, per-model diagnostics page) with cross-Subject aggregation, rate limiting and upload validation hardening.

**Deliberately out of scope for this thesis, documented as future work:** concept drift monitoring (`Model.drift_status` exists in the schema but nothing computes it yet — see ch. 7.5), email/push notifications, scheduled PDF reports, a hybrid curated/Kaggle data-source picker, and CI/CD. None of these affect the personalization/modularity claims the system exists to demonstrate.
