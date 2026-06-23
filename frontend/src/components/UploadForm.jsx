import { useState } from "react";
import axios from "axios";

const DATASET_TYPES = ["credit_card", "ecg", "yahoo"];
const MODEL_TYPES = ["isolation_forest", "lstm_autoencoder"];

export default function UploadForm({ onUploadDone, onTrainDone, username, setUsername }) {
  const [datasetType, setDatasetType] = useState("credit_card");
  const [modelType, setModelType] = useState("isolation_forest");
  const [uploadFile, setUploadFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [training, setTraining] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [error, setError] = useState(null);

  async function handleUpload(e) {
    e.preventDefault();
    if (!uploadFile) return;
    setError(null);
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", uploadFile);
      const res = await axios.post(
        `/api/v1/upload?username=${encodeURIComponent(username)}&dataset_type=${datasetType}`,
        formData
      );
      setUploadResult(res.data);
      onUploadDone(res.data);
    } catch (err) {
      setError(err.response?.data?.detail ?? "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleTrain(e) {
    e.preventDefault();
    setError(null);
    setTraining(true);
    try {
      const res = await axios.post("/api/v1/train", {
        username,
        dataset_type: datasetType,
        model_type: modelType,
      });
      onTrainDone(res.data);
    } catch (err) {
      setError(err.response?.data?.detail ?? "Training failed");
    } finally {
      setTraining(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <label htmlFor="username" className="block text-sm font-medium text-gray-700 mb-1">
          Username
        </label>
        <input
          id="username"
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          placeholder="Enter your username"
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label htmlFor="dataset-type" className="block text-sm font-medium text-gray-700 mb-1">
            Dataset type
          </label>
          <select
            id="dataset-type"
            value={datasetType}
            onChange={(e) => setDatasetType(e.target.value)}
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {DATASET_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="model-type" className="block text-sm font-medium text-gray-700 mb-1">
            Model type
          </label>
          <select
            id="model-type"
            value={modelType}
            onChange={(e) => setModelType(e.target.value)}
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {MODEL_TYPES.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>
      </div>

      <form onSubmit={handleUpload} className="space-y-3">
        <label htmlFor="upload-csv" className="block text-sm font-medium text-gray-700">
          Upload CSV
        </label>
        <input
          id="upload-csv"
          type="file"
          accept=".csv"
          onChange={(e) => setUploadFile(e.target.files[0] ?? null)}
          className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
        />
        <button
          type="submit"
          disabled={!uploadFile || !username || uploading}
          className="w-full bg-indigo-600 text-white text-sm font-medium py-2 px-4 rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {uploading ? "Uploading…" : "Upload"}
        </button>
      </form>

      {uploadResult && (
        <div className="bg-green-50 border border-green-200 rounded-md p-3 text-sm text-green-800" role="status">
          Uploaded <strong>{uploadResult.filename}</strong> — {uploadResult.row_count.toLocaleString()} rows
        </div>
      )}

      <form onSubmit={handleTrain}>
        <button
          type="submit"
          disabled={!uploadResult || training}
          className="w-full bg-amber-500 text-white text-sm font-medium py-2 px-4 rounded-md hover:bg-amber-600 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {training ? "Training model…" : "Train model"}
        </button>
      </form>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-3 text-sm text-red-800" role="alert">
          {error}
        </div>
      )}
    </div>
  );
}
