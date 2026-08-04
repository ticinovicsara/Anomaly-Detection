import { lazy, Suspense } from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
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
  if (loading) return <FullPageSpinner />;
  if (!isAuthed) return <Navigate to="/login" replace />;
  return (
    <AppShell>
      {/* Keyed on pathname so only the page content remounts (and fades in /
          resets its error boundary) on navigation -- the sidebar and header
          stay mounted instead of flickering on every click. */}
      <ErrorBoundary key={location.pathname}>
        <div className="animate-fade-in">
          <Outlet />
        </div>
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
