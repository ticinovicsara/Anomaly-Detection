import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation, useOutlet } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { FullPageSpinner } from "./components/Spinner";
import { ErrorBoundary } from "./components/ErrorBoundary";
import AppShell from "./layout/AppShell";
import { useAuth } from "./hooks/useAuth";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Upload from "./pages/Upload";
import Anomalies from "./pages/Anomalies";
import Settings from "./pages/Settings";

const Dashboard = lazy(() => import("./pages/Dashboard"));
const Models = lazy(() => import("./pages/Models"));

function ProtectedLayout() {
  const { isAuthed, loading } = useAuth();
  const location = useLocation();
  // Captured per-render so AnimatePresence can keep rendering the outgoing
  // page's actual content while it plays its exit animation -- <Outlet/>
  // itself always reflects the *new* route the instant it changes.
  const outlet = useOutlet();
  const reduceMotion = useReducedMotion();
  if (loading) return <FullPageSpinner />;
  if (!isAuthed) return <Navigate to="/login" replace />;
  return (
    <AppShell>
      {/* resetKey (not a React key) clears a caught error on navigation
          without unmounting the boundary -- a hard remount here would
          break AnimatePresence's ability to track exit animations below. */}
      <ErrorBoundary resetKey={location.pathname}>
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={reduceMotion ? false : { opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduceMotion ? undefined : { opacity: 0, y: -6 }}
            transition={{ duration: reduceMotion ? 0 : 0.22, ease: [0.23, 1, 0.32, 1] }}
          >
            {outlet}
          </motion.div>
        </AnimatePresence>
      </ErrorBoundary>
    </AppShell>
  );
}

export default function App() {
  return (
    <Suspense fallback={<FullPageSpinner />}>
      <Routes>
        <Route path="/login" element={<ErrorBoundary><Login /></ErrorBoundary>} />
        <Route path="/register" element={<ErrorBoundary><Register /></ErrorBoundary>} />
        <Route element={<ProtectedLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/models" element={<Models />} />
          <Route path="/anomalies" element={<Anomalies />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
