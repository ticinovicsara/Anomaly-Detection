import { useMemo, useState } from "react";
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  Scatter,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card } from "@/components/Card";
import { CurvePoint } from "@/api/client";
import { OUTCOME_COLOR, OUTCOME_LABEL, Outcome } from "./helpers";

type ChartPoint = CurvePoint & { outcome: Outcome };

const ALL_OUTCOMES: Outcome[] = ["tp", "fp", "fn", "tn"];
const ANOMALIES_ONLY: Outcome[] = ["tp", "fp", "fn"];
const CORRECT_ONLY: Outcome[] = ["tp", "tn"];

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0].payload as ChartPoint;
  return (
    <div className="rounded-xl border border-border bg-surface px-3 py-2 text-xs shadow-soft">
      <p className="font-medium text-text">Window {point.i}</p>
      <p className="mt-0.5 text-muted">
        score <span className="font-mono text-text">{point.score.toFixed(4)}</span>
      </p>
      <p className="mt-0.5" style={{ color: OUTCOME_COLOR[point.outcome] }}>
        {OUTCOME_LABEL[point.outcome]}
      </p>
    </div>
  );
}

export function PredictedVsActualChart({
  data,
  epsilon,
}: {
  data: ChartPoint[];
  epsilon: number | null | undefined;
}) {
  const [activeOutcomes, setActiveOutcomes] = useState<Set<Outcome>>(new Set(ALL_OUTCOMES));
  const [zoomDomain, setZoomDomain] = useState<[number, number] | null>(null);
  const [dragStart, setDragStart] = useState<number | null>(null);
  const [dragEnd, setDragEnd] = useState<number | null>(null);

  const toggleOutcome = (o: Outcome) => {
    setActiveOutcomes((prev) => {
      const next = new Set(prev);
      if (next.has(o)) next.delete(o);
      else next.add(o);
      // Never allow an empty set -- that would just be a blank chart.
      return next.size === 0 ? new Set(ALL_OUTCOMES) : next;
    });
  };
  const setPreset = (outcomes: Outcome[]) => setActiveOutcomes(new Set(outcomes));
  const isFiltered = activeOutcomes.size !== ALL_OUTCOMES.length;

  const counts = useMemo(() => {
    const c: Record<Outcome, number> = { tp: 0, fp: 0, fn: 0, tn: 0 };
    for (const p of data) c[p.outcome]++;
    return c;
  }, [data]);

  const handleMouseDown = (e: any) => {
    if (e?.activeLabel === undefined) return;
    setDragStart(Number(e.activeLabel));
    setDragEnd(Number(e.activeLabel));
  };
  const handleMouseMove = (e: any) => {
    if (dragStart === null || e?.activeLabel === undefined) return;
    setDragEnd(Number(e.activeLabel));
  };
  const handleMouseUp = () => {
    if (dragStart !== null && dragEnd !== null && dragStart !== dragEnd) {
      setZoomDomain([Math.min(dragStart, dragEnd), Math.max(dragStart, dragEnd)]);
    }
    setDragStart(null);
    setDragEnd(null);
  };

  return (
    <Card>
      <div className="mb-1 flex items-center justify-between flex-wrap gap-2">
        <h3 className="text-sm font-semibold text-text">Predicted vs. actual over the test split</h3>
        <div className="flex items-center gap-1.5">
          <FilterChip label="All" active={!isFiltered} onClick={() => setPreset(ALL_OUTCOMES)} />
          <FilterChip label="Anomalies only" active={activeOutcomes.size === 3 && !activeOutcomes.has("tn")} onClick={() => setPreset(ANOMALIES_ONLY)} />
          <FilterChip label="Correct only" active={activeOutcomes.size === 2 && activeOutcomes.has("tp") && activeOutcomes.has("tn")} onClick={() => setPreset(CORRECT_ONLY)} />
          {zoomDomain && (
            <FilterChip label="Reset zoom" onClick={() => setZoomDomain(null)} />
          )}
        </div>
      </div>
      <div className="mb-3 flex items-center gap-3 flex-wrap text-xs text-muted">
        {ALL_OUTCOMES.map((o) => (
          <LegendDot
            key={o}
            color={OUTCOME_COLOR[o]}
            label={`${OUTCOME_LABEL[o]} (${counts[o]})`}
            active={activeOutcomes.has(o)}
            onClick={() => toggleOutcome(o)}
          />
        ))}
        <span className="text-muted/70">Click a legend item to hide it · drag on the chart to zoom</span>
      </div>
      {data.length === 0 ? (
        <p className="text-sm text-muted">No curve data.</p>
      ) : (
        <div className="h-72 select-none">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={data}
              margin={{ top: 4, right: 8, left: 0, bottom: 0 }}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
            >
              <CartesianGrid stroke="rgb(var(--border))" strokeDasharray="3 3" />
              <XAxis
                dataKey="i"
                type="number"
                domain={zoomDomain ?? ["dataMin", "dataMax"]}
                allowDataOverflow
                stroke="rgb(var(--muted))"
                fontSize={11}
                tickLine={false}
                axisLine={false}
              />
              <YAxis stroke="rgb(var(--muted))" fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} cursor={{ stroke: "rgb(var(--border))" }} />
              {epsilon !== null && epsilon !== undefined && (
                <ReferenceLine
                  y={epsilon}
                  stroke="rgb(var(--accent))"
                  strokeDasharray="4 4"
                  label={{ value: "ε", fill: "rgb(var(--accent))", fontSize: 10 }}
                />
              )}
              <Line
                type="monotone"
                dataKey="score"
                stroke="rgb(var(--border))"
                strokeWidth={1}
                dot={false}
                activeDot={false}
                isAnimationActive={false}
                legendType="none"
                tooltipType="none"
              />
              <Scatter
                dataKey="score"
                isAnimationActive={false}
                shape={(props: any) => {
                  const outcome = props.payload.outcome as Outcome;
                  if (!activeOutcomes.has(outcome)) return <g />;
                  return <circle cx={props.cx} cy={props.cy} r={outcome === "tn" ? 2 : 3.5} fill={OUTCOME_COLOR[outcome]} />;
                }}
              />
              {dragStart !== null && dragEnd !== null && dragStart !== dragEnd && (
                <ReferenceArea x1={dragStart} x2={dragEnd} strokeOpacity={0.3} fill="rgb(var(--accent))" fillOpacity={0.12} />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}

function LegendDot({
  color,
  label,
  active,
  onClick,
}: {
  color: string;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-full px-1.5 py-0.5 transition-opacity ${active ? "" : "opacity-35"} hover:opacity-100`}
      title={active ? "Click to hide" : "Click to show"}
    >
      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
      {label}
    </button>
  );
}

function FilterChip({ label, active, onClick }: { label: string; active?: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
        active ? "border-accent bg-accent/10 text-accent" : "border-border text-muted hover:text-text"
      }`}
    >
      {label}
    </button>
  );
}
