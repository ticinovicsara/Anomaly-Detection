import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, AlertTriangle, Brain, Users, Upload as UploadIcon } from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Button } from "../components/Button";
import { Card, StatCard } from "../components/Card";
import { Badge, severityTone, statusTone } from "../components/Badge";
import { DashboardSkeleton } from "../components/Skeleton";
import { StaggerGroup, StaggerItem } from "../components/Stagger";
import {
  anomalies as anomaliesApi,
  isCancelled,
  models as modelsApi,
  subjects as subjectsApi,
  Anomaly,
  ModelInfo,
  Subject,
} from "../api/client";

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [recent, setRecent] = useState<Anomaly[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      modelsApi.list({ signal: controller.signal }),
      anomaliesApi.list({ limit: 30 }, { signal: controller.signal }),
      subjectsApi.list({ signal: controller.signal }),
    ])
      .then(([m, a, s]) => {
        setModels(m.data);
        setRecent(a.data);
        setSubjects(s.data);
      })
      .catch((err) => {
        if (!isCancelled(err)) throw err;
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  if (loading) return <DashboardSkeleton />;

  const readyModels = models.filter((m) => m.status === "ready");
  const now = Date.now();
  const dayMs = 24 * 60 * 60 * 1000;
  const inLast = (days: number) =>
    recent.filter((a) => now - new Date(a.created_at).getTime() < days * dayMs).length;

  const chartData = [...recent]
    .reverse()
    .slice(-40)
    .map((a) => ({ idx: a.window_idx, score: a.score }));
  const currentEpsilon = readyModels[0]?.threshold?.epsilon ?? null;

  const subjectById = new Map(subjects.map((s) => [s.id, s]));
  const trainedSubjects = subjects.filter((s) => s.active_epsilon !== null).sort((a, b) => (a.active_epsilon ?? 0) - (b.active_epsilon ?? 0));
  const maxEpsilon = Math.max(...trainedSubjects.map((s) => s.active_epsilon ?? 0), 0.0001);
  const minEpsilon = Math.min(...trainedSubjects.map((s) => s.active_epsilon ?? Infinity));
  const spreadRatio = minEpsilon > 0 && trainedSubjects.length > 1 ? maxEpsilon / minEpsilon : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="mt-1 text-sm text-muted">
            Overview of your subjects, models, and recently detected anomalies.
          </p>
        </div>
        <Link to="/upload">
          <Button icon={<UploadIcon className="h-4 w-4" />}>Upload data</Button>
        </Link>
      </div>

      {/* Stats */}
      <StaggerGroup className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StaggerItem>
          <StatCard
            label="Anomalies today"
            value={inLast(1)}
            tone={inLast(1) > 0 ? "warning" : "default"}
            icon={<AlertTriangle className="h-5 w-5" />}
          />
        </StaggerItem>
        <StaggerItem>
          <StatCard label="Past 7 days" value={inLast(7)} icon={<Activity className="h-5 w-5" />} />
        </StaggerItem>
        <StaggerItem>
          <StatCard
            label="Trained models"
            value={readyModels.length}
            hint={`${models.length - readyModels.length} training / failed`}
            icon={<Brain className="h-5 w-5" />}
          />
        </StaggerItem>
        <StaggerItem>
          <Link to="/subjects">
            <StatCard label="Subjects" value={subjects.length} icon={<Users className="h-5 w-5" />} />
          </Link>
        </StaggerItem>
      </StaggerGroup>

      {/* Chart + Recent anomalies */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-text">Anomaly scores</h3>
            {currentEpsilon !== null && (
              <Badge tone="accent">threshold ε = {currentEpsilon.toFixed(3)}</Badge>
            )}
          </div>
          {chartData.length === 0 ? (
            <EmptyChart />
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid stroke="rgb(var(--border))" strokeDasharray="3 3" />
                  <XAxis
                    dataKey="idx"
                    stroke="rgb(var(--muted))"
                    fontSize={11}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    stroke="rgb(var(--muted))"
                    fontSize={11}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "rgb(var(--surface))",
                      border: "1px solid rgb(var(--border))",
                      borderRadius: 12,
                      fontSize: 12,
                    }}
                  />
                  {currentEpsilon !== null && (
                    <ReferenceLine
                      y={currentEpsilon}
                      stroke="rgb(var(--danger))"
                      strokeDasharray="4 4"
                      label={{ value: "threshold", fill: "rgb(var(--danger))", fontSize: 10 }}
                    />
                  )}
                  <Line
                    type="monotone"
                    dataKey="score"
                    stroke="rgb(var(--accent))"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card>
          <h3 className="mb-4 text-sm font-semibold text-text">Recent anomalies</h3>
          {recent.length === 0 ? (
            <p className="text-sm text-muted">Nothing yet. Upload data and train a model to get started.</p>
          ) : (
            <ul className="space-y-3 max-h-64 overflow-y-auto pr-1">
              {recent.slice(0, 8).map((a) => (
                <li
                  key={a.id}
                  className="flex items-start justify-between gap-3 rounded-xl border border-border bg-surface-2/50 p-3"
                >
                  <div className="min-w-0">
                    <p className="text-xs text-muted">
                      Window {a.window_idx} · score {a.score.toFixed(3)}
                    </p>
                    <div className="mt-1 flex items-center gap-1.5">
                      {subjectById.get(a.subject_id) && (
                        <Badge tone="default">{subjectById.get(a.subject_id)!.name}</Badge>
                      )}
                      <p className="text-xs text-muted">{new Date(a.created_at).toLocaleString()}</p>
                    </div>
                  </div>
                  <Badge tone={severityTone(a.severity)}>{a.severity}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {/* Threshold spread across subjects -- the visual proof that
          personalization is non-trivial; hidden unless it's actually
          possible to compare (2+ trained subjects). */}
      {trainedSubjects.length > 1 && (
        <Card>
          <h3 className="text-sm font-semibold text-text">Threshold spread across your subjects</h3>
          <div className="mt-4 space-y-2.5">
            {trainedSubjects.map((s) => {
              const pct = Math.max(4, ((s.active_epsilon ?? 0) / maxEpsilon) * 100);
              return (
                <Link
                  key={s.id}
                  to={`/subjects/${s.id}`}
                  className="flex items-center gap-3 rounded-lg px-1 py-1 hover:bg-surface-2/50"
                >
                  <span className="w-32 shrink-0 truncate text-xs text-muted">{s.name}</span>
                  <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-surface-2">
                    <div className="h-full rounded-full bg-accent transition-[width] duration-500 ease-out" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="w-24 shrink-0 text-right font-mono text-xs text-text">
                    ε = {(s.active_epsilon ?? 0).toFixed(4)}
                  </span>
                </Link>
              );
            })}
          </div>
          <p className="mt-4 text-xs text-muted">
            Range: {minEpsilon.toFixed(4)} – {maxEpsilon.toFixed(4)}
            {spreadRatio !== null && ` (${spreadRatio.toFixed(1)}× spread)`} — personalization is visibly non-trivial.
          </p>
        </Card>
      )}

      {/* Models table */}
      <Card>
        <h3 className="mb-4 text-sm font-semibold text-text">Your models</h3>
        {models.length === 0 ? (
          <p className="text-sm text-muted">No models yet.</p>
        ) : (
          <div className="overflow-x-auto -mx-6">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-wider text-muted">
                  <th className="px-6 py-3 font-medium">ID</th>
                  <th className="px-6 py-3 font-medium">Subject</th>
                  <th className="px-6 py-3 font-medium">Algorithm</th>
                  <th className="px-6 py-3 font-medium">Status</th>
                  <th className="px-6 py-3 font-medium">Reason</th>
                  <th className="px-6 py-3 font-medium">ε</th>
                </tr>
              </thead>
              <tbody>
                {models.map((m) => (
                  <tr key={m.id} className="border-b border-border/50 last:border-0">
                    <td className="px-6 py-3 font-mono text-muted">#{m.id}</td>
                    <td className="px-6 py-3 text-text">{subjectById.get(m.subject_id)?.name ?? "-"}</td>
                    <td className="px-6 py-3">
                      <Badge tone="accent">{m.algorithm}</Badge>
                    </td>
                    <td className="px-6 py-3">
                      <Badge tone={statusTone(m.status)}>{m.status}</Badge>
                    </td>
                    <td className="px-6 py-3 text-muted text-xs max-w-md truncate">
                      {m.selection_reason ?? "-"}
                    </td>
                    <td className="px-6 py-3 font-mono text-muted">
                      {m.threshold ? m.threshold.epsilon.toFixed(4) : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function EmptyChart() {
  return (
    <div className="flex h-64 flex-col items-center justify-center gap-2 text-muted">
      <Activity className="h-8 w-8 opacity-50" />
      <p className="text-sm">No predictions yet</p>
    </div>
  );
}
