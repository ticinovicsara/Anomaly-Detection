# Anomaly Detection Frontend

Vite + React + TypeScript + Tailwind CSS. Uiverse-inspired aesthetic: clean cards, subtle borders, soft hover motion, blue accent, dark + light themes.

## Setup

```bash
cd frontend
npm install
npm run dev
```

Runs at http://localhost:5173. It proxies `/api/*` to `http://localhost:3000` (see `vite.config.ts`), so the backend must be running. If port 3000 isn't usable on your machine (Windows sometimes reserves ports in its excluded range), set `VITE_BACKEND_PORT=<port>` in `frontend/.env.local` and start the backend on that port instead.

## Build

```bash
npm run build
npm run preview
```

```bash
npx tsc --noEmit   # type-check only, no build output
```

## Structure

`@/*` is aliased to `src/*` (see `vite.config.ts` + `tsconfig.app.json`) - imports use `@/components/Button`, not relative `../../` paths. Folders with more than a couple of exportable modules have an `index.ts` barrel (`components/`, `hooks/`, and each foldered page).

```
src/
├── main.tsx, App.tsx        # entry + routes
├── theme/                   # ThemeProvider (dark/light via data-theme + CSS vars)
├── api/
│   ├── client.ts            # axios instance + typed API calls
│   └── types.ts             # request/response types (re-exported from client.ts)
├── types/api.generated.ts   # generated from the backend's OpenAPI schema -- see below
├── hooks/                   # useAuth, useAdvancedMode, useCountUp (+ index.ts barrel)
├── layout/AppShell.tsx      # sidebar, topbar, responsive drawer
├── components/              # Button, Card, Input, Badge, Slider, Toast, Modal, Spinner, EvaluationStats, PageHeader (+ index.ts barrel)
└── pages/
    ├── LoginPage.tsx, RegisterPage.tsx
    ├── DashboardPage.tsx        # stats, recent anomalies, chart, models table
    ├── UploadPage/              # drag-and-drop + profiler results + auto model selection
    ├── SubjectsPage.tsx, SubjectDetailPage/  # per-Subject view, retrain, pre-retrain data review
    ├── ModelsPage.tsx           # list of trained models, run prediction
    ├── ModelDiagnosticsPage/    # internal QA view (Advanced mode) -- confusion matrix, predicted-vs-actual
    ├── ExperimentsPage/         # personalization experiment (ch. 7.4) + preset demo
    ├── AnomaliesPage.tsx        # review + label (confirmed / false positive / resolved)
    └── SettingsPage.tsx         # theme toggle + z-multiplier slider per model
```

Pages with genuine internal complexity (extracted sub-components, local helpers) get their own folder + `index.ts` re-export; single-screen pages stay as one flat `XxxPage.tsx` file. Several pages are route-level `lazy()`-loaded in `App.tsx` for code splitting, so nothing re-exports all of `pages/` from one barrel - that would collapse them back into a single chunk.

## Design tokens

Colors are CSS variables (`--bg`, `--surface`, `--accent`, ...) defined in `src/index.css` under `[data-theme="dark"]` and `[data-theme="light"]`. Change them in one place, both themes update. Tailwind classes use them via `bg-surface`, `text-text`, `border-border`, `text-accent`, etc.

Accent color is blue (`#3B82F6` in dark, `#2563EB` in light). Swap `--accent` and `--accent-hover` in `index.css` to re-theme the whole app.

## Keeping API types in sync with the backend

`src/types/api.generated.ts` is generated from the backend's actual OpenAPI schema (`openapi-typescript`), not hand-maintained - most types in `src/api/client.ts` are aliased from it (`components["schemas"]["SubjectOut"]`, etc.) so they can't silently drift from what the backend actually returns.

**Whenever a backend Pydantic schema changes** (a field added/removed/retyped on any `response_model` in `backend/app/api/*.py`):

```bash
# 1. From backend/, export the current OpenAPI schema (no server or DB needed)
cd ../backend
python scripts/export_openapi.py          # writes ../frontend/openapi.json

# 2. From frontend/, regenerate the TypeScript types
cd ../frontend
npm run generate:types                     # writes src/types/api.generated.ts

# 3. Typecheck, then commit the regenerated file
npx tsc --noEmit
git add src/types/api.generated.ts
```

This is a manual step, not a CI gate - there's no pre-commit hook enforcing it at this project's scale. If a type error shows up after step 3, it means frontend code was relying on a backend field/shape that just changed; fix the frontend usage, don't just silence the error.

**Not everything is generated.** A handful of endpoints have no `response_model` declared on the backend (`/upload`, `/upload/analyze`, `/upload/commit`, `/predict/{id}`, `/train/{id}`, `/train/models`) - their response shapes are invisible to OpenAPI, so the corresponding frontend types (`Profile`, `AnalyzeResult`, `CommitResult`, `PredictResult`, `ModelInfo`, `ModelMetrics`) stay hand-written in `client.ts`, each with a comment noting why. Adding `response_model` to those routes would make FastAPI validate/serialize real responses against a new schema - a behavior change, not something to do as part of a types refresh.

## Notes

- Token is stored in `localStorage` under `token`. Axios injects it into every request.
- On any 401 response the client clears the token and redirects to `/login`.
- All list pages auto-refresh (Models polls every 3s while training is in progress).
