import { useEffect, useState } from "react";
import { Save, Sliders, Sun, Moon } from "lucide-react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Slider } from "../components/Slider";
import { FullPageSpinner } from "../components/Spinner";
import { useToast } from "../components/Toast";
import { useTheme } from "../theme/ThemeProvider";
import { models as modelsApi, thresholds, ModelInfo } from "../api/client";

export default function Settings() {
  const { theme, setTheme } = useTheme();
  const [items, setItems] = useState<ModelInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [zValues, setZValues] = useState<Record<number, number>>({});
  const [saving, setSaving] = useState<number | null>(null);
  const toast = useToast();

  useEffect(() => {
    modelsApi
      .list()
      .then((r) => {
        const ready = r.data.filter((m) => m.status === "ready" && m.threshold);
        setItems(ready);
        setZValues(
          Object.fromEntries(ready.map((m) => [m.id, m.threshold!.z_multiplier]))
        );
      })
      .finally(() => setLoading(false));
  }, []);

  const save = async (modelId: number) => {
    setSaving(modelId);
    try {
      const r = await thresholds.update(modelId, zValues[modelId]);
      setItems((prev) =>
        prev.map((m) =>
          m.id === modelId
            ? {
                ...m,
                threshold: {
                  mu: r.data.mu,
                  sigma: r.data.sigma,
                  epsilon: r.data.epsilon,
                  z_multiplier: r.data.z_multiplier,
                },
              }
            : m
        )
      );
      toast({ tone: "success", title: "Threshold saved", message: `ε = ${r.data.epsilon.toFixed(4)}` });
    } catch {
      toast({ tone: "error", title: "Could not save threshold" });
    } finally {
      setSaving(null);
    }
  };

  const previewEpsilon = (m: ModelInfo, z: number) =>
    m.threshold ? m.threshold.mu + z * m.threshold.sigma : 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-muted">Appearance and per-model threshold controls.</p>
      </div>

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

      {/* Thresholds */}
      <div>
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-text">
          <Sliders className="h-4 w-4 text-accent" />
          Detection thresholds
        </h3>
        {loading ? (
          <FullPageSpinner />
        ) : items.length === 0 ? (
          <Card>
            <p className="text-sm text-muted">Train a model first to configure its threshold.</p>
          </Card>
        ) : (
          <div className="space-y-4">
            {items.map((m) => (
              <Card key={m.id}>
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div>
                    <p className="text-sm font-semibold">Model #{m.id} · {m.algorithm}</p>
                    <p className="mt-0.5 text-xs text-muted">
                      μ = {m.threshold!.mu.toFixed(4)} · σ = {m.threshold!.sigma.toFixed(4)}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    onClick={() => save(m.id)}
                    loading={saving === m.id}
                    icon={<Save className="h-3.5 w-3.5" />}
                    disabled={zValues[m.id] === m.threshold!.z_multiplier}
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
                    value={zValues[m.id] ?? 3}
                    onChange={(e) =>
                      setZValues((v) => ({ ...v, [m.id]: parseFloat(e.target.value) }))
                    }
                    formatter={(v) => `z = ${v.toFixed(1)}`}
                  />
                </div>

                <div className="mt-4 flex items-center justify-between rounded-xl bg-surface-2/60 p-3">
                  <div className="text-xs text-muted">
                    <p>Current threshold ε (saved)</p>
                    <p className="mt-0.5 font-mono text-sm text-text">
                      {m.threshold!.epsilon.toFixed(4)}
                    </p>
                  </div>
                  <div className="text-right text-xs text-muted">
                    <p>Preview at z = {(zValues[m.id] ?? 3).toFixed(1)}</p>
                    <p className="mt-0.5 font-mono text-sm text-accent">
                      {previewEpsilon(m, zValues[m.id] ?? 3).toFixed(4)}
                    </p>
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
    </div>
  );
}
