import { Sun, Moon, Wrench } from "lucide-react";
import { Card } from "@/components/Card";
import { Checkbox } from "@/components/Checkbox";
import { PageHeader } from "@/components/PageHeader";
import { useAdvancedMode } from "@/hooks";
import { useTheme } from "@/theme/ThemeProvider";

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const { enabled: advancedMode, toggle: toggleAdvancedMode } = useAdvancedMode();

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" subtitle="Appearance and advanced options." />

      {/* Theme */}
      <Card>
        <h3 className="text-sm font-semibold text-text">Appearance</h3>
        <p className="mt-1 text-xs text-muted">Toggle between dark and light themes.</p>
        <div className="mt-4 inline-flex rounded-xl border border-border bg-surface-2 p-1">
          <button
            onClick={() => setTheme("light")}
            className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm transition-colors ${
              theme === "light" ? "bg-surface text-text shadow-soft" : "text-muted hover:text-text"
            }`}
          >
            <Sun className="h-4 w-4" />
            Light
          </button>
          <button
            onClick={() => setTheme("dark")}
            className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm transition-colors ${
              theme === "dark" ? "bg-surface text-text shadow-soft" : "text-muted hover:text-text"
            }`}
          >
            <Moon className="h-4 w-4" />
            Dark
          </button>
        </div>
      </Card>

      {/* Advanced */}
      <div>
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-text">
          <Wrench className="h-4 w-4 text-accent" />
          Advanced
        </h3>
        <Card>
          <label className="flex cursor-pointer items-start gap-3">
            <Checkbox className="mt-0.5" checked={advancedMode} onChange={toggleAdvancedMode} />
            <div>
              <span className="text-sm font-medium text-text">Show manual algorithm selection</span>
              <p className="mt-0.5 text-xs text-muted">
                By default, the system picks the best algorithm for your data automatically. Enable this to
                override the choice per subject, train alternative algorithms for comparison, and see every
                model (not just the active one).
              </p>
            </div>
          </label>
        </Card>
      </div>
    </div>
  );
}
