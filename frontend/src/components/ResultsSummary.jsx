export default function ResultsSummary({ results }) {
  if (!results?.models?.length) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-gray-800">Results & comparison</h2>
          <p className="text-sm text-gray-500">
            {results.dataset_type.replaceAll("_", " ")} · best model: {results.best_model ?? "—"}
          </p>
        </div>
      </div>

      <div className="overflow-auto rounded-lg border border-gray-200">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left px-4 py-2 font-medium text-gray-600 text-xs">Model</th>
              <th className="text-right px-4 py-2 font-medium text-gray-600 text-xs">F1</th>
              <th className="text-right px-4 py-2 font-medium text-gray-600 text-xs">ROC-AUC</th>
              <th className="text-right px-4 py-2 font-medium text-gray-600 text-xs">Threshold</th>
              <th className="text-right px-4 py-2 font-medium text-gray-600 text-xs">Avg threshold</th>
              <th className="text-right px-4 py-2 font-medium text-gray-600 text-xs">Delta</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {results.models.map((model) => (
              <tr key={model.model_type}>
                <td className="px-4 py-2 text-gray-800">{model.model_type}</td>
                <td className="px-4 py-2 text-right text-gray-600">{formatMetric(model.metrics.f1)}</td>
                <td className="px-4 py-2 text-right text-gray-600">{formatMetric(model.metrics.roc_auc)}</td>
                <td className="px-4 py-2 text-right font-mono text-gray-600">{formatMetric(model.threshold, 6)}</td>
                <td className="px-4 py-2 text-right font-mono text-gray-500">{formatMetric(model.avg_threshold, 6)}</td>
                <td className="px-4 py-2 text-right font-mono text-gray-500">{formatMetric(model.threshold_delta, 6)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function formatMetric(value, digits = 4) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return Number(value).toFixed(digits);
}
