import { useEffect, useMemo, useState } from "react";
import { ChevronDown, FlaskConical } from "lucide-react";
import { Card } from "@/components/Card";
import { Spinner } from "@/components/Spinner";
import {
  models as predictApi,
  PredictBatchDetail,
  PredictBatchSummary,
} from "@/api/client";
import { ConfusionMatrix } from "./ConfusionMatrix";
import { PredictedVsActualChart } from "./PredictedVsActualChart";
import { outcomeOf } from "./helpers";

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function LabeledPredictRuns({
  modelId,
  epsilon,
}: {
  modelId: number;
  epsilon: number | null | undefined;
}) {
  const [batches, setBatches] = useState<PredictBatchSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [detail, setDetail] = useState<PredictBatchDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    predictApi
      .labeledBatches(modelId, { signal: controller.signal })
      .then((r) => setBatches(r.data))
      .catch(() => {})
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [modelId]);

  const toggle = (batchId: string) => {
    if (expanded === batchId) {
      setExpanded(null);
      setDetail(null);
      return;
    }
    setExpanded(batchId);
    setDetail(null);
    setDetailLoading(true);
    predictApi
      .labeledBatchDetail(modelId, batchId)
      .then((r) => setDetail(r.data))
      .catch(() => {})
      .finally(() => setDetailLoading(false));
  };

  const chartData = useMemo(() => {
    if (!detail) return [];
    return detail.curve.map((p) => ({ ...p, outcome: outcomeOf(p) }));
  }, [detail]);

  if (loading || batches.length === 0) return null;

  return (
    <Card className="p-0 overflow-hidden">
      <div className="px-6 py-4">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-text">
          <FlaskConical className="h-4 w-4 text-accent" /> Labeled test runs
          from Predict
        </h3>
        <p className="mt-1 text-xs text-muted">
          Every time you run Predict with a CSV that includes a{" "}
          <code>label</code> column, the result appears here - this is separate
          from the training-time evaluation above.
        </p>
      </div>
      <ul className="divide-y divide-border border-t border-border">
        {batches.map((b) => {
          const isOpen = expanded === b.batch_id;
          const c = b.confusion;
          return (
            <li key={b.batch_id}>
              <button
                onClick={() => toggle(b.batch_id)}
                className="flex w-full items-center justify-between gap-3 px-6 py-3 text-left hover:bg-surface-2/40"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <ChevronDown
                    className={`h-3.5 w-3.5 shrink-0 text-muted transition-transform duration-200 ${isOpen ? "" : "-rotate-90"}`}
                  />
                  <span className="text-sm text-text">
                    {timeAgo(b.created_at)}
                  </span>
                  <span className="text-xs text-muted">
                    {b.n_windows.toLocaleString()} windows
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs shrink-0">
                  <span className="text-success">{c.tp} correct</span>
                  <span className="text-warning">{c.fp} false alarm</span>
                  <span className="text-danger">{c.fn} missed</span>
                </div>
              </button>
              {isOpen && (
                <div className="border-t border-border bg-surface-2/20 p-4 space-y-4">
                  {detailLoading ? (
                    <div className="flex items-center gap-2 py-6 justify-center text-sm text-muted">
                      <Spinner className="h-4 w-4" /> Loading…
                    </div>
                  ) : detail ? (
                    <>
                      <ConfusionMatrix confusion={detail.confusion} />
                      <PredictedVsActualChart
                        data={chartData}
                        epsilon={epsilon}
                      />
                    </>
                  ) : (
                    <p className="text-sm text-muted">
                      Could not load this run.
                    </p>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
