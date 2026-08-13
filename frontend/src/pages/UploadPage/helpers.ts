import { SplitPeriod } from "@/api/client";

export type SubjectTarget = "new" | "existing";
export type SplitMode = "none" | "by_column" | "by_time";
export type AlgorithmChoice = "auto" | "IF" | "LSTM";

export const PERIODS: SplitPeriod[] = ["hourly", "daily", "weekly", "monthly"];
export const PERIOD_MS: Record<SplitPeriod, number> = {
  hourly: 3_600_000,
  daily: 86_400_000,
  weekly: 7 * 86_400_000,
  monthly: 30 * 86_400_000,
};

export function estimateTimeGroups(
  sampleRange: [string, string],
  period: SplitPeriod,
): number | null {
  const start = new Date(sampleRange[0]).getTime();
  const end = new Date(sampleRange[1]).getTime();
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return null;
  return Math.max(1, Math.ceil((end - start) / PERIOD_MS[period]) + 1);
}

export function fmt(n: number | null | undefined, digits = 3): string {
  if (n === null || n === undefined) return "-";
  return n.toFixed(digits);
}
