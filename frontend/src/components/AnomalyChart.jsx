import {
  ComposedChart,
  Line,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Legend,
} from "recharts";

export default function AnomalyChart({ scores, threshold, anomalyIndices }) {
  if (!scores || scores.length === 0) return null;

  const anomalySet = new Set(anomalyIndices);

  const data = scores.map((score, i) => ({
    window: i,
    score: parseFloat(score.toFixed(5)),
    anomaly: anomalySet.has(i) ? score : null,
  }));

  return (
    <div>
      <h2 className="text-base font-semibold text-gray-800 mb-3">Anomaly Score Chart</h2>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 16 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="window"
            label={{ value: "Window index", position: "insideBottomRight", offset: -8, fontSize: 11 }}
            tick={{ fontSize: 11 }}
          />
          <YAxis
            label={{ value: "Score", angle: -90, position: "insideLeft", fontSize: 11 }}
            tick={{ fontSize: 11 }}
          />
          <Tooltip
            formatter={(value, name) => [value?.toFixed(5), name === "score" ? "Reconstruction error" : "Anomaly"]}
            labelFormatter={(label) => `Window ${label}`}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <ReferenceLine
            y={threshold}
            stroke="#ef4444"
            strokeDasharray="4 2"
            label={{ value: `Threshold ${threshold.toFixed(4)}`, fill: "#ef4444", fontSize: 11 }}
          />
          <Line
            type="monotone"
            dataKey="score"
            stroke="#6366f1"
            dot={false}
            strokeWidth={1.5}
            name="Reconstruction error"
          />
          <Scatter
            dataKey="anomaly"
            fill="#ef4444"
            name="Anomaly"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
