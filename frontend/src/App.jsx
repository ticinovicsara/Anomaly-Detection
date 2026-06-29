import { useEffect, useState } from "react";
import axios from "axios";
import UploadForm from "./components/UploadForm";
import AnomalyChart from "./components/AnomalyChart";
import ResultsTable from "./components/ResultsTable";
import ResultsSummary from "./components/ResultsSummary";

export default function App() {
  const [username, setUsername] = useState("");
  const [uploadResult, setUploadResult] = useState(null);
  const [trainResult, setTrainResult] = useState(null);
  const [resultsSummary, setResultsSummary] = useState(null);
  const [predictResult, setPredictResult] = useState(null);
  const [predictFile, setPredictFile] = useState(null);
  const [predicting, setPredicting] = useState(false);
  const [predictError, setPredictError] = useState(null);
  const [resultsError, setResultsError] = useState(null);

  useEffect(() => {
    if (!trainResult?.dataset_type || !username) return;

    let cancelled = false;

    async function loadResults() {
      setResultsError(null);
      try {
        const res = await axios.get(
          `/api/v1/results?username=${encodeURIComponent(username)}&dataset_type=${encodeURIComponent(trainResult.dataset_type)}`
        );
        if (!cancelled) {
          setResultsSummary(res.data);
        }
      } catch (err) {
        if (!cancelled) {
          setResultsError(err.response?.data?.detail ?? "Failed to load results");
        }
      }
    }

    loadResults();

    return () => {
      cancelled = true;
    };
  }, [trainResult, username]);

  async function handlePredict(e) {
    e.preventDefault();
    if (!predictFile || !trainResult) return;
    setPredictError(null);
    setPredicting(true);
    try {
      const formData = new FormData();
      formData.append("file", predictFile);
      const res = await axios.post(
        `/api/v1/predict?username=${encodeURIComponent(username)}&dataset_type=${trainResult.dataset_type}&model_type=${trainResult.model_type}`,
        formData
      );
      setPredictResult(res.data);
    } catch (err) {
      setPredictError(err.response?.data?.detail ?? "Prediction failed");
    } finally {
      setPredicting(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <h1 className="text-xl font-bold text-gray-900">Anomaly Detection Platform</h1>
        <p className="text-sm text-gray-500 mt-0.5">Personalized time-series anomaly detection</p>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-8">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-base font-semibold text-gray-800 mb-4">
              <span className="inline-block w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 text-xs font-bold text-center leading-6 mr-2">1</span>
              Upload &amp; Train
            </h2>
            <UploadForm
              onUploadDone={setUploadResult}
              onTrainDone={setTrainResult}
              username={username}
              setUsername={setUsername}
            />
          </section>

          <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-base font-semibold text-gray-800 mb-4">
              <span className="inline-block w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 text-xs font-bold text-center leading-6 mr-2">2</span>
              Detect Anomalies
            </h2>

            {trainResult ? (
              <div className="space-y-4">
                <div className="bg-green-50 border border-green-200 rounded-md p-3 text-sm text-green-800">
                  Model trained — threshold: <strong>{trainResult.threshold}</strong>
                  <br />
                  <span className="text-xs text-green-700">
                    mean: {trainResult.mean_error} · std: {trainResult.std_error}
                    {trainResult.training_seconds ? ` · ${trainResult.training_seconds}s` : ""}
                  </span>
                </div>

                <form onSubmit={handlePredict} className="space-y-3">
                  <label htmlFor="predict-csv" className="block text-sm font-medium text-gray-700">
                    Upload CSV for prediction
                  </label>
                  <input
                    id="predict-csv"
                    type="file"
                    accept=".csv"
                    onChange={(e) => setPredictFile(e.target.files[0] ?? null)}
                    className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
                  />
                  <button
                    type="submit"
                    disabled={!predictFile || predicting}
                    className="w-full bg-indigo-600 text-white text-sm font-medium py-2 px-4 rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {predicting ? "Detecting…" : "Detect anomalies"}
                  </button>
                </form>

                {predictError && (
                  <div className="bg-red-50 border border-red-200 rounded-md p-3 text-sm text-red-800" role="alert">
                    {predictError}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-gray-400 italic">Train a model first to enable predictions.</p>
            )}
          </section>
        </div>

        {predictResult && (
          <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-6">
            <AnomalyChart
              scores={predictResult.scores}
              threshold={predictResult.threshold}
              anomalyIndices={predictResult.anomaly_indices}
            />
            <ResultsTable predictResult={predictResult} />
          </section>
        )}

        {(resultsSummary || resultsError) && (
          <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            {resultsError ? (
              <div className="bg-red-50 border border-red-200 rounded-md p-3 text-sm text-red-800" role="alert">
                {resultsError}
              </div>
            ) : (
              <ResultsSummary results={resultsSummary} />
            )}
          </section>
        )}
      </main>
    </div>
  );
}
