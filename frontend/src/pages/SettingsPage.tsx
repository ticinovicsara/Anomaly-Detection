import { useEffect, useState } from "react";
import { Save, Sliders, Sun, Moon, Wrench } from "lucide-react";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Checkbox } from "@/components/Checkbox";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { Slider } from "@/components/Slider";
import { FullPageSpinner } from "@/components/Spinner";
import { useToast } from "@/components/Toast";
import { useAdvancedMode } from "@/hooks";
import { useTheme } from "@/theme/ThemeProvider";
import { isCancelled, subjects as subjectsApi, thresholds, Subject } from "@/api/client";

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const { enabled: advancedMode, toggle: toggleAdvancedMode } = useAdvancedMode();

  const [items, setItems] = useState<Subject[]>([]);
  const [loading, setLoading] = useState(true);
  const [zValues, setZValues] = useState<Record<number, number>>({});
  const [saving, setSaving] = useState<number | null>(null);
  const toast = useToast();

  useEffect(() => {
    const controller = new AbortController();
    subjectsApi
      .list({ signal: controller.signal })
      .then((r) => {
        const trained = r.data.filter((s) => s.active_model_id !== null && s.active_z_multiplier !== null);
        setItems(trained);
        setZValues(Object.fromEntries(trained.map((s) => [s.id, s.active_z_multiplier!])));
      })
      .catch((err) => {
        if (!isCancelled(err)) throw err;
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  const save = async (subject: Subject) => {
    if (!subject.active_model_id) return;
    setSaving(subject.id);
    try {
      const r = await thresholds.update(subject.active_model_id, zValues[subject.id]);
      setItems((prev) =>
        prev.map((s) =>
          s.id === subject.id
            ? { ...s, active_epsilon: r.data.epsilon, active_mu: r.data.mu, active_sigma: r.data.sigma, active_z_multiplier: r.data.z_multiplier }
            : s
        )
      );
      toast({ tone: "success", title: "Threshold saved", message: `ε = ${r.data.epsilon.toFixed(4)}` });
    } catch {
      toast({ tone: "error", title: "Could not save threshold" });
    } finally {
      setSaving(null);
    }
  };

  const previewEpsilon = (s: Subject, z: number) => (s.active_mu !== null && s.active_sigma !== null ? s.active_mu + z * s.active_sigma : 0);

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" subtitle="Appearance, per-subject threshold controls, and advanced options." />

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

      {/* Thresholds -- per Subject, not per model: epsilon is a property of
          the Subject's active model, and a Subject only ever has one. */}
      <div>
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-text">
          <Sliders className="h-4 w-4 text-accent" />
          Detection thresholds
        </h3>
        {loading ? (
          <FullPageSpinner />
        ) : items.length === 0 ? (
          <Card>
            <EmptyState
              icon={Sliders}
              title="No trained subjects yet"
              message="Train a subject first to configure its detection threshold."
            />
          </Card>
        ) : (
          <div className="space-y-4">
            {items.map((s) => (
              <Card key={s.id}>
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div>
                    <p className="text-sm font-semibold">{s.name} · {s.active_algorithm}</p>
                    <p className="mt-0.5 text-xs text-muted">
                      μ = {s.active_mu!.toFixed(4)} · σ = {s.active_sigma!.toFixed(4)}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    onClick={() => save(s)}
                    loading={saving === s.id}
                    icon={<Save className="h-3.5 w-3.5" />}
                    disabled={zValues[s.id] === s.active_z_multiplier}
                  >
                    Save
                  </Button>
                </div>

                <div className="mt-5">
                  <Slider
                    label="z-multiplier"
                    min={1}
                    max={6}
                    step={0.1}
                    value={zValues[s.id] ?? 3}
                    onChange={(e) => setZValues((v) => ({ ...v, [s.id]: parseFloat(e.target.value) }))}
                    formatter={(v) => `z = ${v.toFixed(1)}`}
                  />
                </div>

                <div className="mt-4 flex items-center justify-between rounded-xl bg-surface-2/60 p-3">
                  <div className="text-xs text-muted">
                    <p>Current threshold ε (saved)</p>
                    <p className="mt-0.5 font-mono text-sm text-text">{s.active_epsilon!.toFixed(4)}</p>
                  </div>
                  <div className="text-right text-xs text-muted">
                    <p>Preview at z = {(zValues[s.id] ?? 3).toFixed(1)}</p>
                    <p className="mt-0.5 font-mono text-sm text-accent">{previewEpsilon(s, zValues[s.id] ?? 3).toFixed(4)}</p>
                  </div>
                </div>

                <p className="mt-3 text-[11px] text-muted">
                  Lower z → more sensitive (more alarms). Higher z → more tolerant (fewer alarms). Default: 3.0.
                </p>
              </Card>
            ))}
          </div>
        )}
      </div>

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
