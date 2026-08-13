import { Check, ShieldAlert, X } from "lucide-react";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { DataReviewCandidate } from "@/api/client";

type Props = {
  candidates: DataReviewCandidate[];
  labelingCandidateId: number | null;
  retraining: boolean;
  onLabel: (candidateId: number, label: "confirmed" | "false_positive") => void;
  onRetrain: () => void;
  onRetrainForce: () => void;
};

export function PendingReviewCard({
  candidates,
  labelingCandidateId,
  retraining,
  onLabel,
  onRetrain,
  onRetrainForce,
}: Props) {
  return (
    <div className="mt-4 rounded-xl border border-warning/30 bg-warning/5 p-4">
      <div className="flex items-start gap-2">
        <ShieldAlert className="h-4 w-4 shrink-0 text-warning mt-0.5" />
        <div>
          <p className="text-sm font-medium text-text">
            {candidates.length} row{candidates.length === 1 ? "" : "s"} in the newest data look potentially anomalous
          </p>
          <p className="mt-0.5 text-xs text-muted">
            Flagged by a quick unsupervised scan, not the trained model -- just a heads-up before this
            data feeds a retrain. Confirm/dismiss what you can, or skip straight to retraining.
          </p>
        </div>
      </div>
      <ul className="mt-3 divide-y divide-border/60">
        {candidates.map((c) => (
          <li key={c.id} className="flex items-center justify-between gap-3 py-2 text-xs">
            <div className="min-w-0">
              <span className="font-mono text-muted">row {c.row_index}</span>{" "}
              <span className="font-mono text-muted">score {c.score.toFixed(3)}</span>{" "}
              <span className="text-muted">
                {Object.entries(c.row_preview)
                  .slice(0, 3)
                  .map(([k, v]) => `${k}=${v.toFixed(2)}`)
                  .join(", ")}
              </span>
            </div>
            {c.label === "unlabeled" ? (
              <div className="flex shrink-0 gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  loading={labelingCandidateId === c.id}
                  onClick={() => onLabel(c.id, "confirmed")}
                  title="Yes, this is anomalous"
                  aria-label="Confirm as anomalous"
                >
                  <Check className="h-3.5 w-3.5 text-danger" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  loading={labelingCandidateId === c.id}
                  onClick={() => onLabel(c.id, "false_positive")}
                  title="No, this is normal"
                  aria-label="Dismiss as normal"
                >
                  <X className="h-3.5 w-3.5 text-success" />
                </Button>
              </div>
            ) : (
              <Badge tone={c.label === "confirmed" ? "danger" : "success"}>
                {c.label === "confirmed" ? "anomalous" : "normal"}
              </Badge>
            )}
          </li>
        ))}
      </ul>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" onClick={onRetrain} loading={retraining}>
          Retrain now
        </Button>
        <Button variant="secondary" size="sm" onClick={onRetrainForce} loading={retraining}>
          Skip review &amp; retrain anyway
        </Button>
      </div>
    </div>
  );
}
