import { useEffect, useRef, useState } from "react";
import { Brain, PlayCircle, Upload as UploadIcon } from "lucide-react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Badge, statusTone } from "../components/Badge";
import { FullPageSpinner } from "../components/Spinner";
import { useToast } from "../components/Toast";
import { errorMessage, models as modelsApi, ModelInfo, PredictResult } from "../api/client";

export default function Models() {
  const [items, setItems] = useState<ModelInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [predicting, setPredicting] = useState<number | null>(null);
  const [result, setResult] = useState<PredictResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [targetModel, setTargetModel] = useState<number | null>(null);
  const toast = useToast();

  const fetchList = () => modelsApi.list().then((r) => setItems(r.data));

  useEffect(() => {
    fetchList().finally(() => setLoading(false));
    const t = setInterval(() => {
      // if any training/pending, keep polling
      modelsApi.list().then((r) => setItems(r.data));
    }, 3000);
    return () => clearInterval(t);
  }, []);

  const runPredict = async (file: File) => {
    if (targetModel === null) return;
    setPredicting(targetModel);
    setResult(null);
    try {
      const r = await modelsApi.predict(targetModel, file);
      setResult(r.data);
      toast({
        tone: r.data.anomaly_count > 0 ? "warning" : "success",
        title: `${r.data.anomaly_count} anomalies detected`,
        message: `${r.data.total_windows} windows · rate ${(r.data.anomaly_rate * 100).toFixed(1)}%`,
      });
    } catch (err) {
      toast({ tone: "error", title: "Prediction failed", message: errorMessage(err) });
    } finally {
      setPredicting(null);
    }
  };

  if (loading) return <FullPageSpinner />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Models</h1>
        <p className="mt-1 text-sm text-muted">
          Trained models — click <b>Predict</b> to run one on new data.
        </p>
      </div>

      {items.length === 0 ? (
        <Card>
          <p className="text-sm text-muted">
            No models yet. Upload data on the <a className="text-accent hover:underline" href="/upload">Upload</a> page.
          </p>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((m) => (
            <Card key={m.id} hoverable>
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="rounded-xl bg-accent/10 p-2 text-accent">
                    <Brain className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold">Model #{m.id}</p>
                    <p className="text-xs text-muted">Dataset #{m.dataset_id}</p>
                  </div>
                </div>
                <Badge tone={statusTone(m.status)}>{m.status}</Badge>
              </div>

              <div className="mt-4 space-y-2">
                <Row label="Algorithm" value={m.algorithm} />
                <Row
                  label="Threshold ε"
                  value={m.threshold ? m.threshold.epsilon.toFixed(4) : "—"}
                />
                <Row
                  label="z-multiplier"
                  value={m.threshold ? m.threshold.z_multiplier.toFixed(1) : "—"}
                />
              </div>

              {m.selection_reason && (
                <p className="mt-3 rounded-lg bg-surface-2/60 p-2.5 text-[11px] text-muted">
                  {m.selection_reason}
                </p>
              )}

              {m.status === "failed" && m.metrics?.error && (
                <p className="mt-3 rounded-lg bg-danger/10 p-2.5 text-[11px] text-danger">
                  {m.metrics.error}
                </p>
              )}

              <Button
                variant="secondary"
                size="sm"
                className="mt-4 w-full"
                disabled={m.status !== "ready"}
                loading={predicting === m.id}
                icon={<PlayCircle className="h-4 w-4" />}
                onClick={() => {
                  setTargetModel(m.id);
                  fileInputRef.current?.click();
                }}
              >
                Predict on new CSV
              </Button>
            </Card>
          ))}
        </div>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept=".csv"
        hidden
        onChange={(e) => e.target.files?.[0] && runPredict(e.target.files[0])}
      />

      {result && (
        <Card className="animate-fade-in">
          <div className="flex items-center gap-3 mb-4">
            <div className="rounded-xl bg-accent/10 p-2 text-accent">
              <UploadIcon className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold">Prediction result</p>
              <p className="text-xs text-muted">
                Model #{result.model_id} · algorithm {result.algorithm}
              </p>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-4">
            <StatMini label="Windows" value={result.total_windows} />
            <StatMini label="Anomalies" value={result.anomaly_count} tone="warning" />
            <StatMini label="Rate" value={`${(result.anomaly_rate * 100).toFixed(1)}%`} />
            <StatMini label="Threshold" value={result.threshold.toFixed(3)} />
          </div>
        </Card>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-muted">{label}</span>
      <span className="font-mono text-text">{value}</span>
    </div>
  );
}

function StatMini({ label, value, tone }: { label: string; value: string | number; tone?: "warning" }) {
  return (
    <div className="rounded-xl border border-border bg-surface-2/50 p-3">
      <p className="text-[10px] uppercase tracking-wider text-muted">{label}</p>
      <p
        className={`mt-1 font-mono text-lg font-semibold ${
          tone === "warning" ? "text-warning" : "text-text"
        }`}
      >
        {value}
      </p>
    </div>
  );
}
