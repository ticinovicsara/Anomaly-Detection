import { DragEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { UploadCloud, FileText } from "lucide-react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Input } from "../components/Input";
import { useToast } from "../components/Toast";
import {
  datasets,
  errorMessage,
  subjects as subjectsApi,
  AnalyzeResult,
  Subject,
  SplitPeriod,
} from "../api/client";

type SubjectTarget = "new" | "existing";
type SplitMode = "none" | "by_column" | "by_time";

const PERIODS: SplitPeriod[] = ["hourly", "daily", "weekly", "monthly"];
const PERIOD_MS: Record<SplitPeriod, number> = {
  hourly: 3_600_000,
  daily: 86_400_000,
  weekly: 7 * 86_400_000,
  monthly: 30 * 86_400_000,
};

function estimateTimeGroups(sampleRange: [string, string], period: SplitPeriod): number | null {
  const start = new Date(sampleRange[0]).getTime();
  const end = new Date(sampleRange[1]).getTime();
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return null;
  return Math.max(1, Math.ceil((end - start) / PERIOD_MS[period]) + 1);
}

export default function Upload() {
  const [dragging, setDragging] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState<AnalyzeResult | null>(null);

  const [existingSubjects, setExistingSubjects] = useState<Subject[]>([]);
  const [target, setTarget] = useState<SubjectTarget>("new");
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [existingSubjectId, setExistingSubjectId] = useState<number | null>(null);

  const [splitMode, setSplitMode] = useState<SplitMode>("none");
  const [splitColumn, setSplitColumn] = useState("");
  const [splitPeriod, setSplitPeriod] = useState<SplitPeriod>("daily");

  const [committing, setCommitting] = useState(false);

  const toast = useToast();
  const nav = useNavigate();

  useEffect(() => {
    const controller = new AbortController();
    subjectsApi
      .list({ signal: controller.signal })
      .then((r) => setExistingSubjects(r.data))
      .catch(() => {
        // Non-critical: the "add to existing subject" option just won't
        // have anything to offer if this fails.
      });
    return () => controller.abort();
  }, []);

  const handleFile = async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".csv")) {
      toast({ tone: "error", title: "Only .csv files are accepted" });
      return;
    }
    setAnalyzing(true);
    setAnalysis(null);
    try {
      const r = await datasets.analyze(file);
      setAnalysis(r.data);
      setNewName(file.name.replace(/\.csv$/i, ""));
      setNewDescription("");
      setTarget("new");
      setExistingSubjectId(null);
      setSplitMode("none");
      setSplitColumn("");
      toast({
        tone: "success",
        title: "File analyzed",
        message: `${r.data.n_rows.toLocaleString()} rows, ${r.data.n_features} columns`,
      });
    } catch (err) {
      toast({ tone: "error", title: "Analysis failed", message: errorMessage(err, "Try again") });
    } finally {
      setAnalyzing(false);
    }
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const setSplit = (mode: SplitMode) => {
    setSplitMode(mode);
    setSplitColumn("");
    // Splitting always creates new subjects -- an "existing" target
    // wouldn't make sense once N new subjects are about to be created.
    if (mode !== "none" && target === "existing") setTarget("new");
  };

  const idColumns = analysis?.split_options.candidate_id_columns ?? [];
  const timeColumns = analysis?.split_options.candidate_time_columns ?? [];
  const selectedIdColumn = idColumns.find((c) => c.column === splitColumn);
  const selectedTimeColumn = timeColumns.find((c) => c.column === splitColumn);

  const splitPreview =
    splitMode === "by_column" && selectedIdColumn
      ? `Will create ${selectedIdColumn.n_unique} subjects`
      : splitMode === "by_time" && selectedTimeColumn
        ? (() => {
            const n = estimateTimeGroups(selectedTimeColumn.sample_range, splitPeriod);
            return n ? `Will create ~${n} subjects` : null;
          })()
        : null;

  const canCommit =
    !!analysis &&
    !committing &&
    (target === "new" ? newName.trim().length > 0 : existingSubjectId !== null) &&
    (splitMode === "none" || !!splitColumn);

  const commit = async () => {
    if (!analysis || !canCommit) return;
    setCommitting(true);
    try {
      const split =
        splitMode === "none"
          ? ({ mode: "none" } as const)
          : splitMode === "by_column"
            ? ({ mode: "by_column", column: splitColumn } as const)
            : ({ mode: "by_time", column: splitColumn, period: splitPeriod } as const);

      const r = await datasets.commit({
        temp_id: analysis.temp_id,
        target,
        subject_name: target === "new" ? newName.trim() : undefined,
        subject_description: target === "new" ? newDescription.trim() || undefined : undefined,
        subject_id: target === "existing" ? existingSubjectId ?? undefined : undefined,
        split,
      });
      const n = r.data.subject_ids.length;
      toast({
        tone: "info",
        title: n === 1 ? "Subject ready, training in progress" : `Created ${n} subjects, training in progress`,
      });
      nav("/subjects");
    } catch (err) {
      toast({ tone: "error", title: "Could not save", message: errorMessage(err) });
    } finally {
      setCommitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Upload data</h1>
        <p className="mt-1 text-sm text-muted">
          Drop a CSV, and we&apos;ll analyze it and help you organize it into subjects.
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
            <p className="text-sm font-medium text-text">{analyzing ? "Analyzing…" : "Drop your CSV here"}</p>
            <p className="mt-1 text-xs text-muted">or click to browse, up to 50 MB</p>
          </div>
          <input
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          />
        </label>
      </Card>

      {/* Steps 2-4 reveal once the file is analyzed -- grid-rows 0fr/1fr
          trick animates the height smoothly instead of the layout just
          popping taller. */}
      <div
        className={`grid transition-[grid-template-rows] duration-300 ease-out ${
          analysis ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
      >
        <div className="overflow-hidden">
          {analysis && (
            <div className="space-y-6 pt-1 animate-fade-in">
              {/* Profile */}
              <Card>
                <div className="flex items-center gap-3">
                  <div className="rounded-xl bg-surface-2 p-2 text-accent">
                    <FileText className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-text">Data profile</p>
                    <p className="text-xs text-muted">
                      {analysis.n_rows.toLocaleString()} rows · {analysis.n_features} columns
                    </p>
                  </div>
                </div>
                <div className="mt-5 grid gap-2 sm:grid-cols-2">
                  <ProfileRow
                    label="Autocorrelation (lag 1)"
                    value={fmt(analysis.profile.autocorr_lag1)}
                    hint="closer to 1 → strongly sequential"
                  />
                  <ProfileRow
                    label="Stationarity p-value"
                    value={fmt(analysis.profile.adf_pvalue)}
                    hint="< 0.05 → stationary"
                  />
                  <ProfileRow
                    label="Dominant frequency"
                    value={fmt(analysis.profile.fft_peak, 4)}
                    hint="periodic patterns"
                  />
                  <ProfileRow label="Numeric features" value={String(analysis.profile.n_features)} />
                </div>
              </Card>

              {/* Where does this data belong? */}
              <Card>
                <p className="text-sm font-semibold text-text">Where does this data belong?</p>
                <div className="mt-4 space-y-3">
                  <label className="flex cursor-pointer items-start gap-3">
                    <input
                      type="radio"
                      name="target"
                      className="mt-1 accent-accent"
                      checked={target === "new"}
                      onChange={() => setTarget("new")}
                    />
                    <div className="flex-1">
                      <span className="text-sm text-text">Create new subject</span>
                      {target === "new" && (
                        <div className="mt-2 space-y-2">
                          <Input
                            placeholder="e.g. Patient 101"
                            value={newName}
                            onChange={(e) => setNewName(e.target.value)}
                          />
                          <Input
                            placeholder="Description (optional)"
                            value={newDescription}
                            onChange={(e) => setNewDescription(e.target.value)}
                          />
                        </div>
                      )}
                    </div>
                  </label>

                  <label
                    className={`flex items-start gap-3 ${
                      existingSubjects.length === 0 || splitMode !== "none" ? "opacity-50" : "cursor-pointer"
                    }`}
                    title={splitMode !== "none" ? "Splitting always creates new subjects" : undefined}
                  >
                    <input
                      type="radio"
                      name="target"
                      className="mt-1 accent-accent"
                      checked={target === "existing"}
                      disabled={existingSubjects.length === 0 || splitMode !== "none"}
                      onChange={() => setTarget("existing")}
                    />
                    <div className="flex-1">
                      <span className="text-sm text-text">Add to existing subject</span>
                      {target === "existing" && (
                        <select
                          className="mt-2 w-full rounded-xl border border-border bg-surface-2 px-3 py-2.5 text-sm text-text focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
                          value={existingSubjectId ?? ""}
                          onChange={(e) => setExistingSubjectId(Number(e.target.value))}
                        >
                          <option value="" disabled>
                            Select a subject…
                          </option>
                          {existingSubjects.map((s) => (
                            <option key={s.id} value={s.id}>
                              {s.name}
                            </option>
                          ))}
                        </select>
                      )}
                    </div>
                  </label>
                </div>
              </Card>

              {/* How to organize this data? */}
              <Card>
                <p className="text-sm font-semibold text-text">How should this data be organized?</p>
                <div className="mt-4 space-y-3">
                  <label className="flex cursor-pointer items-center gap-3">
                    <input
                      type="radio"
                      name="split"
                      className="accent-accent"
                      checked={splitMode === "none"}
                      onChange={() => setSplit("none")}
                    />
                    <span className="text-sm text-text">Treat as one subject (default)</span>
                  </label>

                  <label
                    className={`flex items-start gap-3 ${idColumns.length === 0 ? "opacity-50" : "cursor-pointer"}`}
                  >
                    <input
                      type="radio"
                      name="split"
                      className="mt-1 accent-accent"
                      checked={splitMode === "by_column"}
                      disabled={idColumns.length === 0}
                      onChange={() => setSplit("by_column")}
                    />
                    <div className="flex-1">
                      <span className="text-sm text-text">Split by column</span>
                      {splitMode === "by_column" && (
                        <select
                          className="mt-2 w-full rounded-xl border border-border bg-surface-2 px-3 py-2.5 text-sm text-text focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
                          value={splitColumn}
                          onChange={(e) => setSplitColumn(e.target.value)}
                        >
                          <option value="" disabled>
                            Select a column…
                          </option>
                          {idColumns.map((c) => (
                            <option key={c.column} value={c.column}>
                              {c.column} ({c.n_unique} unique values)
                            </option>
                          ))}
                        </select>
                      )}
                    </div>
                  </label>

                  <label
                    className={`flex items-start gap-3 ${timeColumns.length === 0 ? "opacity-50" : "cursor-pointer"}`}
                  >
                    <input
                      type="radio"
                      name="split"
                      className="mt-1 accent-accent"
                      checked={splitMode === "by_time"}
                      disabled={timeColumns.length === 0}
                      onChange={() => setSplit("by_time")}
                    />
                    <div className="flex-1">
                      <span className="text-sm text-text">Split by time</span>
                      {splitMode === "by_time" && (
                        <div className="mt-2 flex gap-2">
                          <select
                            className="flex-1 rounded-xl border border-border bg-surface-2 px-3 py-2.5 text-sm text-text focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
                            value={splitColumn}
                            onChange={(e) => setSplitColumn(e.target.value)}
                          >
                            <option value="" disabled>
                              Select a column…
                            </option>
                            {timeColumns.map((c) => (
                              <option key={c.column} value={c.column}>
                                {c.column}
                              </option>
                            ))}
                          </select>
                          <select
                            className="w-32 rounded-xl border border-border bg-surface-2 px-3 py-2.5 text-sm text-text focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
                            value={splitPeriod}
                            onChange={(e) => setSplitPeriod(e.target.value as SplitPeriod)}
                          >
                            {PERIODS.map((p) => (
                              <option key={p} value={p}>
                                {p}
                              </option>
                            ))}
                          </select>
                        </div>
                      )}
                    </div>
                  </label>
                </div>
                {splitPreview && <p className="mt-4 text-xs font-medium text-accent">{splitPreview}</p>}
              </Card>

              <Button onClick={commit} loading={committing} disabled={!canCommit} className="w-full sm:w-auto">
                Analyze &amp; train
              </Button>
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
  if (n === null || n === undefined) return "-";
  return n.toFixed(digits);
}
