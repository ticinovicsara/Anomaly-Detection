import { lazy, Suspense } from "react";
import {
  Navigate,
  Route,
  Routes,
  useLocation,
  useOutlet,
} from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { FullPageSpinner } from "@/components/Spinner";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import AppShell from "@/layout/AppShell";
import { useAuth } from "@/hooks";
import LoginPage from "@/pages/LoginPage";
import RegisterPage from "@/pages/RegisterPage";
import AnomaliesPage from "@/pages/AnomaliesPage";
import SettingsPage from "@/pages/SettingsPage";

const DashboardPage = lazy(() => import("@/pages/DashboardPage"));
const ModelsPage = lazy(() => import("@/pages/ModelsPage"));
const SubjectsPage = lazy(() => import("@/pages/SubjectsPage"));
const SubjectDetailPage = lazy(() => import("@/pages/SubjectDetailPage"));
const ExperimentsPage = lazy(() => import("@/pages/ExperimentsPage"));
const ModelDiagnosticsPage = lazy(() => import("@/pages/ModelDiagnosticsPage"));
const UploadPage = lazy(() => import("@/pages/UploadPage"));

function ProtectedLayout() {
  const { isAuthed, loading } = useAuth();
  const location = useLocation();
  const outlet = useOutlet(); // captured so AnimatePresence can still render the outgoing page mid-exit
  const reduceMotion = useReducedMotion();
  if (loading) return <FullPageSpinner />;
  if (!isAuthed) return <Navigate to="/login" replace />;
  return (
    <AppShell>
      <ErrorBoundary resetKey={location.pathname}>
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={reduceMotion ? false : { opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduceMotion ? undefined : { opacity: 0, y: -6 }}
            transition={{
              duration: reduceMotion ? 0 : 0.22,
              ease: [0.23, 1, 0.32, 1],
            }}
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
        <Route
          path="/login"
          element={
            <ErrorBoundary>
              <LoginPage />
            </ErrorBoundary>
          }
        />
        <Route
          path="/register"
          element={
            <ErrorBoundary>
              <RegisterPage />
            </ErrorBoundary>
          }
        />
        <Route element={<ProtectedLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/subjects" element={<SubjectsPage />} />
          <Route path="/subjects/:id" element={<SubjectDetailPage />} />
          <Route path="/models" element={<ModelsPage />} />
          <Route
            path="/models/:id/diagnostics"
            element={<ModelDiagnosticsPage />}
          />
          <Route path="/anomalies" element={<AnomaliesPage />} />
          <Route path="/experiments" element={<ExperimentsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
