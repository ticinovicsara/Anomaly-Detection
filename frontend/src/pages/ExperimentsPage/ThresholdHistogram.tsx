import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Download } from "lucide-react";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ExperimentResult, PresetDemoResult } from "@/api/client";

type Props = {
  result: ExperimentResult | PresetDemoResult;
  onExport: () => void;
};

export function ThresholdHistogram({ result, onExport }: Props) {
  const chartData = Object.entries(result.epsilons)
    .map(([name, epsilon]) => ({ name, epsilon }))
    .sort((a, b) => a.epsilon - b.epsilon);

  const globalEps = result.cross_application.global_epsilon ?? null;

  return (
    <Card>
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text">Results — threshold histogram</h3>
        <Button variant="ghost" size="sm" onClick={onExport} icon={<Download className="h-3.5 w-3.5" />}>
          Export as JSON
        </Button>
      </div>
      <div className="mt-4 h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData}>
            <CartesianGrid stroke="rgb(var(--border))" strokeDasharray="3 3" />
            <XAxis dataKey="name" stroke="rgb(var(--muted))" fontSize={11} tickLine={false} axisLine={false} />
            <YAxis stroke="rgb(var(--muted))" fontSize={11} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{
                background: "rgb(var(--surface))",
                border: "1px solid rgb(var(--border))",
                borderRadius: 12,
                fontSize: 12,
              }}
              formatter={(v: number) => v.toFixed(4)}
            />
            {globalEps !== null && (
              <ReferenceLine
                y={globalEps}
                stroke="rgb(var(--danger))"
                strokeDasharray="4 4"
                label={{ value: "global ε (mean)", fill: "rgb(var(--danger))", fontSize: 10 }}
              />
            )}
            <Bar dataKey="epsilon" fill="rgb(var(--accent))" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-3 text-xs text-muted">
        Range: {result.statistics.min.toFixed(4)} – {result.statistics.max.toFixed(4)}
        {result.statistics.range_ratio !== null && ` (${result.statistics.range_ratio.toFixed(1)}× spread)`}, showing
        personalization is far from marginal.
      </p>
    </Card>
  );
}
