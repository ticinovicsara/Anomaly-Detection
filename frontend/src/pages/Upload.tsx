import { DragEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { UploadCloud, FileText, Sparkles, Brain, ArrowRight } from "lucide-react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Badge } from "../components/Badge";
import { useToast } from "../components/Toast";
import { datasets, errorMessage, models, Profile } from "../api/client";

type UploadedInfo = {
  dataset_id: number;
  name: string;
  n_rows: number;
  n_features: number;
  profile: Profile;
};

export default function Upload() {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [training, setTraining] = useState(false);
  const [info, setInfo] = useState<UploadedInfo | null>(null);
  const [chosen, setChosen] = useState<{ algorithm_chosen: string; reason: string } | null>(null);
  const toast = useToast();
  const nav = useNavigate();

  const handleFile = async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".csv")) {
      toast({ tone: "error", title: "Only .csv files are accepted" });
      return;
    }
    setUploading(true);
    setInfo(null);
    setChosen(null);
    try {
      const r = await datasets.upload(file);
      setInfo(r.data);
      toast({ tone: "success", title: "File uploaded", message: `${r.data.n_rows} rows analyzed` });
    } catch (err) {
      toast({ tone: "error", title: "Upload failed", message: errorMessage(err, "Try again") });
    } finally {
      setUploading(false);
    }
  };

  const startTraining = async () => {
    if (!info) return;
    setTraining(true);
    try {
      const r = await models.train(info.dataset_id);
      setChosen({ algorithm_chosen: r.data.algorithm_chosen, reason: r.data.reason });
      toast({
        tone: "info",
        title: "Training started",
        message: `${r.data.algorithm_chosen} — ${r.data.reason}`,
      });
      setTimeout(() => nav("/models"), 800);
    } catch (err) {
      toast({ tone: "error", title: "Could not start training", message: errorMessage(err) });
    } finally {
      setTraining(false);
    }
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Upload data</h1>
        <p className="mt-1 text-sm text-muted">
          Drop a CSV — we&apos;ll analyze it and pick the best model automatically.
        </p>
      </div>

      {/* Dropzone */}
      <Card className="p-0 overflow-hidden">
        <label
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`flex cursor-pointer flex-col items-center justify-center gap-3 border-2 border-dashed p-12 transition-colors duration-150 ease-out ${
            dragging ? "border-accent bg-accent/5" : "border-border hover:border-accent/60 hover:bg-surface-2/50"
          }`}
        >
          <div className="rounded-2xl bg-accent/10 p-4 text-accent">
            <UploadCloud className="h-8 w-8" />
          </div>
          <div className="text-center">
            <p className="text-sm font-medium text-text">
              {uploading ? "Uploading…" : "Drop your CSV here"}
            </p>
            <p className="mt-1 text-xs text-muted">or click to browse — up to 50 MB</p>
          </div>
          <input
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          />
        </label>
      </Card>

      {/* Result -- grid-rows 0fr/1fr trick animates the reveal's height smoothly
          instead of the layout just popping taller when info arrives. */}
      <div
        className={`grid transition-[grid-template-rows] duration-300 ease-out ${
          info ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
      >
        <div className="overflow-hidden">
          {info && (
            <div className="grid gap-6 lg:grid-cols-2 animate-fade-in pt-1">
              <Card>
                <div className="flex items-center gap-3">
                  <div className="rounded-xl bg-surface-2 p-2 text-accent">
                    <FileText className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-text">{info.name}</p>
                    <p className="text-xs text-muted">
                      {info.n_rows.toLocaleString()} rows · {info.n_features} columns
                    </p>
                  </div>
                </div>

                <div className="mt-5 space-y-2">
                  <ProfileRow label="Rows" value={info.n_rows.toLocaleString()} />
                  <ProfileRow label="Numeric features" value={String(info.profile.n_features)} />
                  <ProfileRow
                    label="Autocorrelation (lag 1)"
                    value={fmt(info.profile.autocorr_lag1)}
                    hint="closer to 1 → strongly sequential"
                  />
                  <ProfileRow
                    label="Stationarity p-value"
                    value={fmt(info.profile.adf_pvalue)}
                    hint="< 0.05 → stationary"
                  />
                  <ProfileRow
                    label="Dominant frequency"
                    value={fmt(info.profile.fft_peak, 4)}
                    hint="periodic patterns"
                  />
                </div>
              </Card>

              <Card>
                <div className="flex items-center gap-3">
                  <div className="rounded-xl bg-accent/10 p-2 text-accent">
                    <Sparkles className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-text">Model recommendation</p>
                    <p className="text-xs text-muted">
                      Based on the data profile — you don&apos;t have to choose.
                    </p>
                  </div>
                </div>

                {chosen ? (
                  <div className="mt-5">
                    <div className="rounded-xl border border-accent/30 bg-accent/5 p-4">
                      <div className="flex items-center gap-2">
                        <Brain className="h-4 w-4 text-accent" />
                        <span className="text-sm font-semibold text-text">{chosen.algorithm_chosen}</span>
                        <Badge tone="accent">selected</Badge>
                      </div>
                      <p className="mt-2 text-xs text-muted">{chosen.reason}</p>
                    </div>
                  </div>
                ) : (
                  <div className="mt-5">
                    <p className="text-sm text-muted">
                      Click <b>Start training</b> — the system will profile your data, select the best model
                      (Isolation Forest or LSTM), train it, and calibrate a personalized threshold.
                    </p>
                    <div className="mt-4 flex gap-2">
                      <Button
                        onClick={startTraining}
                        loading={training}
                        icon={<ArrowRight className="h-4 w-4" />}
                      >
                        Start training
                      </Button>
                    </div>
                  </div>
                )}
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ProfileRow({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex items-baseline justify-between rounded-lg px-3 py-2 hover:bg-surface-2/50">
      <div>
        <p className="text-xs text-muted">{label}</p>
        {hint && <p className="text-[10px] text-muted/70">{hint}</p>}
      </div>
      <span className="font-mono text-sm text-text">{value}</span>
    </div>
  );
}

function fmt(n: number | null | undefined, digits = 3): string {
  if (n === null || n === undefined) return "—";
  return n.toFixed(digits);
}
