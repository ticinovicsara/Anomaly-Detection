export default function ResultsTable({ predictResult }) {
  if (!predictResult) return null;

  const { scores, anomaly_indices, threshold, total_windows, anomaly_count, anomaly_rate } = predictResult;
  const anomalySet = new Set(anomaly_indices);

  return (
    <div className="space-y-4">
      <h2 className="text-base font-semibold text-gray-800">Detection Results</h2>

      <div className="grid grid-cols-3 gap-3">
        <div className="bg-gray-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-gray-900">{total_windows.toLocaleString()}</div>
          <div className="text-xs text-gray-500 mt-0.5">Total windows</div>
        </div>
        <div className="bg-red-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-red-600">{anomaly_count.toLocaleString()}</div>
          <div className="text-xs text-gray-500 mt-0.5">Anomalies</div>
        </div>
        <div className="bg-amber-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-amber-600">{(anomaly_rate * 100).toFixed(2)}%</div>
          <div className="text-xs text-gray-500 mt-0.5">Anomaly rate</div>
        </div>
      </div>

      <div className="overflow-auto max-h-64 rounded-lg border border-gray-200">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 sticky top-0">
            <tr>
              <th className="text-left px-4 py-2 font-medium text-gray-600 text-xs">Window</th>
              <th className="text-right px-4 py-2 font-medium text-gray-600 text-xs">Score</th>
              <th className="text-right px-4 py-2 font-medium text-gray-600 text-xs">Threshold</th>
              <th className="text-center px-4 py-2 font-medium text-gray-600 text-xs">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {scores.map((score, i) => {
              const flagged = anomalySet.has(i);
              return (
                <tr key={i} className={flagged ? "bg-red-50" : ""}>
                  <td className="px-4 py-1.5 text-gray-700">{i}</td>
                  <td className={`px-4 py-1.5 text-right font-mono ${flagged ? "text-red-700 font-semibold" : "text-gray-600"}`}>
                    {score.toFixed(5)}
                  </td>
                  <td className="px-4 py-1.5 text-right font-mono text-gray-500">
                    {threshold.toFixed(5)}
                  </td>
                  <td className="px-4 py-1.5 text-center">
                    {flagged ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700">
                        Anomaly
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700">
                        Normal
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
