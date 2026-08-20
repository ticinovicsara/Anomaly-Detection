import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, FlaskConical, Info } from "lucide-react";
import { Card } from "@/components/Card";
import { Badge, statusTone } from "@/components/Badge";
import { EmptyState } from "@/components/EmptyState";
import { EvaluationStats } from "@/components/EvaluationStats";
import { FullPageSpinner } from "@/components/Spinner";
import {
  isCancelled,
  models as modelsApi,
  subjects as subjectsApi,
  ModelInfo,
  Subject,
} from "@/api/client";
import { ConfusionMatrix } from "./ConfusionMatrix";
import { LabeledPredictRuns } from "./LabeledPredictRuns";
import { PredictedVsActualChart } from "./PredictedVsActualChart";
import { WorstErrorsTable } from "./WorstErrorsTable";
import { outcomeOf } from "./helpers";

export default function ModelDiagnosticsPage() {
  const { id } = useParams<{ id: string }>();
  const modelId = Number(id);

  const [models, setModels] = useState<ModelInfo[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([modelsApi.list({ signal: controller.signal }), subjectsApi.list({ signal: controller.signal })])
      .then(([m, s]) => {
        setModels(m.data);
        setSubjects(s.data);
      })
      .catch((err) => {
        if (!isCancelled(err)) throw err;
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  const model = models.find((m) => m.id === modelId) ?? null;
  const subject = model ? subjects.find((s) => s.id === model.subject_id) ?? null : null;
  const evaluation = model?.metrics.evaluation ?? null;

  const chartData = useMemo(() => {
    if (!evaluation?.curve) return [];
    return evaluation.curve.map((p) => ({ ...p, outcome: outcomeOf(p) }));
  }, [evaluation]);

  const worstErrors = useMemo(() => {
    if (!evaluation?.curve || evaluation.epsilon === null || evaluation.epsilon === undefined) return [];
    const eps = evaluation.epsilon;
    return evaluation.curve
      .filter((p) => p.actual !== p.predicted)
      .map((p) => ({ ...p, outcome: outcomeOf(p), margin: p.score - eps }))
      .sort((a, b) => Math.abs(b.margin) - Math.abs(a.margin))
      .slice(0, 15);
  }, [evaluation]);

  if (loading) return <FullPageSpinner />;

  if (!model) {
    return (
      <Card>
        <EmptyState icon={ArrowLeft} title="Model not found" message="It may have been deleted." />
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Link
        to={subject ? `/subjects/${subject.id}` : "/models"}
        className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-text"
      >
        <ArrowLeft className="h-4 w-4" /> Back to {subject ? subject.name : "models"}
      </Link>

      <div className="flex items-center gap-3 flex-wrap">
        <div className="rounded-xl bg-accent/10 p-2 text-accent">
          <FlaskConical className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Model #{model.id} diagnostics</h1>
          <p className="mt-1 text-sm text-muted">
            {subject?.name ?? "Unknown subject"} · internal QA view, evaluated against the labeled test split
          </p>
        </div>
        <Badge tone="accent">{model.algorithm}</Badge>
        <Badge tone={statusTone(model.status)}>{model.status}</Badge>
      </div>

      {!evaluation ? (
        <Card>
          <EmptyState
            icon={FlaskConical}
            title="No evaluation available"
            message="This model wasn't trained with a labeled dataset (no ground-truth anomaly column was marked at upload time), so there's nothing to compare predictions against."
          />
        </Card>
      ) : (
        <>
          <div className="flex items-start gap-2.5 rounded-xl border border-border bg-surface-2/60 p-3.5 text-xs text-muted">
            <Info className="h-4 w-4 shrink-0 mt-0.5 text-accent" />
            <p>
              This section is a one-time backtest computed when the model was trained, using the ground-truth
              labels you marked at upload - it doesn&apos;t run again automatically. To check a specific new file
              instead, run <b>Predict</b> on the Models page with a CSV that includes a <code>label</code> column -
              the result then appears both here (under &quot;Labeled test runs&quot; below) and on your Anomalies
              page, tagged correct / false alarm / missed.
            </p>
          </div>

          <Card>
            <h3 className="text-sm font-semibold text-text">Metrics on held-out test set</h3>
            <p className="mt-1 text-xs text-muted">
              {evaluation.n_test_samples != null && evaluation.n_test_positive != null
                ? `${evaluation.n_test_samples.toLocaleString()} test points · ${evaluation.n_test_positive.toLocaleString()} actually anomalous · `
                : ""}
              evaluated at the real operational threshold ε
              {evaluation.epsilon !== null && evaluation.epsilon !== undefined ? ` = ${evaluation.epsilon.toFixed(4)}` : ""}
            </p>
            <div className="mt-4">
              <EvaluationStats evaluation={evaluation} />
            </div>
          </Card>

          {evaluation.confusion && <ConfusionMatrix confusion={evaluation.confusion} />}

          <PredictedVsActualChart data={chartData} epsilon={evaluation.epsilon} />

          <WorstErrorsTable errors={worstErrors} />
        </>
      )}

      <LabeledPredictRuns modelId={model.id} epsilon={model.threshold?.epsilon} />
    </div>
  );
}
