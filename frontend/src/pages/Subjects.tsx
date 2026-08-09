import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Heart, CreditCard, Server, Circle, Plus, FlaskConical, ArrowRight } from "lucide-react";
import { LucideIcon } from "lucide-react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { Input } from "../components/Input";
import { Modal } from "../components/Modal";
import { StaggerGroup, StaggerItem } from "../components/Stagger";
import { TableRowsSkeleton } from "../components/Skeleton";
import { useToast } from "../components/Toast";
import { errorMessage, isCancelled, subjects as subjectsApi, Subject } from "../api/client";

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

export default function Subjects() {
  const [items, setItems] = useState<Subject[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const toast = useToast();
  const nav = useNavigate();

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
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Subjects</h1>
          <p className="mt-1 text-sm text-muted">
            The entities you track — a patient, a card, a service. Each gets its own personalized threshold.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/experiments">
            <Button variant="secondary" icon={<FlaskConical className="h-4 w-4" />}>
              Personalization experiment
            </Button>
          </Link>
          <Button onClick={() => setCreateOpen(true)} icon={<Plus className="h-4 w-4" />}>
            New subject
          </Button>
        </div>
      </div>

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
      ) : (
        <StaggerGroup className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((s) => {
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

                    <p className="mt-4 font-mono text-lg font-semibold text-text">
                      {s.active_epsilon !== null ? `ε = ${s.active_epsilon.toFixed(4)}` : "Not trained yet"}
                    </p>

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
