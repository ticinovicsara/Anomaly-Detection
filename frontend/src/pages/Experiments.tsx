import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Check, Download, FlaskConical, Sparkles } from "lucide-react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { TableRowsSkeleton } from "../components/Skeleton";
import { useToast } from "../components/Toast";
import {
  errorMessage,
  experiments as experimentsApi,
  isCancelled,
  subjects as subjectsApi,
  ExperimentResult,
  PresetDemoResult,
  Subject,
} from "../api/client";

function pct(v: number | null): string {
  return v === null ? "-" : `${(v * 100).toFixed(1)}%`;
}

function average(values: (number | null)[]): number | null {
  const present = values.filter((v): v is number => v !== null);
  if (present.length === 0) return null;
  return present.reduce((a, b) => a + b, 0) / present.length;
}

export default function Experiments() {
  const toast = useToast();

  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [loadingSubjects, setLoadingSubjects] = useState(true);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const [result, setResult] = useState<ExperimentResult | PresetDemoResult | null>(null);
  const [running, setRunning] = useState(false);
  const [runningDemo, setRunningDemo] = useState(false);

  const loadSubjects = (signal?: AbortSignal) =>
    subjectsApi.list({ signal }).then((r) => {
      setSubjects(r.data);
      setSelected((prev) => {
        if (prev.size > 0) return prev;
        return new Set(r.data.filter((s) => s.active_epsilon !== null).map((s) => s.id));
      });
    });

  useEffect(() => {
    const controller = new AbortController();
    loadSubjects(controller.signal)
      .catch((err) => {
        if (!isCancelled(err)) throw err;
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingSubjects(false);
      });
    return () => controller.abort();
  }, []);

  const trainedSubjects = useMemo(() => subjects.filter((s) => s.active_epsilon !== null), [subjects]);

  const toggle = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => setSelected(new Set(trainedSubjects.map((s) => s.id)));
  const selectNone = () => setSelected(new Set());

  const runExperiment = async () => {
    setRunning(true);
    try {
      const r = await experimentsApi.run(Array.from(selected));
      setResult(r.data);
    } catch (err) {
      toast({ tone: "error", title: "Experiment failed", message: errorMessage(err) });
    } finally {
      setRunning(false);
    }
  };

  const runPresetDemo = async () => {
    setRunningDemo(true);
    try {
      const r = await experimentsApi.presetDemo();
      setResult(r.data);
      toast({
        tone: "success",
        title: "Demo ready",
        message: `Created ${r.data.created_subject_ids.length} synthetic subjects and ran the experiment across them.`,
      });
      await loadSubjects();
    } catch (err) {
      toast({ tone: "error", title: "Demo failed", message: errorMessage(err) });
    } finally {
      setRunningDemo(false);
    }
  };

  const exportJson = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `personalization-experiment-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const chartData = result
    ? Object.entries(result.epsilons)
        .map(([name, epsilon]) => ({ name, epsilon }))
        .sort((a, b) => a.epsilon - b.epsilon)
    : [];

  const globalEps = result?.cross_application.global_epsilon ?? null;
  const lowGroupFp = result
    ? average(
        Object.entries(result.epsilons)
          .filter(([, eps]) => eps < (globalEps ?? 0))
          .map(([name]) => result.cross_application.fp_rate_at_global[name] ?? null)
      )
    : null;
  const highGroupMiss = result
    ? average(
        Object.entries(result.epsilons)
          .filter(([, eps]) => eps >= (globalEps ?? 0))
          .map(([name]) => result.cross_application.miss_rate_at_global[name] ?? null)
      )
    : null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Personalization experiment</h1>
        <p className="mt-1 text-sm text-muted">
          Run this experiment across your subjects to visualize the impact of personalized thresholds vs. a
          single global one.
        </p>
      </div>

      <Card>
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <h3 className="text-sm font-semibold text-text">Select subjects to include</h3>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={selectAll} disabled={trainedSubjects.length === 0}>
              Select all
            </Button>
            <Button variant="ghost" size="sm" onClick={selectNone} disabled={selected.size === 0}>
              Select none
            </Button>
          </div>
        </div>

        {loadingSubjects ? (
          <div className="mt-4">
            <TableRowsSkeleton rows={3} />
          </div>
        ) : trainedSubjects.length === 0 ? (
          <EmptyState
            icon={FlaskConical}
            title="No trained subjects yet"
            message="Train at least two subjects to compare their thresholds, or try the preset demo below."
          />
        ) : (
          <ul className="mt-4 grid gap-2 sm:grid-cols-2">
            {trainedSubjects.map((s) => {
              const checked = selected.has(s.id);
              return (
                <li key={s.id}>
                  <button
                    onClick={() => toggle(s.id)}
                    className="flex w-full items-center justify-between gap-3 rounded-xl border border-border bg-surface-2/50 px-3.5 py-2.5 text-left transition-colors duration-150 hover:border-accent/40"
                  >
                    <span className="flex items-center gap-2.5 min-w-0">
                      <span
                        className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-md border transition-colors duration-150 ${
                          checked ? "border-accent bg-accent text-white" : "border-border bg-surface"
                        }`}
                      >
                        {checked && <Check className="h-3 w-3" strokeWidth={3} />}
                      </span>
                      <span className="truncate text-sm text-text">{s.name}</span>
                    </span>
                    <span className="shrink-0 font-mono text-xs text-muted">ε = {s.active_epsilon!.toFixed(4)}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}

        <div className="mt-5">
          <Button onClick={runExperiment} loading={running} disabled={selected.size < 2} icon={<FlaskConical className="h-4 w-4" />}>
            Run experiment
          </Button>
          {selected.size < 2 && trainedSubjects.length > 0 && (
            <p className="mt-2 text-xs text-muted">Select at least 2 subjects to run the comparison.</p>
          )}
        </div>
      </Card>

      <Card>
        <h3 className="text-sm font-semibold text-text">Or: try a preset demo</h3>
        <p className="mt-1 text-sm text-muted">
          Generates 10 synthetic subjects sharing the same underlying signal structure but different noise
          levels, trains an LSTM Autoencoder independently on each, and runs the experiment across them — a
          quick way to see the argument without uploading real data first.
        </p>
        <div className="mt-4">
          <Button variant="secondary" onClick={runPresetDemo} loading={runningDemo} icon={<Sparkles className="h-4 w-4" />}>
            Load &amp; run demo
          </Button>
        </div>
      </Card>

      {result && (
        <>
          <Card>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-text">Results — threshold histogram</h3>
              <Button variant="ghost" size="sm" onClick={exportJson} icon={<Download className="h-3.5 w-3.5" />}>
                Export as JSON
              </Button>
            </div>
            <div className="mt-4 h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid stroke="rgb(var(--border))" strokeDasharray="3 3" />
                  <XAxis dataKey="name" stroke="rgb(var(--muted))" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis stroke="rgb(var(--muted))" fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip
                    contentStyle={{
                      background: "rgb(var(--surface))",
                      border: "1px solid rgb(var(--border))",
                      borderRadius: 12,
                      fontSize: 12,
                    }}
                    formatter={(v: number) => v.toFixed(4)}
                  />
                  {globalEps !== null && (
                    <ReferenceLine
                      y={globalEps}
                      stroke="rgb(var(--danger))"
                      strokeDasharray="4 4"
                      label={{ value: "global ε (mean)", fill: "rgb(var(--danger))", fontSize: 10 }}
                    />
                  )}
                  <Bar dataKey="epsilon" fill="rgb(var(--accent))" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-3 text-xs text-muted">
              Range: {result.statistics.min.toFixed(4)} – {result.statistics.max.toFixed(4)}
              {result.statistics.range_ratio !== null && ` (${result.statistics.range_ratio.toFixed(1)}× spread)`} —
              personalization is visibly non-trivial.
            </p>
          </Card>

          <Card>
            <h3 className="text-sm font-semibold text-text">Cross-application impact</h3>
            <p className="mt-1 text-xs text-muted">
              What happens if a single global threshold (the mean ε across the selected subjects, {globalEps?.toFixed(4)})
              were applied to everyone instead of each subject's own personalized ε.
            </p>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div className="rounded-xl bg-surface-2/60 p-4">
                <p className="text-xs text-muted">Subjects with a naturally lower threshold</p>
                <p className="mt-1 text-2xl font-semibold text-danger">{pct(lowGroupFp)}</p>
                <p className="mt-0.5 text-xs text-muted">average false-positive rate under the global threshold</p>
              </div>
              <div className="rounded-xl bg-surface-2/60 p-4">
                <p className="text-xs text-muted">Subjects with a naturally higher threshold</p>
                <p className="mt-1 text-2xl font-semibold text-danger">{pct(highGroupMiss)}</p>
                <p className="mt-0.5 text-xs text-muted">average missed-anomaly rate under the global threshold</p>
              </div>
            </div>
            <p className="mt-4 text-xs text-muted">
              Personalized thresholds eliminate both by construction — each subject is scored only against its own
              calibrated ε, never the population average.
            </p>

            <div className="mt-5 overflow-x-auto -mx-6">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wider text-muted">
                    <th className="px-6 py-2.5 font-medium">Subject</th>
                    <th className="px-6 py-2.5 font-medium">Personal ε</th>
                    <th className="px-6 py-2.5 font-medium">FP rate at global ε</th>
                    <th className="px-6 py-2.5 font-medium">Miss rate at global ε</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(result.epsilons).map(([name, eps]) => (
                    <tr key={name} className="border-b border-border/50 last:border-0">
                      <td className="px-6 py-2.5 text-text">{name}</td>
                      <td className="px-6 py-2.5 font-mono text-muted">{eps.toFixed(4)}</td>
                      <td className="px-6 py-2.5 font-mono text-muted">{pct(result.cross_application.fp_rate_at_global[name] ?? null)}</td>
                      <td className="px-6 py-2.5 font-mono text-muted">{pct(result.cross_application.miss_rate_at_global[name] ?? null)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card>
            <h3 className="text-sm font-semibold text-text">Statistics</h3>
            <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-5">
              <Stat label="mean ε" value={result.statistics.mean.toFixed(4)} />
              <Stat label="std ε" value={result.statistics.std.toFixed(4)} />
              <Stat label="min ε" value={result.statistics.min.toFixed(4)} />
              <Stat label="max ε" value={result.statistics.max.toFixed(4)} />
              <Stat label="range ratio" value={result.statistics.range_ratio !== null ? `${result.statistics.range_ratio.toFixed(1)}×` : "-"} />
            </div>
          </Card>

          {"created_subject_ids" in result && (
            <p className="text-xs text-muted">
              Demo subjects were added to your account — view them on the{" "}
              <Link to="/subjects" className="text-accent hover:underline">
                Subjects page
              </Link>
              .
            </p>
          )}
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 font-mono text-lg font-semibold text-text">{value}</p>
    </div>
  );
}
