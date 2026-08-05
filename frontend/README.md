# Anomaly Detection Frontend

Vite + React + TypeScript + Tailwind CSS. Uiverse-inspired aesthetic: clean cards, subtle borders, soft hover motion, blue accent, dark + light themes.

## Setup

```bash
cd frontend
npm install
npm run dev
```

Runs at http://localhost:5173. It proxies `/api/*` to `http://localhost:8000` (see `vite.config.ts`), so the backend must be running.

## Build

```bash
npm run build
npm run preview
```

## Structure

```
src/
├── main.tsx, App.tsx        # entry + routes
├── theme/                   # ThemeProvider (dark/light via data-theme + CSS vars)
├── api/client.ts            # axios instance + typed API calls
├── hooks/useAuth.ts         # auth state + logout
├── layout/AppShell.tsx      # sidebar, topbar, responsive drawer
├── components/              # Button, Card, Input, Badge, Slider, Toast, Modal, Spinner
└── pages/
    ├── Login.tsx, Register.tsx
    ├── Dashboard.tsx        # stats, recent anomalies, chart, models table
    ├── Upload.tsx           # drag-and-drop + profiler results + auto model selection
    ├── Models.tsx           # list of trained models, run prediction
    ├── Anomalies.tsx        # review + label (confirmed / false positive / resolved)
    └── Settings.tsx         # theme toggle + z-multiplier slider per model
```

## Design tokens

Colors are CSS variables (`--bg`, `--surface`, `--accent`, ...) defined in `src/index.css` under `[data-theme="dark"]` and `[data-theme="light"]`. Change them in one place, both themes update. Tailwind classes use them via `bg-surface`, `text-text`, `border-border`, `text-accent`, etc.

Accent color is blue (`#3B82F6` in dark, `#2563EB` in light). Swap `--accent` and `--accent-hover` in `index.css` to re-theme the whole app.

## Notes

- Token is stored in `localStorage` under `token`. Axios injects it into every request.
- On any 401 response the client clears the token and redirects to `/login`.
- All list pages auto-refresh (Models polls every 3s while training is in progress).
