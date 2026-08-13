import { Card } from "@/components/Card";
import { ExperimentResult, PresetDemoResult } from "@/api/client";
import { pct, average } from "./helpers";

type Props = {
  result: ExperimentResult | PresetDemoResult;
};

export function CrossApplicationImpact({ result }: Props) {
  const globalEps = result.cross_application.global_epsilon ?? null;
  const entries = Object.entries(result.epsilons);

  const lowGroupFp = average(
    entries
      .filter(([, eps]) => eps < (globalEps ?? 0))
      .map(([name]) => result.cross_application.fp_rate_at_global[name] ?? null),
  );
  const highGroupMiss = average(
    entries
      .filter(([, eps]) => eps >= (globalEps ?? 0))
      .map(([name]) => result.cross_application.miss_rate_at_global[name] ?? null),
  );

  return (
    <Card>
      <h3 className="text-sm font-semibold text-text">Cross-application impact</h3>
      <p className="mt-1 text-xs text-muted">
        What happens if a single global threshold (the mean ε across the selected subjects, {globalEps?.toFixed(4)})
        were applied to everyone instead of each subject's own personalized ε.
      </p>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div className="rounded-xl bg-surface-2/60 p-4">
          <p className="text-xs text-muted">Subjects with a naturally lower threshold</p>
          <p className="mt-1 text-2xl font-semibold text-danger">{pct(lowGroupFp)}</p>
          <p className="mt-0.5 text-xs text-muted">average false-positive rate under the global threshold</p>
        </div>
        <div className="rounded-xl bg-surface-2/60 p-4">
          <p className="text-xs text-muted">Subjects with a naturally higher threshold</p>
          <p className="mt-1 text-2xl font-semibold text-danger">{pct(highGroupMiss)}</p>
          <p className="mt-0.5 text-xs text-muted">average missed-anomaly rate under the global threshold</p>
        </div>
      </div>
      <p className="mt-4 text-xs text-muted">
        Personalized thresholds eliminate both by construction — each subject is scored only against its own
        calibrated ε, never the population average.
      </p>

      <div className="mt-5 overflow-x-auto -mx-6">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase tracking-wider text-muted">
              <th className="px-6 py-2.5 font-medium">Subject</th>
              <th className="px-6 py-2.5 font-medium">Personal ε</th>
              <th className="px-6 py-2.5 font-medium">FP rate at global ε</th>
              <th className="px-6 py-2.5 font-medium">Miss rate at global ε</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([name, eps]) => (
              <tr key={name} className="border-b border-border/50 last:border-0">
                <td className="px-6 py-2.5 text-text">{name}</td>
                <td className="px-6 py-2.5 font-mono text-muted">{eps.toFixed(4)}</td>
                <td className="px-6 py-2.5 font-mono text-muted">{pct(result.cross_application.fp_rate_at_global[name] ?? null)}</td>
                <td className="px-6 py-2.5 font-mono text-muted">{pct(result.cross_application.miss_rate_at_global[name] ?? null)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
