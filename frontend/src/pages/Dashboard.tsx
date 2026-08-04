import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  Brain,
  Database,
  Upload as UploadIcon,
} from "lucide-react";
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
import { FullPageSpinner } from "../components/Spinner";
import { anomalies as anomaliesApi, isCancelled, models as modelsApi, Anomaly, ModelInfo } from "../api/client";

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [recent, setRecent] = useState<Anomaly[]>([]);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      modelsApi.list({ signal: controller.signal }),
      anomaliesApi.list({ limit: 30 }, { signal: controller.signal }),
    ])
      .then(([m, a]) => {
        setModels(m.data);
        setRecent(a.data);
      })
      .catch((err) => {
        if (!isCancelled(err)) throw err;
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  if (loading) return <FullPageSpinner />;

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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="mt-1 text-sm text-muted">
            Overview of your models and recently detected anomalies.
          </p>
        </div>
        <Link to="/upload">
          <Button icon={<UploadIcon className="h-4 w-4" />}>Upload data</Button>
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Anomalies today"
          value={inLast(1)}
          tone={inLast(1) > 0 ? "warning" : "default"}
          icon={<AlertTriangle className="h-5 w-5" />}
        />
        <StatCard label="Past 7 days" value={inLast(7)} icon={<Activity className="h-5 w-5" />} />
        <StatCard
          label="Trained models"
          value={readyModels.length}
          hint={`${models.length - readyModels.length} training / failed`}
          icon={<Brain className="h-5 w-5" />}
        />
        <StatCard
          label="Datasets"
          value={new Set(models.map((m) => m.dataset_id)).size}
          icon={<Database className="h-5 w-5" />}
        />
      </div>

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
            <p className="text-sm text-muted">Nothing yet — upload data and train a model to get started.</p>
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
                    <p className="mt-0.5 text-xs text-muted">
                      {new Date(a.created_at).toLocaleString()}
                    </p>
                  </div>
                  <Badge tone={severityTone(a.severity)}>{a.severity}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

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
                    <td className="px-6 py-3">
                      <Badge tone="accent">{m.algorithm}</Badge>
                    </td>
                    <td className="px-6 py-3">
                      <Badge tone={statusTone(m.status)}>{m.status}</Badge>
                    </td>
                    <td className="px-6 py-3 text-muted text-xs max-w-md truncate">
                      {m.selection_reason ?? "—"}
                    </td>
                    <td className="px-6 py-3 font-mono text-muted">
                      {m.threshold ? m.threshold.epsilon.toFixed(4) : "—"}
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
