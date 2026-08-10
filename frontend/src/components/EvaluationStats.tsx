import { Evaluation } from "@/api/client";

export function EvaluationStats({ evaluation }: { evaluation: Evaluation | null | undefined }) {
  if (!evaluation) {
    return <p className="text-xs text-muted">N/A — dataset has no labeled anomalies</p>;
  }
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      <Stat label="Precision" value={evaluation.precision} />
      <Stat label="Recall" value={evaluation.recall} />
      <Stat label="F1" value={evaluation.f1} />
      <Stat label="AU-ROC" value={evaluation.auc} />
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="rounded-lg border border-border bg-surface-2/50 px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-wider text-muted">{label}</p>
      <p className="mt-0.5 font-mono text-sm font-semibold text-text">{value !== null ? value.toFixed(3) : "-"}</p>
    </div>
  );
}
