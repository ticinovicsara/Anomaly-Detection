import { Badge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { CurvePoint } from "@/api/client";
import { OUTCOME_LABEL, Outcome } from "./helpers";

type ErrorRow = CurvePoint & { outcome: Outcome; margin: number };

export function WorstErrorsTable({ errors }: { errors: ErrorRow[] }) {
  return (
    <Card>
      <h3 className="text-sm font-semibold text-text">Largest misses (by distance from ε)</h3>
      <p className="mt-1 text-xs text-muted">
        Where the model disagreed with the label, sorted by how confidently wrong it was.
      </p>
      {errors.length === 0 ? (
        <p className="mt-3 text-sm text-muted">No misclassifications in the sampled curve - looks clean.</p>
      ) : (
        <div className="mt-4 overflow-x-auto -mx-6">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wider text-muted">
                <th className="px-6 py-2 font-medium">#</th>
                <th className="px-6 py-2 font-medium">Type</th>
                <th className="px-6 py-2 font-medium">Actual</th>
                <th className="px-6 py-2 font-medium">Predicted</th>
                <th className="px-6 py-2 font-medium">Score</th>
                <th className="px-6 py-2 font-medium">Margin vs ε</th>
              </tr>
            </thead>
            <tbody>
              {errors.map((e) => (
                <tr key={e.i} className="border-b border-border/50 last:border-0">
                  <td className="px-6 py-2 font-mono text-muted">{e.i}</td>
                  <td className="px-6 py-2">
                    <Badge tone={e.outcome === "fp" ? "warning" : "danger"}>{OUTCOME_LABEL[e.outcome]}</Badge>
                  </td>
                  <td className="px-6 py-2 text-text">{e.actual ? "anomaly" : "normal"}</td>
                  <td className="px-6 py-2 text-text">{e.predicted ? "anomaly" : "normal"}</td>
                  <td className="px-6 py-2 font-mono text-muted">{e.score.toFixed(4)}</td>
                  <td className="px-6 py-2 font-mono text-muted">
                    {e.margin >= 0 ? "+" : ""}
                    {e.margin.toFixed(4)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
