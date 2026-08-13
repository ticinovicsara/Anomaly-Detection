import {
  CartesianGrid,
  ComposedChart,
  Line,
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

export function PredictedVsActualChart({
  data,
  epsilon,
}: {
  data: ChartPoint[];
  epsilon: number | null | undefined;
}) {
  return (
    <Card>
      <div className="mb-4 flex items-center justify-between flex-wrap gap-2">
        <h3 className="text-sm font-semibold text-text">Predicted vs. actual over the test split</h3>
        <div className="flex items-center gap-3 text-xs text-muted">
          <LegendDot color={OUTCOME_COLOR.tp} label="correct anomaly" />
          <LegendDot color={OUTCOME_COLOR.fp} label="false positive" />
          <LegendDot color={OUTCOME_COLOR.fn} label="missed" />
          <LegendDot color={OUTCOME_COLOR.tn} label="correct normal" />
        </div>
      </div>
      {data.length === 0 ? (
        <p className="text-sm text-muted">No curve data.</p>
      ) : (
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="rgb(var(--border))" strokeDasharray="3 3" />
              <XAxis dataKey="i" stroke="rgb(var(--muted))" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis stroke="rgb(var(--muted))" fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip
                contentStyle={{
                  background: "rgb(var(--surface))",
                  border: "1px solid rgb(var(--border))",
                  borderRadius: 12,
                  fontSize: 12,
                }}
                formatter={(value: number, name: string, item) => {
                  if (name === "score") {
                    const outcome = (item.payload as { outcome: Outcome }).outcome;
                    return [value.toFixed(4), OUTCOME_LABEL[outcome]];
                  }
                  return [value, name];
                }}
              />
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
              />
              <Scatter
                dataKey="score"
                isAnimationActive={false}
                shape={(props: any) => {
                  const outcome = props.payload.outcome as Outcome;
                  return <circle cx={props.cx} cy={props.cy} r={outcome === "tn" ? 2 : 3.5} fill={OUTCOME_COLOR[outcome]} />;
                }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}
