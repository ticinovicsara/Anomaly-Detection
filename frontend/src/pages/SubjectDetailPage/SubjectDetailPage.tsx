import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, FlaskConical, Pencil, Plus, RotateCcw, Trash2 } from "lucide-react";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Badge, statusTone } from "@/components/Badge";
import { EmptyState } from "@/components/EmptyState";
import { EvaluationStats } from "@/components/EvaluationStats";
import { Input } from "@/components/Input";
import { Modal } from "@/components/Modal";
import { Slider } from "@/components/Slider";
import { TableRowsSkeleton } from "@/components/Skeleton";
import { useToast } from "@/components/Toast";
import { useAdvancedMode } from "@/hooks";
import {
  dataReview as dataReviewApi,
  errorMessage,
  isCancelled,
  reviewRequired,
  subjects as subjectsApi,
  thresholds,
  DataReviewCandidate,
  SubjectDetail as SubjectDetailType,
} from "@/api/client";
import { AdvancedModelsPanel } from "./AdvancedModelsPanel";
import { PendingReviewCard } from "./PendingReviewCard";
import { timeAgo } from "./helpers";

export default function SubjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const subjectId = Number(id);
  const nav = useNavigate();
  const toast = useToast();
  const { enabled: advancedMode } = useAdvancedMode();

  const [subject, setSubject] = useState<SubjectDetailType | null>(null);
  const [loading, setLoading] = useState(true);

  const [editOpen, setEditOpen] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [saving, setSaving] = useState(false);

  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const [retraining, setRetraining] = useState(false);
  const [zValue, setZValue] = useState(3);
  const [savingThreshold, setSavingThreshold] = useState(false);

  const [savingReviewToggle, setSavingReviewToggle] = useState(false);
  const [pendingCandidates, setPendingCandidates] = useState<DataReviewCandidate[] | null>(null);
  const [labelingCandidateId, setLabelingCandidateId] = useState<number | null>(null);

  const [advancedExpanded, setAdvancedExpanded] = useState(false);
  const [trainingAlt, setTrainingAlt] = useState<"IF" | "LSTM" | null>(null);
  const [activatingModelId, setActivatingModelId] = useState<number | null>(null);

  const fetchDetail = async (signal?: AbortSignal) => {
    const r = await subjectsApi.detail(subjectId, { signal });
    setSubject(r.data);
    const active = r.data.models.find((m) => m.is_active);
    setZValue(active?.threshold ? active.threshold.z_multiplier : 3);
    return r.data;
  };

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchDetail(controller.signal)
      .catch((err) => {
        if (!isCancelled(err)) throw err;
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [subjectId]);

  const refresh = () => fetchDetail().catch(() => {});

  if (loading) {
    return (
      <div className="space-y-6">
        <Card className="p-0">
          <TableRowsSkeleton rows={6} />
        </Card>
      </div>
    );
  }

  if (!subject) {
    return (
      <Card>
        <EmptyState
          icon={ArrowLeft}
          title="Subject not found"
          message="It may have been deleted."
          action={
            <Link to="/subjects">
              <Button size="sm">Back to subjects</Button>
            </Link>
          }
        />
      </Card>
    );
  }

  const activeModel = subject.models.find((m) => m.is_active) ?? null;

  const openEdit = () => {
    setEditName(subject.name);
    setEditDescription(subject.description ?? "");
    setEditOpen(true);
  };

  const saveEdit = async () => {
    if (!editName.trim()) return;
    setSaving(true);
    try {
      await subjectsApi.update(subject.id, { name: editName.trim(), description: editDescription.trim() || undefined });
      setEditOpen(false);
      await refresh();
    } catch (err) {
      toast({ tone: "error", title: "Could not save", message: errorMessage(err) });
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    setDeleting(true);
    try {
      await subjectsApi.delete(subject.id);
      toast({ tone: "success", title: "Subject deleted" });
      nav("/subjects");
    } catch (err) {
      toast({ tone: "error", title: "Could not delete", message: errorMessage(err) });
      setDeleting(false);
    }
  };

  const retrain = async (force = false) => {
    setRetraining(true);
    try {
      const r = await subjectsApi.retrain(subject.id, force);
      setPendingCandidates(null);
      const delta = r.data.delta_pct;
      toast({
        tone: "success",
        title: "Retrained with latest data",
        message:
          delta !== null
            ? `ε ${delta >= 0 ? "increased" : "decreased"} ${Math.abs(delta).toFixed(1)}% (${r.data.old_epsilon?.toFixed(4)} → ${r.data.new_epsilon.toFixed(4)})`
            : `ε = ${r.data.new_epsilon.toFixed(4)}`,
      });
      await refresh();
    } catch (err) {
      const blocked = reviewRequired(err);
      if (blocked) {
        setPendingCandidates(blocked.pending_candidates);
        toast({ tone: "warning", title: "Review needed before retraining", message: blocked.message });
      } else {
        toast({ tone: "error", title: "Retrain failed", message: errorMessage(err) });
      }
    } finally {
      setRetraining(false);
    }
  };

  const togglePreRetrainCheck = async () => {
    if (!subject) return;
    setSavingReviewToggle(true);
    try {
      await subjectsApi.update(subject.id, { pre_retrain_check_enabled: !subject.pre_retrain_check_enabled });
      await refresh();
    } catch (err) {
      toast({ tone: "error", title: "Could not update setting", message: errorMessage(err) });
    } finally {
      setSavingReviewToggle(false);
    }
  };

  const labelCandidate = async (candidateId: number, label: "confirmed" | "false_positive") => {
    if (!subject || !pendingCandidates) return;
    setLabelingCandidateId(candidateId);
    const previous = pendingCandidates;
    setPendingCandidates(pendingCandidates.map((c) => (c.id === candidateId ? { ...c, label } : c)));
    try {
      await dataReviewApi.label(subject.id, candidateId, label);
    } catch (err) {
      setPendingCandidates(previous);
      toast({ tone: "error", title: "Could not update", message: errorMessage(err) });
    } finally {
      setLabelingCandidateId(null);
    }
  };

  const saveThreshold = async () => {
    if (!activeModel) return;
    setSavingThreshold(true);
    try {
      const r = await thresholds.update(activeModel.id, zValue);
      toast({ tone: "success", title: "Threshold saved", message: `ε = ${r.data.epsilon.toFixed(4)}` });
      await refresh();
    } catch (err) {
      toast({ tone: "error", title: "Could not save threshold", message: errorMessage(err) });
    } finally {
      setSavingThreshold(false);
    }
  };

  const trainAlternative = async (algorithm: "IF" | "LSTM") => {
    setTrainingAlt(algorithm);
    try {
      const r = await subjectsApi.trainAlternative(subject.id, algorithm);
      toast({ tone: "success", title: `${algorithm} trained`, message: `ε = ${r.data.epsilon.toFixed(4)} (not activated)` });
      await refresh();
    } catch (err) {
      toast({ tone: "error", title: "Training failed", message: errorMessage(err) });
    } finally {
      setTrainingAlt(null);
    }
  };

  const activateModel = async (modelId: number) => {
    setActivatingModelId(modelId);
    try {
      await subjectsApi.activateModel(subject.id, modelId);
      toast({ tone: "success", title: `Model #${modelId} is now active` });
      await refresh();
    } catch (err) {
      toast({ tone: "error", title: "Could not activate model", message: errorMessage(err) });
    } finally {
      setActivatingModelId(null);
    }
  };

  const previewEpsilon = activeModel?.threshold ? activeModel.threshold.mu + zValue * activeModel.threshold.sigma : null;

  return (
    <div className="space-y-6">
      <Link to="/subjects" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-text">
        <ArrowLeft className="h-4 w-4" /> Back to subjects
      </Link>

      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{subject.name}</h1>
          {subject.description && <p className="mt-1 text-sm text-muted">{subject.description}</p>}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={openEdit} icon={<Pencil className="h-3.5 w-3.5" />}>
            Edit
          </Button>
          <Button variant="danger" size="sm" onClick={() => setDeleteOpen(true)} icon={<Trash2 className="h-3.5 w-3.5" />}>
            Delete
          </Button>
        </div>
      </div>

      {/* Threshold */}
      <Card>
        <h3 className="text-sm font-semibold text-text">Personalized threshold</h3>
        {!activeModel || !activeModel.threshold ? (
          <p className="mt-3 text-sm text-muted">No trained model yet — upload data or train to calibrate a threshold.</p>
        ) : (
          <>
            <div className="mt-3 flex flex-wrap items-baseline gap-x-6 gap-y-1">
              <span className="font-mono text-2xl font-semibold text-accent">ε = {activeModel.threshold.epsilon.toFixed(4)}</span>
              <span className="font-mono text-sm text-muted">μ = {activeModel.threshold.mu.toFixed(4)}</span>
              <span className="font-mono text-sm text-muted">σ = {activeModel.threshold.sigma.toFixed(4)}</span>
            </div>
            <div className="mt-5">
              <Slider label="z-multiplier" min={1} max={6} step={0.1} value={zValue} onChange={(e) => setZValue(parseFloat(e.target.value))} formatter={(v) => `z = ${v.toFixed(1)}`} />
            </div>
            <div className="mt-4 flex items-center justify-between rounded-xl bg-surface-2/60 p-3">
              <div className="text-xs text-muted">
                <p>Preview at z = {zValue.toFixed(1)}</p>
                <p className="mt-0.5 font-mono text-sm text-text">{previewEpsilon !== null ? previewEpsilon.toFixed(4) : "-"}</p>
              </div>
              <Button size="sm" onClick={saveThreshold} loading={savingThreshold} disabled={zValue === activeModel.threshold.z_multiplier}>
                Save threshold
              </Button>
            </div>
          </>
        )}
      </Card>

      {/* Datasets */}
      <Card>
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-text">Datasets ({subject.datasets.length})</h3>
          <Link to="/upload">
            <Button variant="secondary" size="sm" icon={<Plus className="h-3.5 w-3.5" />}>
              Add data
            </Button>
          </Link>
        </div>
        {subject.datasets.length === 0 ? (
          <p className="mt-3 text-sm text-muted">No datasets uploaded yet.</p>
        ) : (
          <ul className="mt-3 divide-y divide-border">
            {subject.datasets.map((d) => (
              <li key={d.id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                <span className="min-w-0 truncate text-text">{d.name}</span>
                <span className="shrink-0 font-mono text-xs text-muted">
                  {d.n_rows?.toLocaleString() ?? "-"} rows · {new Date(d.uploaded_at).toLocaleDateString()}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* Model */}
      <Card>
        <h3 className="text-sm font-semibold text-text">Model</h3>
        {!activeModel ? (
          <p className="mt-3 text-sm text-muted">Not trained yet.</p>
        ) : (
          <>
            <div className="mt-3 flex items-center gap-2">
              <Badge tone="accent">{activeModel.algorithm}</Badge>
              <Badge tone={statusTone(activeModel.status)}>{activeModel.status}</Badge>
              {activeModel.trained_at && <span className="text-xs text-muted">Trained {timeAgo(activeModel.trained_at)}</span>}
            </div>
            {activeModel.selection_reason && (
              <p className="mt-2 text-xs text-muted">
                {activeModel.selection_mode === "auto" ? "Selected automatically because: " : ""}
                &quot;{activeModel.selection_reason}&quot;
              </p>
            )}
            <div className="mt-4">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted">
                  Evaluation on held-out test set
                </p>
                {advancedMode && activeModel.evaluation && (
                  <Link
                    to={`/models/${activeModel.id}/diagnostics`}
                    className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
                  >
                    <FlaskConical className="h-3 w-3" /> Full diagnostics
                  </Link>
                )}
              </div>
              <div className="mt-2">
                <EvaluationStats evaluation={activeModel.evaluation} />
              </div>
            </div>
            <div className="mt-4 flex items-center gap-4 flex-wrap">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => retrain()}
                loading={retraining}
                disabled={subject.datasets.length === 0}
                icon={<RotateCcw className="h-3.5 w-3.5" />}
              >
                Retrain with latest data
              </Button>
              <label className="flex cursor-pointer items-center gap-2 text-xs text-muted" title="Optional -- flags a handful of suspicious rows in the newest data for you to glance at before they're baked into the model. Off by default, and you can always skip it.">
                <input
                  type="checkbox"
                  className="accent-accent"
                  checked={subject.pre_retrain_check_enabled}
                  disabled={savingReviewToggle}
                  onChange={togglePreRetrainCheck}
                />
                Review new data before retraining
              </label>
            </div>

            {pendingCandidates && pendingCandidates.length > 0 && (
              <PendingReviewCard
                candidates={pendingCandidates}
                labelingCandidateId={labelingCandidateId}
                retraining={retraining}
                onLabel={labelCandidate}
                onRetrain={() => retrain()}
                onRetrainForce={() => retrain(true)}
              />
            )}
          </>
        )}

        {advancedMode && (
          <AdvancedModelsPanel
            subject={subject}
            expanded={advancedExpanded}
            onToggleExpanded={() => setAdvancedExpanded((v) => !v)}
            trainingAlt={trainingAlt}
            onTrainAlternative={trainAlternative}
            activatingModelId={activatingModelId}
            onActivateModel={activateModel}
          />
        )}
      </Card>

      <Modal open={editOpen} onClose={() => setEditOpen(false)} title="Edit subject">
        <div className="space-y-3">
          <Input label="Name" value={editName} onChange={(e) => setEditName(e.target.value)} />
          <Input label="Description" value={editDescription} onChange={(e) => setEditDescription(e.target.value)} />
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setEditOpen(false)}>
              Cancel
            </Button>
            <Button onClick={saveEdit} loading={saving} disabled={!editName.trim()}>
              Save
            </Button>
          </div>
        </div>
      </Modal>

      <Modal open={deleteOpen} onClose={() => setDeleteOpen(false)} title="Delete subject">
        <div className="space-y-4">
          <p className="text-sm text-muted">
            This permanently deletes <b className="text-text">{subject.name}</b> and all of its datasets, models, and
            anomaly history. This cannot be undone.
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={confirmDelete} loading={deleting}>
              Delete permanently
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
