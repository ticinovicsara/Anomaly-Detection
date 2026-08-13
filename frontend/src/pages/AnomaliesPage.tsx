import { useEffect, useState } from "react";
import { Check, X, RotateCcw, Filter, ShieldCheck } from "lucide-react";
import {
  Button,
  Card,
  Badge,
  severityTone,
  useToast,
  PageHeader,
  EmptyState,
  TableRowsSkeleton,
} from "@/components";
import {
  anomalies as api,
  isCancelled,
  subjects as subjectsApi,
  Anomaly,
  Subject,
} from "@/api/client";

const labels = [
  { value: "", label: "All" },
  { value: "unlabeled", label: "Unlabeled" },
  { value: "confirmed", label: "Confirmed" },
  { value: "false_positive", label: "False positive" },
  { value: "resolved", label: "Resolved" },
];

export default function AnomaliesPage() {
  const [items, setItems] = useState<Anomaly[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [loading, setLoading] = useState(true);
  const [labelFilter, setLabelFilter] = useState("");
  const [subjectFilter, setSubjectFilter] = useState<number | null>(null);
  const toast = useToast();

  useEffect(() => {
    const controller = new AbortController();
    subjectsApi
      .list({ signal: controller.signal })
      .then((r) => setSubjects(r.data))
      .catch(() => {});
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    api
      .list(
        {
          label: labelFilter || undefined,
          subject_id: subjectFilter ?? undefined,
          limit: 200,
        },
        { signal: controller.signal },
      )
      .then((r) => setItems(r.data))
      .catch((err) => {
        if (!isCancelled(err)) throw err;
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [labelFilter, subjectFilter]);

  const subjectById = new Map(subjects.map((s) => [s.id, s]));

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
      <PageHeader
        title="Anomalies"
        subtitle="Review detected anomalies and label them. Your feedback improves calibration."
      />

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
      {subjects.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="w-4" />
          <button
            onClick={() => setSubjectFilter(null)}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
              subjectFilter === null
                ? "border-accent bg-accent/10 text-accent"
                : "border-border text-muted hover:text-text"
            }`}
          >
            All subjects
          </button>
          {subjects.map((s) => (
            <button
              key={s.id}
              onClick={() => setSubjectFilter(s.id)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                subjectFilter === s.id
                  ? "border-accent bg-accent/10 text-accent"
                  : "border-border text-muted hover:text-text"
              }`}
            >
              {s.name}
            </button>
          ))}
        </div>
      )}

      {/* List */}
      {loading ? (
        <Card className="p-0">
          <TableRowsSkeleton />
        </Card>
      ) : items.length === 0 ? (
        <Card>
          <EmptyState
            icon={ShieldCheck}
            title={
              labelFilter ? "No matches for this filter" : "No anomalies yet"
            }
            message={
              labelFilter
                ? "Try a different label, or clear the filter to see everything."
                : "Anomalies will show up here once a model flags something in your data."
            }
          />
        </Card>
      ) : (
        <Card className="p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-wider text-muted">
                  <th className="px-6 py-3 font-medium">When</th>
                  <th className="px-6 py-3 font-medium">Subject</th>
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
                  <tr
                    key={a.id}
                    className="border-b border-border/50 last:border-0 hover:bg-surface-2/30"
                  >
                    <td className="px-6 py-3 text-xs text-muted">
                      {new Date(a.created_at).toLocaleString()}
                    </td>
                    <td className="px-6 py-3">
                      {subjectById.get(a.subject_id) ? (
                        <Badge>{subjectById.get(a.subject_id)!.name}</Badge>
                      ) : (
                        <span className="text-xs text-muted">-</span>
                      )}
                    </td>
                    <td className="px-6 py-3 font-mono text-xs text-muted">
                      #{a.model_id}
                    </td>
                    <td className="px-6 py-3 font-mono text-xs">
                      {a.window_idx}
                    </td>
                    <td className="px-6 py-3 font-mono text-xs">
                      {a.score.toFixed(3)}
                    </td>
                    <td className="px-6 py-3">
                      <Badge tone={severityTone(a.severity)}>
                        {a.severity}
                      </Badge>
                    </td>
                    <td className="px-6 py-3">
                      <Badge
                        tone={
                          a.label === "confirmed"
                            ? "success"
                            : a.label === "false_positive"
                              ? "danger"
                              : "default"
                        }
                      >
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
  const cls =
    tone === "success"
      ? "text-success"
      : tone === "warning"
        ? "text-warning"
        : "text-text";
  return (
    <Card>
      <p className="text-xs uppercase tracking-wider text-muted">{label}</p>
      <p className={`mt-2 text-2xl font-semibold ${cls}`}>{value}</p>
    </Card>
  );
}
