import { ChevronDown, History as HistoryIcon } from "lucide-react";
import { ThresholdHistoryEntry } from "@/api/client";
import { timeAgo } from "./helpers";

const SOURCE_LABEL: Record<string, string> = {
  trained: "First training",
  retrained: "Retrain (new data)",
  trained_alternative: "Alternative algorithm",
  z_updated: "z changed",
};

function deltaBadge(current: number, previous: number | null) {
  if (previous === null || previous === current) return null;
  const up = current > previous;
  const pct = previous !== 0 ? Math.abs(((current - previous) / previous) * 100) : null;
  return (
    <span className={`ml-1.5 font-mono text-[11px] ${up ? "text-warning" : "text-success"}`}>
      {up ? "▲" : "▼"} {pct !== null ? `${pct.toFixed(1)}%` : ""}
    </span>
  );
}

export function ThresholdHistoryPanel({
  history,
  expanded,
  onToggleExpanded,
}: {
  history: ThresholdHistoryEntry[];
  expanded: boolean;
  onToggleExpanded: () => void;
}) {
  if (history.length === 0) return null;

  return (
    <div className="mt-5 border-t border-border pt-4">
      <button
        onClick={onToggleExpanded}
        className="flex w-full items-center justify-between text-left text-xs font-semibold uppercase tracking-wider text-muted hover:text-text"
      >
        <span className="inline-flex items-center gap-1.5">
          <HistoryIcon className="h-3.5 w-3.5" /> History ({history.length})
        </span>
        <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`} />
      </button>
      <div
        className={`grid transition-[grid-template-rows] duration-200 ease-out ${
          expanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
      >
        <div className="overflow-hidden">
          <p className="mt-3 text-xs text-muted">
            Every calibration this subject has had - a z-multiplier edit, a retrain on new data, or an initial
            training - so you never have to write down the old ε yourself before changing it.
          </p>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-muted">
                  <th className="py-1.5 pr-3 font-medium">When</th>
                  <th className="py-1.5 pr-3 font-medium">Change</th>
                  <th className="py-1.5 pr-3 font-medium">ε</th>
                  <th className="py-1.5 pr-3 font-medium">z</th>
                  <th className="py-1.5 pr-3 font-medium">μ</th>
                  <th className="py-1.5 pr-3 font-medium">σ</th>
                  <th className="py-1.5 font-medium">Rows</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {history.map((h, i) => {
                  const previous = history[i + 1] ?? null;
                  return (
                    <tr key={h.id}>
                      <td className="py-1.5 pr-3 whitespace-nowrap text-muted" title={h.created_at}>
                        {timeAgo(h.created_at)}
                      </td>
                      <td className="py-1.5 pr-3 whitespace-nowrap text-text">
                        {SOURCE_LABEL[h.source] ?? h.source}
                      </td>
                      <td className="py-1.5 pr-3 whitespace-nowrap font-mono text-text">
                        {h.epsilon.toFixed(4)}
                        {previous && deltaBadge(h.epsilon, previous.epsilon)}
                      </td>
                      <td className="py-1.5 pr-3 whitespace-nowrap font-mono text-muted">{h.z_multiplier.toFixed(1)}</td>
                      <td className="py-1.5 pr-3 whitespace-nowrap font-mono text-muted">{h.mu.toFixed(4)}</td>
                      <td className="py-1.5 pr-3 whitespace-nowrap font-mono text-muted">{h.sigma.toFixed(4)}</td>
                      <td className="py-1.5 whitespace-nowrap font-mono text-muted">
                        {h.n_rows !== null ? h.n_rows.toLocaleString() : "-"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
