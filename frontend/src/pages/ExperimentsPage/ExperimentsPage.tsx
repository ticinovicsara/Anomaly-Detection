import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { useToast } from "@/components/Toast";
import {
  errorMessage,
  experiments as experimentsApi,
  isCancelled,
  subjects as subjectsApi,
  ExperimentResult,
  PresetDemoResult,
  Subject,
} from "@/api/client";
import { SubjectSelector } from "./SubjectSelector";
import { ThresholdHistogram } from "./ThresholdHistogram";
import { CrossApplicationImpact } from "./CrossApplicationImpact";

export default function ExperimentsPage() {
  const toast = useToast();

  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [loadingSubjects, setLoadingSubjects] = useState(true);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const [result, setResult] = useState<ExperimentResult | PresetDemoResult | null>(null);
  const [running, setRunning] = useState(false);
  const [runningDemo, setRunningDemo] = useState(false);

  const loadSubjects = (signal?: AbortSignal) =>
    subjectsApi.list({ signal }).then((r) => {
      setSubjects(r.data);
      setSelected((prev) => {
        if (prev.size > 0) return prev;
        return new Set(r.data.filter((s) => s.active_epsilon !== null).map((s) => s.id));
      });
    });

  useEffect(() => {
    const controller = new AbortController();
    loadSubjects(controller.signal)
      .catch((err) => {
        if (!isCancelled(err)) throw err;
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingSubjects(false);
      });
    return () => controller.abort();
  }, []);

  const trainedSubjects = useMemo(() => subjects.filter((s) => s.active_epsilon !== null), [subjects]);

  const toggle = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => setSelected(new Set(trainedSubjects.map((s) => s.id)));
  const selectNone = () => setSelected(new Set());

  const runExperiment = async () => {
    setRunning(true);
    try {
      const r = await experimentsApi.run(Array.from(selected));
      setResult(r.data);
    } catch (err) {
      toast({ tone: "error", title: "Experiment failed", message: errorMessage(err) });
    } finally {
      setRunning(false);
    }
  };

  const runPresetDemo = async () => {
    setRunningDemo(true);
    try {
      const r = await experimentsApi.presetDemo();
      setResult(r.data);
      toast({
        tone: "success",
        title: "Demo ready",
        message: `Created ${r.data.created_subject_ids.length} synthetic subjects and ran the experiment across them.`,
      });
      await loadSubjects();
    } catch (err) {
      toast({ tone: "error", title: "Demo failed", message: errorMessage(err) });
    } finally {
      setRunningDemo(false);
    }
  };

  const exportJson = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `personalization-experiment-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Personalization experiment"
        subtitle="Run this experiment across your subjects to visualize the impact of personalized thresholds vs. a single global one."
      />

      <SubjectSelector
        loading={loadingSubjects}
        subjects={trainedSubjects}
        selected={selected}
        onToggle={toggle}
        onSelectAll={selectAll}
        onSelectNone={selectNone}
        onRun={runExperiment}
        running={running}
      />

      <Card>
        <h3 className="text-sm font-semibold text-text">Or: try a preset demo</h3>
        <p className="mt-1 text-sm text-muted">
          Generates 10 synthetic subjects sharing the same underlying signal structure but different noise
          levels, trains an LSTM Autoencoder independently on each, and runs the experiment across them — a
          quick way to see the argument without uploading real data first.
        </p>
        <div className="mt-4">
          <Button variant="secondary" onClick={runPresetDemo} loading={runningDemo} icon={<Sparkles className="h-4 w-4" />}>
            Load &amp; run demo
          </Button>
        </div>
      </Card>

      {result && (
        <>
          <ThresholdHistogram result={result} onExport={exportJson} />

          <CrossApplicationImpact result={result} />

          <Card>
            <h3 className="text-sm font-semibold text-text">Statistics</h3>
            <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-5">
              <Stat label="mean ε" value={result.statistics.mean.toFixed(4)} />
              <Stat label="std ε" value={result.statistics.std.toFixed(4)} />
              <Stat label="min ε" value={result.statistics.min.toFixed(4)} />
              <Stat label="max ε" value={result.statistics.max.toFixed(4)} />
              <Stat label="range ratio" value={result.statistics.range_ratio !== null ? `${result.statistics.range_ratio.toFixed(1)}×` : "-"} />
            </div>
          </Card>

          {"created_subject_ids" in result && (
            <p className="text-xs text-muted">
              Demo subjects were added to your account — view them on the{" "}
              <Link to="/subjects" className="text-accent hover:underline">
                Subjects page
              </Link>
              .
            </p>
          )}
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 font-mono text-lg font-semibold text-text">{value}</p>
    </div>
  );
}
