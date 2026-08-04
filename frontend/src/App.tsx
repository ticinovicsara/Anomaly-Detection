import { Navigate, Route, Routes } from "react-router-dom";
import { FullPageSpinner } from "./components/Spinner";
import AppShell from "./layout/AppShell";
import { useAuth } from "./hooks/useAuth";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Upload from "./pages/Upload";
import Models from "./pages/Models";
import Anomalies from "./pages/Anomalies";
import Settings from "./pages/Settings";

function Protected({ children }: { children: JSX.Element }) {
  const { isAuthed, loading } = useAuth();
  if (loading) return <FullPageSpinner />;
  if (!isAuthed) return <Navigate to="/login" replace />;
  return <AppShell>{children}</AppShell>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/" element={<Protected><Dashboard /></Protected>} />
      <Route path="/upload" element={<Protected><Upload /></Protected>} />
      <Route path="/models" element={<Protected><Models /></Protected>} />
      <Route path="/anomalies" element={<Protected><Anomalies /></Protected>} />
      <Route path="/settings" element={<Protected><Settings /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
