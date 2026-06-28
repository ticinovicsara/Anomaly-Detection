# Changelog

## [Unreleased] — 2026-06-28

### Added

- `window_labels()` in preprocessing — max-pooling point-level labels to window-level for LSTM evaluation alignment (Schmidl et al. 2022)
- `load_yahoo()` in preprocessing — Yahoo S5 Webscope loader: drops timestamps and changepoint columns, warns on missing label column
- `backend/conftest.py` — sys.path setup so pytest resolves the app module from any working directory
- `backend/.env.example` — DATABASE_URL reference for local development
- `backend/tests/test_integration.py` — 4 end-to-end pipeline tests (Isolation Forest + LSTM) without PostgreSQL
- `TestWindowLabels` expanded to 5 tests; `TestLoadCreditcardAmountScaler` (3 tests); `TestLoadYahoo` (5 tests)

### Fixed

- `load_creditcard()` Amount `StandardScaler` not persisted: prediction previously fit a fresh scaler on prediction data, making anomaly scores incomparable to the training threshold; fixed with `amount_scaler_path` parameter (save on train, load on predict)
- Yahoo dataset type falling through to `load_ecg()` in upload, train, and predict routers — column schema mismatch would raise `KeyError` at runtime
- `_label_column()` in train.py: yahoo now correctly returns `"is_anomaly"` instead of `"label"`
- `.gitignore`: `.env.*` pattern blocked `.env.example`; `!.env.example` exception added

---

## [Unreleased] — 2026-06-23

### Added

**ML Pipeline**
- `backend/app/ml/preprocessing.py` — data loading, normalization (MinMaxScaler), sliding window creation (window=50, stride=10), time-ordered 70/15/15 split, Credit Card and ECG dataset loaders
- `backend/app/ml/isolation_forest.py` — baseline model: train, predict (binary), evaluate (precision/recall/F1/ROC-AUC), calibrate_threshold (mean+3σ)
- `backend/app/ml/lstm_autoencoder.py` — main model: build_model (64→32 encoder, 32→64 decoder), train (EarlyStopping patience=5), get_reconstruction_error, calibrate_threshold, predict, evaluate

**Tests**
- `backend/tests/test_preprocessing.py` — 25 tests across 5 classes
- `backend/tests/test_isolation_forest.py` — 16 tests across 4 classes
- `backend/tests/test_lstm_autoencoder.py` — 28 tests across 6 classes

**Database Layer**
- `backend/app/database.py` — SQLAlchemy engine, SessionLocal, Base, get_db dependency
- `backend/app/models.py` — User, UploadLog, ModelMeta ORM models (SQLAlchemy 2.0 mapped_column style)
- `backend/alembic/` — full Alembic setup: env.py, script.py.mako, initial migration (0001_initial_schema.py)

**FastAPI Backend**
- `backend/app/routers/upload.py` — POST /api/v1/upload: file upload, schema validation, user creation, upload logging
- `backend/app/routers/train.py` — POST /api/v1/train: full ML pipeline (load → split → normalize → train → calibrate), model meta upsert
- `backend/app/routers/predict.py` — POST /api/v1/predict: anomaly detection on new CSV, returns scores + anomaly indices
- `backend/app/main.py` — FastAPI app, CORS middleware, router mounting, /health endpoint

**Frontend**
- `frontend/src/components/UploadForm.jsx` — file upload + model training form with two-step flow
- `frontend/src/components/AnomalyChart.jsx` — Recharts ComposedChart: score line + anomaly scatter + threshold reference line
- `frontend/src/components/ResultsTable.jsx` — summary stats + scrollable per-window score table
- `frontend/src/App.jsx` — two-column layout, state orchestration, predict step
- `frontend/vite.config.js`, `tailwind.config.js`, `postcss.config.js`, `package.json`

**Deploy & CI**
- `.github/workflows/backend-ci.yml` — pytest + PostgreSQL service on GitHub Actions
- `.github/workflows/frontend-ci.yml` — npm build on GitHub Actions
- `render.yaml` — Render.com backend deploy config
- `frontend/vercel.json` — Vercel frontend deploy config with API proxy rewrites

**Documentation**
- `docs/wiki/` — 9 research paper summaries ingested into project wiki
- `C:/Users/ticin/Radna površina/Zavrsni/code_explanations.md` — full plain-language explanation of every file

### Fixed

- Path traversal vulnerability in upload.py (`file.filename` → `Path(file.filename).name`)
- Shared temp file race condition in predict.py (unique UUID-based temp path)
- CORS wildcard+credentials crash in main.py
- Missing input validation for `dataset_type`/`model_type` in train.py and predict.py before path construction
- TOCTOU race in `_get_or_create_user` (IntegrityError catch + rollback)
- Isolation Forest model double-loaded in predict.py
- LSTM `elapsed = 0.0` — now measured with `time.time()`
- `roc_auc_score` crash on single-class input — guarded with `len(np.unique(y_true)) > 1` in both evaluate functions
- Silent ECG label fabrication in `load_ecg` — now emits `warnings.warn`
