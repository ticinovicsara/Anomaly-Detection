import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Brain, ChevronDown, FlaskConical, PlayCircle, Upload as UploadIcon } from "lucide-react";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Badge, statusTone } from "@/components/Badge";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { FullPageSpinner } from "@/components/Spinner";
import { useToast } from "@/components/Toast";
import { useAdvancedMode } from "@/hooks";
import {
  errorMessage,
  isCancelled,
  models as modelsApi,
  subjects as subjectsApi,
  ModelInfo,
  PredictResult,
  Subject,
} from "@/api/client";

export default function ModelsPage() {
  const { enabled: advancedMode } = useAdvancedMode();

  const [items, setItems] = useState<ModelInfo[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [loading, setLoading] = useState(true);
  const [predicting, setPredicting] = useState<number | null>(null);
  const [result, setResult] = useState<PredictResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [targetModel, setTargetModel] = useState<number | null>(null);
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());
  const toast = useToast();

  useEffect(() => {
    const controller = new AbortController();
    let intervalId: number | undefined;
    const isPending = (list: ModelInfo[]) =>
      list.some((m) => m.status === "training" || m.status === "pending");

    const poll = () => {
      modelsApi
        .list({ signal: controller.signal })
        .then((r) => {
          setItems(r.data);
          if (!isPending(r.data) && intervalId !== undefined) {
            clearInterval(intervalId);
            intervalId = undefined;
          }
        })
        .catch((err) => {
          if (!isCancelled(err)) throw err;
        });
    };

    Promise.all([modelsApi.list({ signal: controller.signal }), subjectsApi.list({ signal: controller.signal })])
      .then(([m, s]) => {
        setItems(m.data);
        setSubjects(s.data);
        if (isPending(m.data)) intervalId = window.setInterval(poll, 3000);
      })
      .catch((err) => {
        if (!isCancelled(err)) throw err;
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => {
      controller.abort();
      if (intervalId !== undefined) clearInterval(intervalId);
    };
  }, []);

  const runPredict = async (file: File) => {
    if (targetModel === null) return;
    setPredicting(targetModel);
    setResult(null);
    try {
      const r = await modelsApi.predict(targetModel, file);
      setResult(r.data);
      toast({
        tone: r.data.anomaly_count > 0 ? "warning" : "success",
        title: `${r.data.anomaly_count} anomalies detected`,
        message: `${r.data.total_windows} windows · rate ${(r.data.anomaly_rate * 100).toFixed(1)}%`,
      });
    } catch (err) {
      toast({ tone: "error", title: "Prediction failed", message: errorMessage(err) });
    } finally {
      setPredicting(null);
    }
  };

  const groups = useMemo(() => {
    const bySubject = new Map<number, ModelInfo[]>();
    for (const m of items) {
      const arr = bySubject.get(m.subject_id) ?? [];
      arr.push(m);
      bySubject.set(m.subject_id, arr);
    }
    return subjects
      .map((s) => {
        const all = bySubject.get(s.id) ?? [];
        const visible = advancedMode ? all : all.filter((m) => m.is_active).length > 0 ? all.filter((m) => m.is_active) : all.slice(0, 1);
        return { subject: s, models: visible };
      })
      .filter((g) => g.models.length > 0);
  }, [items, subjects, advancedMode]);

  const toggleCollapsed = (subjectId: number) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(subjectId)) next.delete(subjectId);
      else next.add(subjectId);
      return next;
    });
  };

  if (loading) return <FullPageSpinner />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Models"
        subtitle={
          <>
            Grouped by subject. Click <b>Predict</b> to run one on new data.
          </>
        }
      />

      {groups.length === 0 ? (
        <Card>
          <EmptyState
            icon={Brain}
            title="No models yet"
            message="Upload a CSV and start training to see your models here."
            action={
              <Link to="/upload">
                <Button size="sm" variant="secondary" icon={<UploadIcon className="h-3.5 w-3.5" />}>
                  Upload data
                </Button>
              </Link>
            }
          />
        </Card>
      ) : (
        <div className="space-y-4">
          {groups.map(({ subject, models }) => {
            const isCollapsed = collapsed.has(subject.id);
            return (
              <Card key={subject.id} className="p-0 overflow-hidden">
                <button
                  onClick={() => toggleCollapsed(subject.id)}
                  className="flex w-full items-center justify-between gap-3 px-6 py-4 text-left hover:bg-surface-2/40"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <ChevronDown
                      className={`h-4 w-4 shrink-0 text-muted transition-transform duration-200 ${isCollapsed ? "-rotate-90" : ""}`}
                    />
                    <Link
                      to={`/subjects/${subject.id}`}
                      onClick={(e) => e.stopPropagation()}
                      className="truncate text-sm font-semibold text-text hover:text-accent"
                    >
                      {subject.name}
                    </Link>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted shrink-0">
                    <span>{models.length} model{models.length === 1 ? "" : "s"}</span>
                    {subject.active_epsilon !== null && (
                      <span className="font-mono">ε = {subject.active_epsilon.toFixed(4)}</span>
                    )}
                  </div>
                </button>

                <div
                  className={`grid transition-[grid-template-rows] duration-200 ease-out ${
                    isCollapsed ? "grid-rows-[0fr]" : "grid-rows-[1fr]"
                  }`}
                >
                  <div className="overflow-hidden">
                    <ul className="divide-y divide-border border-t border-border">
                      {models.map((m) => (
                        <li key={m.id} className="flex flex-wrap items-center justify-between gap-3 px-6 py-3">
                          <div className="flex flex-wrap items-center gap-2 min-w-0">
                            <span className="text-sm text-text">Model #{m.id}</span>
                            <Badge tone="accent">{m.algorithm}</Badge>
                            <Badge tone={statusTone(m.status)}>{m.status}</Badge>
                            {advancedMode && (
                              <span className={`h-1.5 w-1.5 rounded-full ${m.is_active ? "bg-success" : "bg-border"}`} title={m.is_active ? "Active" : "Not active"} />
                            )}
                            {advancedMode && m.selection_mode === "manual" && <Badge>manual</Badge>}
                            {m.threshold && <span className="font-mono text-xs text-muted">ε={m.threshold.epsilon.toFixed(4)}</span>}
                            {m.metrics.evaluation && m.metrics.evaluation.f1 !== null && (
                              <span className="font-mono text-xs text-muted" title="F1 on held-out test set">
                                F1={m.metrics.evaluation.f1.toFixed(3)}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            {advancedMode && m.metrics.evaluation && (
                              <Link to={`/models/${m.id}/diagnostics`}>
                                <Button variant="ghost" size="sm" icon={<FlaskConical className="h-3.5 w-3.5" />}>
                                  Diagnostics
                                </Button>
                              </Link>
                            )}
                            <Button
                              variant="secondary"
                              size="sm"
                              disabled={m.status !== "ready"}
                              loading={predicting === m.id}
                              icon={<PlayCircle className="h-3.5 w-3.5" />}
                              onClick={() => {
                                setTargetModel(m.id);
                                fileInputRef.current?.click();
                              }}
                            >
                              Predict
                            </Button>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept=".csv"
        hidden
        onChange={(e) => e.target.files?.[0] && runPredict(e.target.files[0])}
      />

      {result && (
        <Card className="animate-fade-in">
          <div className="flex items-center gap-3 mb-4">
            <div className="rounded-xl bg-accent/10 p-2 text-accent">
              <UploadIcon className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold">Prediction result</p>
              <p className="text-xs text-muted">
                Model #{result.model_id} · algorithm {result.algorithm}
              </p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 [&>*]:h-full">
            <StatMini label="Windows" value={result.total_windows} />
            <StatMini label="Anomalies" value={result.anomaly_count} tone="warning" />
            <StatMini label="Rate" value={`${(result.anomaly_rate * 100).toFixed(1)}%`} />
            <StatMini label="Threshold" value={result.threshold.toFixed(3)} />
          </div>
        </Card>
      )}
    </div>
  );
}

function StatMini({ label, value, tone }: { label: string; value: string | number; tone?: "warning" }) {
  return (
    <div className="rounded-xl border border-border bg-surface-2/50 p-3">
      <p className="text-[10px] uppercase tracking-wider text-muted">{label}</p>
      <p
        className={`mt-1 font-mono text-lg font-semibold ${
          tone === "warning" ? "text-warning" : "text-text"
        }`}
      >
        {value}
      </p>
    </div>
  );
}
