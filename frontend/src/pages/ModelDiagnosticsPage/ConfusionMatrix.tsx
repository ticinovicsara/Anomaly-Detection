import { Card } from "@/components/Card";
import { Confusion } from "@/api/client";

export function ConfusionMatrix({ confusion }: { confusion: Confusion }) {
  const total = confusion.tp + confusion.fp + confusion.tn + confusion.fn;
  return (
    <Card>
      <h3 className="text-sm font-semibold text-text">Confusion matrix</h3>
      <div className="mt-4 grid grid-cols-2 gap-3 sm:max-w-md">
        <ConfusionCell label="True positive" value={confusion.tp} total={total} tone="success" />
        <ConfusionCell label="False positive" value={confusion.fp} total={total} tone="warning" />
        <ConfusionCell label="False negative (missed)" value={confusion.fn} total={total} tone="danger" />
        <ConfusionCell label="True negative" value={confusion.tn} total={total} tone="default" />
      </div>
    </Card>
  );
}

function ConfusionCell({
  label,
  value,
  total,
  tone,
}: {
  label: string;
  value: number;
  total: number;
  tone: "success" | "warning" | "danger" | "default";
}) {
  const pct = total > 0 ? ((value / total) * 100).toFixed(1) : "0.0";
  const toneClasses = {
    success: "border-success/30 bg-success/5",
    warning: "border-warning/30 bg-warning/5",
    danger: "border-danger/30 bg-danger/5",
    default: "border-border bg-surface-2/50",
  }[tone];
  return (
    <div className={`rounded-xl border p-3 ${toneClasses}`}>
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 font-mono text-xl font-semibold text-text">{value}</p>
      <p className="text-[11px] text-muted">{pct}% of test set</p>
    </div>
  );
}
