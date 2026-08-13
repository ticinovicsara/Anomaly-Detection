import { Check, FlaskConical } from "lucide-react";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { EmptyState } from "@/components/EmptyState";
import { TableRowsSkeleton } from "@/components/Skeleton";
import { Subject } from "@/api/client";

type Props = {
  loading: boolean;
  subjects: Subject[];
  selected: Set<number>;
  onToggle: (id: number) => void;
  onSelectAll: () => void;
  onSelectNone: () => void;
  onRun: () => void;
  running: boolean;
};

export function SubjectSelector({
  loading,
  subjects,
  selected,
  onToggle,
  onSelectAll,
  onSelectNone,
  onRun,
  running,
}: Props) {
  return (
    <Card>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h3 className="text-sm font-semibold text-text">Select subjects to include</h3>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={onSelectAll} disabled={subjects.length === 0}>
            Select all
          </Button>
          <Button variant="ghost" size="sm" onClick={onSelectNone} disabled={selected.size === 0}>
            Select none
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="mt-4">
          <TableRowsSkeleton rows={3} />
        </div>
      ) : subjects.length === 0 ? (
        <EmptyState
          icon={FlaskConical}
          title="No trained subjects yet"
          message="Train at least two subjects to compare their thresholds, or try the preset demo below."
        />
      ) : (
        <ul className="mt-4 grid gap-2 sm:grid-cols-2">
          {subjects.map((s) => {
            const checked = selected.has(s.id);
            return (
              <li key={s.id}>
                <button
                  onClick={() => onToggle(s.id)}
                  className="flex w-full items-center justify-between gap-3 rounded-xl border border-border bg-surface-2/50 px-3.5 py-2.5 text-left transition-colors duration-150 hover:border-accent/40"
                >
                  <span className="flex items-center gap-2.5 min-w-0">
                    <span
                      className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-md border transition-colors duration-150 ${
                        checked ? "border-accent bg-accent text-white" : "border-border bg-surface"
                      }`}
                    >
                      {checked && <Check className="h-3 w-3" strokeWidth={3} />}
                    </span>
                    <span className="truncate text-sm text-text">{s.name}</span>
                  </span>
                  <span className="shrink-0 font-mono text-xs text-muted">ε = {s.active_epsilon!.toFixed(4)}</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <div className="mt-5">
        <Button onClick={onRun} loading={running} disabled={selected.size < 2} icon={<FlaskConical className="h-4 w-4" />}>
          Run experiment
        </Button>
        {selected.size < 2 && subjects.length > 0 && (
          <p className="mt-2 text-xs text-muted">Select at least 2 subjects to run the comparison.</p>
        )}
      </div>
    </Card>
  );
}
