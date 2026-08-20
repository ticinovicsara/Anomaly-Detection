import { Link } from "react-router-dom";
import { Check, FlaskConical, Search, SlidersHorizontal, X } from "lucide-react";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { EmptyState } from "@/components/EmptyState";
import { Input } from "@/components/Input";
import { TableRowsSkeleton } from "@/components/Skeleton";
import { Subject } from "@/api/client";

type Algorithm = "all" | "IF" | "LSTM";

type Props = {
  loading: boolean;
  subjects: Subject[];
  filteredSubjects: Subject[];
  runnableCount: number;
  selected: Set<number>;
  onToggle: (id: number) => void;
  onSelectAll: (ids: number[]) => void;
  onSelectNone: () => void;
  onRun: () => void;
  running: boolean;
  search: string;
  onSearchChange: (v: string) => void;
  epsilonMin: string;
  onEpsilonMinChange: (v: string) => void;
  epsilonMax: string;
  onEpsilonMaxChange: (v: string) => void;
  algorithmFilter: Algorithm;
  onAlgorithmFilterChange: (v: Algorithm) => void;
};

export function SubjectSelector({
  loading,
  subjects,
  filteredSubjects,
  runnableCount,
  selected,
  onToggle,
  onSelectAll,
  onSelectNone,
  onRun,
  running,
  search,
  onSearchChange,
  epsilonMin,
  onEpsilonMinChange,
  epsilonMax,
  onEpsilonMaxChange,
  algorithmFilter,
  onAlgorithmFilterChange,
}: Props) {
  const hasActiveFilters = search.trim() !== "" || epsilonMin !== "" || epsilonMax !== "" || algorithmFilter !== "all";
  const clearFilters = () => {
    onSearchChange("");
    onEpsilonMinChange("");
    onEpsilonMaxChange("");
    onAlgorithmFilterChange("all");
  };

  return (
    <Card>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h3 className="text-sm font-semibold text-text">Select subjects to include</h3>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onSelectAll(filteredSubjects.map((s) => s.id))}
            disabled={subjects.length === 0}
            title={hasActiveFilters ? "Selects only the subjects currently shown by the filter" : undefined}
          >
            Select all
          </Button>
          <Button variant="ghost" size="sm" onClick={onSelectNone} disabled={selected.size === 0}>
            Select none
          </Button>
        </div>
      </div>

      {!loading && subjects.length > 0 && (
        <div className="mt-4 space-y-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <Input
              className="pl-9"
              placeholder="Search by name…"
              value={search}
              onChange={(e) => onSearchChange(e.target.value)}
            />
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted">ε above</label>
              <input
                type="number"
                step="0.0001"
                placeholder="min"
                value={epsilonMin}
                onChange={(e) => onEpsilonMinChange(e.target.value)}
                className="w-24 rounded-xl border border-border bg-surface-2 px-3 py-2 text-sm text-text placeholder:text-muted focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted">ε below</label>
              <input
                type="number"
                step="0.0001"
                placeholder="max"
                value={epsilonMax}
                onChange={(e) => onEpsilonMaxChange(e.target.value)}
                className="w-24 rounded-xl border border-border bg-surface-2 px-3 py-2 text-sm text-text placeholder:text-muted focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted">Model</label>
              <div className="flex gap-1.5">
                {(["all", "IF", "LSTM"] as const).map((a) => (
                  <button
                    key={a}
                    onClick={() => onAlgorithmFilterChange(a)}
                    className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                      algorithmFilter === a ? "border-accent bg-accent/10 text-accent" : "border-border text-muted hover:text-text"
                    }`}
                  >
                    {a === "all" ? "All" : a}
                  </button>
                ))}
              </div>
            </div>
            {hasActiveFilters && (
              <Button variant="ghost" size="sm" onClick={clearFilters} icon={<X className="h-3.5 w-3.5" />}>
                Clear filters
              </Button>
            )}
          </div>
          {hasActiveFilters && (
            <p className="text-xs text-muted">
              Showing {filteredSubjects.length} of {subjects.length} subjects · {runnableCount} selected within this filter
              will run
            </p>
          )}
        </div>
      )}

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
      ) : filteredSubjects.length === 0 ? (
        <div className="mt-4">
          <EmptyState icon={Search} title="No subjects match your filters" message="Try loosening the search or filters above." />
        </div>
      ) : (
        <ul className="mt-4 grid gap-2 sm:grid-cols-2">
          {filteredSubjects.map((s) => {
            const checked = selected.has(s.id);
            return (
              <li key={s.id} className="flex items-stretch gap-1.5">
                <button
                  onClick={() => onToggle(s.id)}
                  className="flex flex-1 min-w-0 items-center justify-between gap-3 rounded-xl border border-border bg-surface-2/50 px-3.5 py-2.5 text-left transition-colors duration-150 hover:border-accent/40"
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
                <Link
                  to={`/subjects/${s.id}`}
                  title="Edit this subject's threshold"
                  className="flex shrink-0 items-center justify-center rounded-xl border border-border bg-surface-2/50 px-2.5 text-muted transition-colors duration-150 hover:border-accent/40 hover:text-accent"
                >
                  <SlidersHorizontal className="h-3.5 w-3.5" />
                </Link>
              </li>
            );
          })}
        </ul>
      )}

      <div className="mt-5">
        <Button onClick={onRun} loading={running} disabled={runnableCount < 2} icon={<FlaskConical className="h-4 w-4" />}>
          Run experiment
        </Button>
        {runnableCount < 2 && subjects.length > 0 && (
          <p className="mt-2 text-xs text-muted">Select at least 2 subjects (within the current filter) to run the comparison.</p>
        )}
      </div>
    </Card>
  );
}
