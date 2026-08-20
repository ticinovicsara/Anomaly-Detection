import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Heart, CreditCard, Server, Circle, Plus, FlaskConical, ArrowRight, Search, X } from "lucide-react";
import { LucideIcon } from "lucide-react";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { EmptyState } from "@/components/EmptyState";
import { Input } from "@/components/Input";
import { Modal } from "@/components/Modal";
import { PageHeader } from "@/components/PageHeader";
import { StaggerGroup, StaggerItem } from "@/components/Stagger";
import { TableRowsSkeleton } from "@/components/Skeleton";
import { useToast } from "@/components/Toast";
import { errorMessage, isCancelled, experiments as experimentsApi, subjects as subjectsApi, EvaluationSummary, Subject } from "@/api/client";

type Domain = "biomedical" | "financial" | "infrastructure" | "unknown";

function inferDomain(subject: Subject): Domain {
  const text = `${subject.name} ${subject.description ?? ""} ${subject.source_hint ?? ""}`.toLowerCase();
  if (/patient|ecg|heart|cardiac|biomedical|mit-bih|arrhythmia/.test(text)) return "biomedical";
  if (/card|bank|transaction|financial|credit|fraud/.test(text)) return "financial";
  if (/server|cpu|infra|metric|service|network|aws|cloud/.test(text)) return "infrastructure";
  return "unknown";
}

const DOMAIN_ICON: Record<Domain, LucideIcon> = {
  biomedical: Heart,
  financial: CreditCard,
  infrastructure: Server,
  unknown: Circle,
};

export default function SubjectsPage() {
  const [items, setItems] = useState<Subject[]>([]);
  const [evalSummary, setEvalSummary] = useState<EvaluationSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const toast = useToast();
  const nav = useNavigate();

  const [search, setSearch] = useState("");
  const [epsilonMin, setEpsilonMin] = useState("");
  const [epsilonMax, setEpsilonMax] = useState("");
  const [algorithmFilter, setAlgorithmFilter] = useState<"all" | "IF" | "LSTM">("all");
  const [minDatasets, setMinDatasets] = useState("");

  const hasActiveFilters =
    search.trim() !== "" || epsilonMin !== "" || epsilonMax !== "" || algorithmFilter !== "all" || minDatasets !== "";

  const clearFilters = () => {
    setSearch("");
    setEpsilonMin("");
    setEpsilonMax("");
    setAlgorithmFilter("all");
    setMinDatasets("");
  };

  const filteredItems = useMemo(() => {
    const q = search.trim().toLowerCase();
    const min = epsilonMin === "" ? null : Number(epsilonMin);
    const max = epsilonMax === "" ? null : Number(epsilonMax);
    const minDs = minDatasets === "" ? null : Number(minDatasets);
    return items.filter((s) => {
      if (q && !(s.name.toLowerCase().includes(q) || (s.description ?? "").toLowerCase().includes(q))) return false;
      if (min !== null && (s.active_epsilon === null || s.active_epsilon < min)) return false;
      if (max !== null && (s.active_epsilon === null || s.active_epsilon > max)) return false;
      if (algorithmFilter !== "all" && s.active_algorithm !== algorithmFilter) return false;
      if (minDs !== null && s.n_datasets < minDs) return false;
      return true;
    });
  }, [items, search, epsilonMin, epsilonMax, algorithmFilter, minDatasets]);

  useEffect(() => {
    const controller = new AbortController();
    subjectsApi
      .list({ signal: controller.signal })
      .then((r) => setItems(r.data))
      .catch((err) => {
        if (!isCancelled(err)) throw err;
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    // Additive summary -- failure here shouldn't block the grid from rendering.
    experimentsApi
      .evaluationSummary({ signal: controller.signal })
      .then((r) => setEvalSummary(r.data))
      .catch(() => {});
    return () => controller.abort();
  }, []);

  const createSubject = async () => {
    if (!name.trim()) return;
    setCreating(true);
    try {
      const r = await subjectsApi.create(name.trim(), description.trim() || undefined);
      setCreateOpen(false);
      setName("");
      setDescription("");
      nav(`/subjects/${r.data.id}`);
    } catch (err) {
      toast({ tone: "error", title: "Could not create subject", message: errorMessage(err) });
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Subjects"
        subtitle="The entities you track — a patient, a card, a service. Each gets its own personalized threshold."
        action={
          <>
            <Link to="/experiments">
              <Button variant="secondary" icon={<FlaskConical className="h-4 w-4" />}>
                Personalization experiment
              </Button>
            </Link>
            <Button onClick={() => setCreateOpen(true)} icon={<Plus className="h-4 w-4" />}>
              New subject
            </Button>
          </>
        }
      />

      {evalSummary && evalSummary.n_labeled_subjects > 0 && evalSummary.f1_statistics && (
        <Card>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">
            Across your {evalSummary.n_labeled_subjects} labeled subject{evalSummary.n_labeled_subjects === 1 ? "" : "s"}
          </p>
          <div className="mt-3 flex flex-wrap items-baseline gap-x-6 gap-y-1">
            <span className="font-mono text-2xl font-semibold text-accent">
              F1 {(evalSummary.f1_statistics.mean * 100).toFixed(0)}% avg
            </span>
            <span className="font-mono text-sm text-muted">
              range {(evalSummary.f1_statistics.min * 100).toFixed(0)}%–{(evalSummary.f1_statistics.max * 100).toFixed(0)}%
            </span>
            {evalSummary.auc_statistics && (
              <span className="font-mono text-sm text-muted">
                AU-ROC avg {evalSummary.auc_statistics.mean.toFixed(3)}
              </span>
            )}
            {evalSummary.n_unlabeled_subjects > 0 && (
              <span className="text-xs text-muted">
                ({evalSummary.n_unlabeled_subjects} subject{evalSummary.n_unlabeled_subjects === 1 ? "" : "s"} without
                labeled data, not included)
              </span>
            )}
          </div>
          <p className="mt-2 text-xs text-muted">
            This is a summary only — each subject keeps its own accuracy shown individually below.
          </p>
        </Card>
      )}

      {!loading && items.length > 0 && (
        <Card>
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <Input
              className="pl-9"
              placeholder="Search by name or description…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="mt-3 flex flex-wrap items-end gap-3">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted">ε above</label>
              <input
                type="number"
                step="0.0001"
                placeholder="min"
                value={epsilonMin}
                onChange={(e) => setEpsilonMin(e.target.value)}
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
                onChange={(e) => setEpsilonMax(e.target.value)}
                className="w-24 rounded-xl border border-border bg-surface-2 px-3 py-2 text-sm text-text placeholder:text-muted focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted">Min datasets</label>
              <input
                type="number"
                min={0}
                step="1"
                placeholder="e.g. 2"
                value={minDatasets}
                onChange={(e) => setMinDatasets(e.target.value)}
                className="w-24 rounded-xl border border-border bg-surface-2 px-3 py-2 text-sm text-text placeholder:text-muted focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted">Model</label>
              <div className="flex gap-1.5">
                {(["all", "IF", "LSTM"] as const).map((a) => (
                  <button
                    key={a}
                    onClick={() => setAlgorithmFilter(a)}
                    className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                      algorithmFilter === a
                        ? "border-accent bg-accent/10 text-accent"
                        : "border-border text-muted hover:text-text"
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
            <p className="mt-3 text-xs text-muted">
              Showing {filteredItems.length} of {items.length} subject{items.length === 1 ? "" : "s"}
            </p>
          )}
        </Card>
      )}

      {loading ? (
        <Card className="p-0">
          <TableRowsSkeleton rows={4} />
        </Card>
      ) : items.length === 0 ? (
        <Card>
          <EmptyState
            icon={Circle}
            title="No subjects yet"
            message="Upload data to get started — each upload becomes (or joins) a subject."
            action={
              <Link to="/upload">
                <Button size="sm" icon={<Plus className="h-3.5 w-3.5" />}>
                  Upload data
                </Button>
              </Link>
            }
          />
        </Card>
      ) : filteredItems.length === 0 ? (
        <Card>
          <EmptyState
            icon={Search}
            title="No subjects match your filters"
            message="Try loosening the search or filters above."
            action={
              <Button size="sm" variant="secondary" onClick={clearFilters}>
                Clear filters
              </Button>
            }
          />
        </Card>
      ) : (
        <StaggerGroup className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredItems.map((s) => {
            const Icon = DOMAIN_ICON[inferDomain(s)];
            return (
              <StaggerItem key={s.id}>
                <Link to={`/subjects/${s.id}`}>
                  <Card hoverable className="h-full">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-text">{s.name}</p>
                        {s.description && <p className="mt-0.5 truncate text-xs text-muted">{s.description}</p>}
                      </div>
                      <div className="rounded-xl bg-surface-2 p-2 text-accent shrink-0">
                        <Icon className="h-4 w-4" />
                      </div>
                    </div>

                    <div className="mt-4 flex items-center gap-3 flex-wrap">
                      <p className="font-mono text-lg font-semibold text-text">
                        {s.active_epsilon !== null ? `ε = ${s.active_epsilon.toFixed(4)}` : "Not trained yet"}
                      </p>
                      {s.active_f1 != null && (
                        <span
                          className="rounded-full border border-success/20 bg-success/10 px-2 py-0.5 font-mono text-xs font-medium text-success"
                          title={
                            s.active_auc != null
                              ? `F1 ${(s.active_f1 * 100).toFixed(0)}% · AU-ROC ${s.active_auc.toFixed(3)} on held-out test set`
                              : `F1 ${(s.active_f1 * 100).toFixed(0)}% on held-out test set`
                          }
                        >
                          F1 {(s.active_f1 * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>

                    <div className="mt-4 flex items-center gap-4 text-xs text-muted">
                      <span>
                        {s.n_datasets} dataset{s.n_datasets === 1 ? "" : "s"}
                      </span>
                      <span>
                        {s.n_models} model{s.n_models === 1 ? "" : "s"}
                      </span>
                      <span>
                        {s.n_anomalies} anomal{s.n_anomalies === 1 ? "y" : "ies"}
                      </span>
                    </div>

                    <div className="mt-4 flex items-center gap-1 text-xs font-medium text-accent">
                      View <ArrowRight className="h-3 w-3" />
                    </div>
                  </Card>
                </Link>
              </StaggerItem>
            );
          })}
        </StaggerGroup>
      )}

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="New subject">
        <div className="space-y-3">
          <Input label="Name" placeholder="e.g. Patient 101" value={name} onChange={(e) => setName(e.target.value)} />
          <Input
            label="Description (optional)"
            placeholder="24 y/o male, sinus arrhythmia"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={createSubject} loading={creating} disabled={!name.trim()}>
              Create
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
