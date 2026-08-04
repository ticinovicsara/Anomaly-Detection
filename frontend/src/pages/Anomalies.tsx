import { useEffect, useState } from "react";
import { Check, X, RotateCcw, Filter } from "lucide-react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Badge, severityTone } from "../components/Badge";
import { FullPageSpinner } from "../components/Spinner";
import { useToast } from "../components/Toast";
import { anomalies as api, Anomaly } from "../api/client";

const labels = [
  { value: "", label: "All" },
  { value: "unlabeled", label: "Unlabeled" },
  { value: "confirmed", label: "Confirmed" },
  { value: "false_positive", label: "False positive" },
  { value: "resolved", label: "Resolved" },
];

export default function Anomalies() {
  const [items, setItems] = useState<Anomaly[]>([]);
  const [loading, setLoading] = useState(true);
  const [labelFilter, setLabelFilter] = useState("");
  const toast = useToast();

  const load = () => {
    setLoading(true);
    api
      .list({ label: labelFilter || undefined, limit: 200 })
      .then((r) => setItems(r.data))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [labelFilter]);

  const setLabel = async (id: number, label: string) => {
    const previous = items;
    setItems((prev) => prev.map((a) => (a.id === id ? { ...a, label } : a)));
    try {
      const r = await api.label(id, label);
      setItems((prev) => prev.map((a) => (a.id === id ? r.data : a)));
      toast({ tone: "success", title: `Marked as ${label.replace("_", " ")}` });
    } catch {
      setItems(previous);
      toast({ tone: "error", title: "Could not update" });
    }
  };

  const fpCount = items.filter((a) => a.label === "false_positive").length;
  const confirmedCount = items.filter((a) => a.label === "confirmed").length;
  const fpRate = items.length ? (fpCount / items.length) * 100 : 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Anomalies</h1>
        <p className="mt-1 text-sm text-muted">
          Review detected anomalies and label them — your feedback improves calibration.
        </p>
      </div>

      {/* Summary */}
      <div className="grid gap-4 sm:grid-cols-3">
        <SummaryCard label="Total" value={items.length} />
        <SummaryCard label="Confirmed" value={confirmedCount} tone="success" />
        <SummaryCard
          label="False positive rate"
          value={`${fpRate.toFixed(1)}%`}
          tone={fpRate > 30 ? "warning" : "default"}
        />
      </div>

      {/* Filter */}
      <div className="flex items-center gap-2 flex-wrap">
        <Filter className="h-4 w-4 text-muted" />
        {labels.map((l) => (
          <button
            key={l.value}
            onClick={() => setLabelFilter(l.value)}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
              labelFilter === l.value
                ? "border-accent bg-accent/10 text-accent"
                : "border-border text-muted hover:text-text"
            }`}
          >
            {l.label}
          </button>
        ))}
      </div>

      {/* List */}
      {loading ? (
        <FullPageSpinner />
      ) : items.length === 0 ? (
        <Card>
          <p className="text-sm text-muted">No anomalies match this filter.</p>
        </Card>
      ) : (
        <Card className="p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-wider text-muted">
                  <th className="px-6 py-3 font-medium">When</th>
                  <th className="px-6 py-3 font-medium">Model</th>
                  <th className="px-6 py-3 font-medium">Window</th>
                  <th className="px-6 py-3 font-medium">Score</th>
                  <th className="px-6 py-3 font-medium">Severity</th>
                  <th className="px-6 py-3 font-medium">Label</th>
                  <th className="px-6 py-3 text-right font-medium">Action</th>
                </tr>
              </thead>
              <tbody>
                {items.map((a) => (
                  <tr key={a.id} className="border-b border-border/50 last:border-0 hover:bg-surface-2/30">
                    <td className="px-6 py-3 text-xs text-muted">{new Date(a.created_at).toLocaleString()}</td>
                    <td className="px-6 py-3 font-mono text-xs text-muted">#{a.model_id}</td>
                    <td className="px-6 py-3 font-mono text-xs">{a.window_idx}</td>
                    <td className="px-6 py-3 font-mono text-xs">{a.score.toFixed(3)}</td>
                    <td className="px-6 py-3">
                      <Badge tone={severityTone(a.severity)}>{a.severity}</Badge>
                    </td>
                    <td className="px-6 py-3">
                      <Badge tone={a.label === "confirmed" ? "success" : a.label === "false_positive" ? "danger" : "default"}>
                        {a.label.replace("_", " ")}
                      </Badge>
                    </td>
                    <td className="px-6 py-3 text-right">
                      <div className="inline-flex gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setLabel(a.id, "confirmed")}
                          title="Confirm"
                          aria-label="Confirm anomaly"
                        >
                          <Check className="h-3.5 w-3.5 text-success" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setLabel(a.id, "false_positive")}
                          title="Mark false positive"
                          aria-label="Mark as false positive"
                        >
                          <X className="h-3.5 w-3.5 text-danger" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setLabel(a.id, "unlabeled")}
                          title="Reset"
                          aria-label="Reset label"
                        >
                          <RotateCcw className="h-3.5 w-3.5 text-muted" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}

function SummaryCard({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string | number;
  tone?: "default" | "success" | "warning";
}) {
  const cls = tone === "success" ? "text-success" : tone === "warning" ? "text-warning" : "text-text";
  return (
    <Card>
      <p className="text-xs uppercase tracking-wider text-muted">{label}</p>
      <p className={`mt-2 text-2xl font-semibold ${cls}`}>{value}</p>
    </Card>
  );
}
