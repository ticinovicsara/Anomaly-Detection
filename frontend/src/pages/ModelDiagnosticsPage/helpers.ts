import { CurvePoint } from "@/api/client";

export type Outcome = "tp" | "fp" | "fn" | "tn";

export function outcomeOf(p: CurvePoint): Outcome {
  if (p.actual === 1 && p.predicted === 1) return "tp";
  if (p.actual === 0 && p.predicted === 1) return "fp";
  if (p.actual === 1 && p.predicted === 0) return "fn";
  return "tn";
}

export const OUTCOME_COLOR: Record<Outcome, string> = {
  tp: "rgb(var(--success))",
  fp: "rgb(var(--warning))",
  fn: "rgb(var(--danger))",
  tn: "rgb(var(--muted))",
};

export const OUTCOME_LABEL: Record<Outcome, string> = {
  tp: "Correctly flagged anomaly",
  fp: "False positive",
  fn: "Missed anomaly",
  tn: "Correctly normal",
};
