import { useEffect, useMemo, useState } from "react";
import { Check, X, RotateCcw, Filter, ShieldCheck, ChevronDown } from "lucide-react";
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

// Overlapping sliding windows mean one real anomaly can produce many
// consecutive AnomalyEvents (window_idx close together). Anything within
// this many windows of the previous one is treated as the same episode.
const EPISODE_WINDOW_GAP = 5;

type Episode = {
  key: string;
  modelId: number;
  windowMin: number;
  windowMax: number;
  peakScore: number;
  worstSeverity: string;
  events: Anomaly[];
};

function groupIntoEpisodes(events: Anomaly[]): Episode[] {
  const byModel = new Map<number, Anomaly[]>();
  for (const e of events) {
    const arr = byModel.get(e.model_id) ?? [];
    arr.push(e);
    byModel.set(e.model_id, arr);
  }

  const episodes: Episode[] = [];
  for (const [modelId, modelEvents] of byModel) {
    const sorted = [...modelEvents].sort((a, b) => a.window_idx - b.window_idx);
    let current: Anomaly[] = [];
    const flush = () => {
      if (current.length === 0) return;
      const windows = current.map((e) => e.window_idx);
      const scores = current.map((e) => e.score);
      const severityRank: Record<string, number> = { critical: 3, warning: 2, info: 1 };
      const worst = current.reduce((a, b) =>
        (severityRank[b.severity] ?? 0) > (severityRank[a.severity] ?? 0) ? b : a,
      );
      episodes.push({
        key: `${modelId}-${windows[0]}`,
        modelId,
        windowMin: Math.min(...windows),
        windowMax: Math.max(...windows),
        peakScore: Math.max(...scores),
        worstSeverity: worst.severity,
        events: [...current],
      });
      current = [];
    };
    for (const e of sorted) {
      const prev = current[current.length - 1];
      if (prev && e.window_idx - prev.window_idx > EPISODE_WINDOW_GAP) flush();
      current.push(e);
    }
    flush();
  }
  return episodes.sort((a, b) => {
    const aLatest = Math.max(...a.events.map((e) => new Date(e.created_at).getTime()));
    const bLatest = Math.max(...b.events.map((e) => new Date(e.created_at).getTime()));
    return bLatest - aLatest;
  });
}

export default function AnomaliesPage() {
  const [items, setItems] = useState<Anomaly[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [loading, setLoading] = useState(true);
  const [labelFilter, setLabelFilter] = useState("");
  const [subjectFilter, setSubjectFilter] = useState<number | null>(null);
  const [expandedSubjects, setExpandedSubjects] = useState<Set<number>>(new Set());
  const [expandedEpisodes, setExpandedEpisodes] = useState<Set<string>>(new Set());
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
    } catch {
      setItems(previous);
      toast({ tone: "error", title: "Could not update" });
    }
  };

  const setLabelForEpisode = async (episode: Episode, label: string) => {
    await Promise.all(episode.events.map((e) => setLabel(e.id, label)));
    toast({ tone: "success", title: `Marked ${episode.events.length} window(s) as ${label.replace("_", " ")}` });
  };

  const fpCount = items.filter((a) => a.label === "false_positive").length;
  const confirmedCount = items.filter((a) => a.label === "confirmed").length;
  const fpRate = items.length ? (fpCount / items.length) * 100 : 0;

  const bySubject = useMemo(() => {
    const map = new Map<number, Anomaly[]>();
    for (const a of items) {
      const arr = map.get(a.subject_id) ?? [];
      arr.push(a);
      map.set(a.subject_id, arr);
    }
    return Array.from(map.entries())
      .map(([subjectId, events]) => ({
        subjectId,
        subject: subjectById.get(subjectId),
        episodes: groupIntoEpisodes(events),
        total: events.length,
      }))
      .sort((a, b) => b.total - a.total);
  }, [items, subjects]);

  const toggleSubject = (id: number) => {
    setExpandedSubjects((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };
  const toggleEpisode = (key: string) => {
    setExpandedEpisodes((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Anomalies"
        subtitle="Grouped by subject, then by episode — overlapping windows from the same real event are collapsed into one row."
      />

      {/* Summary */}
      <div className="grid gap-4 sm:grid-cols-3">
        <SummaryCard label="Total detections" value={items.length} />
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

      {/* Grouped list */}
      {loading ? (
        <Card className="p-0">
          <TableRowsSkeleton />
        </Card>
      ) : items.length === 0 ? (
        <Card>
          <EmptyState
            icon={ShieldCheck}
            title={labelFilter ? "No matches for this filter" : "No anomalies yet"}
            message={
              labelFilter
                ? "Try a different label, or clear the filter to see everything."
                : "Anomalies will show up here once a model flags something in your data."
            }
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {bySubject.map(({ subjectId, subject, episodes, total }) => {
            const subjectOpen = expandedSubjects.has(subjectId) || bySubject.length === 1;
            return (
              <Card key={subjectId} className="p-0 overflow-hidden">
                <button
                  onClick={() => toggleSubject(subjectId)}
                  className="flex w-full items-center justify-between gap-3 px-6 py-4 text-left hover:bg-surface-2/30"
                >
                  <div className="flex items-center gap-3">
                    <Badge>{subject?.name ?? `Subject #${subjectId}`}</Badge>
                    <span className="text-xs text-muted">
                      {episodes.length} episode{episodes.length === 1 ? "" : "s"} · {total} window
                      {total === 1 ? "" : "s"} total
                    </span>
                  </div>
                  <ChevronDown
                    className={`h-4 w-4 text-muted transition-transform duration-150 ${subjectOpen ? "rotate-180" : ""}`}
                  />
                </button>

                {subjectOpen && (
                  <div className="border-t border-border">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border text-left text-xs uppercase tracking-wider text-muted">
                          <th className="px-6 py-2.5 font-medium">Episode</th>
                          <th className="px-6 py-2.5 font-medium">Model</th>
                          <th className="px-6 py-2.5 font-medium">Windows</th>
                          <th className="px-6 py-2.5 font-medium">Peak score</th>
                          <th className="px-6 py-2.5 font-medium">Severity</th>
                          <th className="px-6 py-2.5 text-right font-medium">Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {episodes.map((ep) => {
                          const open = expandedEpisodes.has(ep.key);
                          return (
                            <>
                              <tr
                                key={ep.key}
                                className="cursor-pointer border-b border-border/50 hover:bg-surface-2/30"
                                onClick={() => toggleEpisode(ep.key)}
                              >
                                <td className="px-6 py-3">
                                  <div className="flex items-center gap-2">
                                    <ChevronDown
                                      className={`h-3.5 w-3.5 text-muted transition-transform duration-150 ${open ? "rotate-180" : ""}`}
                                    />
                                    <span className="text-xs text-muted">
                                      {ep.events.length} window{ep.events.length === 1 ? "" : "s"}
                                    </span>
                                  </div>
                                </td>
                                <td className="px-6 py-3 font-mono text-xs text-muted">#{ep.modelId}</td>
                                <td className="px-6 py-3 font-mono text-xs">
                                  {ep.windowMin === ep.windowMax ? ep.windowMin : `${ep.windowMin}–${ep.windowMax}`}
                                </td>
                                <td className="px-6 py-3 font-mono text-xs">{ep.peakScore.toFixed(3)}</td>
                                <td className="px-6 py-3">
                                  <Badge tone={severityTone(ep.worstSeverity)}>{ep.worstSeverity}</Badge>
                                </td>
                                <td className="px-6 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                                  <div className="inline-flex gap-1">
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      onClick={() => setLabelForEpisode(ep, "confirmed")}
                                      title="Confirm all windows in this episode"
                                      aria-label="Confirm episode"
                                    >
                                      <Check className="h-3.5 w-3.5 text-success" />
                                    </Button>
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      onClick={() => setLabelForEpisode(ep, "false_positive")}
                                      title="Mark all windows in this episode as false positive"
                                      aria-label="Mark episode as false positive"
                                    >
                                      <X className="h-3.5 w-3.5 text-danger" />
                                    </Button>
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      onClick={() => setLabelForEpisode(ep, "unlabeled")}
                                      title="Reset all windows in this episode"
                                      aria-label="Reset episode"
                                    >
                                      <RotateCcw className="h-3.5 w-3.5 text-muted" />
                                    </Button>
                                  </div>
                                </td>
                              </tr>
                              {open && (
                                <tr key={`${ep.key}-detail`}>
                                  <td colSpan={6} className="bg-surface-2/40 px-6 py-3">
                                    <table className="w-full text-xs">
                                      <thead>
                                        <tr className="text-left text-muted">
                                          <th className="py-1.5 pr-4 font-medium">When</th>
                                          <th className="py-1.5 pr-4 font-medium">Window</th>
                                          <th className="py-1.5 pr-4 font-medium">Score</th>
                                          <th className="py-1.5 pr-4 font-medium">Label</th>
                                          <th className="py-1.5 text-right font-medium">Action</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {ep.events.map((a) => (
                                          <tr key={a.id} className="border-t border-border/40">
                                            <td className="py-2 pr-4 text-muted">
                                              {new Date(a.created_at).toLocaleString()}
                                            </td>
                                            <td className="py-2 pr-4 font-mono">{a.window_idx}</td>
                                            <td className="py-2 pr-4 font-mono">{a.score.toFixed(3)}</td>
                                            <td className="py-2 pr-4">
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
                                            <td className="py-2 text-right">
                                              <div className="inline-flex gap-1">
                                                <Button
                                                  variant="ghost"
                                                  size="sm"
                                                  onClick={() => setLabel(a.id, "confirmed")}
                                                  aria-label="Confirm anomaly"
                                                >
                                                  <Check className="h-3.5 w-3.5 text-success" />
                                                </Button>
                                                <Button
                                                  variant="ghost"
                                                  size="sm"
                                                  onClick={() => setLabel(a.id, "false_positive")}
                                                  aria-label="Mark as false positive"
                                                >
                                                  <X className="h-3.5 w-3.5 text-danger" />
                                                </Button>
                                                <Button
                                                  variant="ghost"
                                                  size="sm"
                                                  onClick={() => setLabel(a.id, "unlabeled")}
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
                                  </td>
                                </tr>
                              )}
                            </>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
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
