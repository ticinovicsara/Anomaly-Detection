import { ReactNode, useState } from "react";
import { NavLink, Link } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import {
  Activity,
  LayoutDashboard,
  Upload as UploadIcon,
  Users,
  Brain,
  AlertTriangle,
  FlaskConical,
  Settings as SettingsIcon,
  Menu,
  X,
  Sun,
  Moon,
  LogOut,
} from "lucide-react";
import { cn } from "../lib/cn";
import { useTheme } from "../theme/ThemeProvider";
import { logout, useAuth } from "../hooks/useAuth";

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/upload", label: "Upload", icon: UploadIcon },
  { to: "/subjects", label: "Subjects", icon: Users },
  { to: "/models", label: "Models", icon: Brain },
  { to: "/anomalies", label: "Anomalies", icon: AlertTriangle },
  { to: "/experiments", label: "Experiments", icon: FlaskConical },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

export default function AppShell({ children }: { children: ReactNode }) {
  const { theme, toggle } = useTheme();
  const { user } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 w-64 border-r border-border bg-surface transition-transform lg:translate-x-0 lg:static lg:z-auto",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-16 items-center justify-between border-b border-border px-5">
          <Link to="/" className="flex items-center gap-2.5">
            <div className="rounded-lg bg-accent/10 p-1.5 text-accent">
              <Activity className="h-5 w-5" />
            </div>
            <span className="text-sm font-semibold tracking-tight">Anomaly</span>
          </Link>
          <button
            className="lg:hidden text-muted hover:text-text"
            onClick={() => setMobileOpen(false)}
            aria-label="Close menu"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <nav className="p-3">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                cn(
                  "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors duration-150 ease-out",
                  isActive
                    ? "bg-accent/10 text-accent"
                    : "text-muted hover:bg-surface-2 hover:text-text"
                )
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            className="fixed inset-0 z-30 bg-black/50 lg:hidden"
            onClick={() => setMobileOpen(false)}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
          />
        )}
      </AnimatePresence>

      {/* Main */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex h-16 items-center justify-between border-b border-border bg-surface px-4 sm:px-6">
          <button
            className="lg:hidden text-muted hover:text-text"
            onClick={() => setMobileOpen(true)}
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="flex-1" />
          <div className="flex items-center gap-2">
            <button
              onClick={toggle}
              title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
              className="rounded-xl p-2 text-muted transition-colors hover:bg-surface-2 hover:text-text"
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
            <div className="hidden sm:flex items-center gap-2 rounded-xl border border-border bg-surface-2 px-3 py-1.5">
              <div className="h-6 w-6 rounded-full bg-accent/20 grid place-items-center text-xs font-semibold text-accent">
                {user?.email?.[0]?.toUpperCase() || "?"}
              </div>
              <span className="text-xs text-text max-w-[160px] truncate">{user?.email}</span>
            </div>
            <button
              onClick={logout}
              title="Sign out"
              aria-label="Sign out"
              className="rounded-xl p-2 text-muted transition-colors hover:bg-surface-2 hover:text-text"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <div className="mx-auto max-w-7xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
