import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("token");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  }
);

export default api;

export type Profile = {
  n_rows: number;
  n_features: number;
  autocorr_lag1?: number | null;
  adf_pvalue?: number | null;
  fft_peak?: number | null;
  column_stats?: Record<string, { mean: number; std: number; min: number; max: number }>;
  error?: string;
};

export type Dataset = {
  id: number;
  name: string;
  n_rows: number;
  n_features: number;
  uploaded_at: string;
};

export type Threshold = {
  mu: number;
  sigma: number;
  epsilon: number;
  z_multiplier: number;
};

export type ModelInfo = {
  id: number;
  dataset_id: number;
  algorithm: "IF" | "LSTM";
  status: "pending" | "training" | "ready" | "failed";
  selection_reason: string | null;
  trained_at: string | null;
  drift_status: string;
  metrics: Record<string, any>;
  threshold: Threshold | null;
};

export type Anomaly = {
  id: number;
  prediction_id: number;
  model_id: number;
  window_idx: number;
  score: number;
  severity: string;
  label: string;
  note: string | null;
  created_at: string;
};

export type PredictResult = {
  batch_id: string;
  model_id: number;
  algorithm: string;
  threshold: number;
  total_windows: number;
  anomaly_count: number;
  anomaly_rate: number;
  results: { batch_id: string; window_idx: number; score: number; is_anomaly: boolean }[];
};

export const auth = {
  register: (email: string, password: string) =>
    api.post("/auth/register", { email, password }),
  login: (email: string, password: string) =>
    api.post<{ access_token: string; token_type: string }>("/auth/login", { email, password }),
  me: () => api.get<{ id: number; email: string }>("/auth/me"),
};

export const datasets = {
  upload: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return api.post<{ dataset_id: number; name: string; n_rows: number; n_features: number; profile: Profile }>(
      "/upload",
      fd,
      { headers: { "Content-Type": "multipart/form-data" } }
    );
  },
  list: () => api.get<Dataset[]>("/upload"),
};

export const models = {
  train: (datasetId: number) =>
    api.post<{ status: string; algorithm_chosen: string; reason: string }>(`/train/${datasetId}`),
  list: () => api.get<ModelInfo[]>("/train/models"),
  predict: (modelId: number, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return api.post<PredictResult>(`/predict/${modelId}`, fd, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
};

export const anomalies = {
  list: (params?: { model_id?: number; label?: string; limit?: number }) =>
    api.get<Anomaly[]>("/anomalies", { params }),
  label: (eventId: number, label: string, note?: string) =>
    api.patch<Anomaly>(`/anomalies/${eventId}`, { label, note }),
};

export const thresholds = {
  get: (modelId: number) => api.get<Threshold & { calibrated_at: string }>(`/settings/threshold/${modelId}`),
  update: (modelId: number, z: number) =>
    api.patch<Threshold & { calibrated_at: string }>(`/settings/threshold/${modelId}`, {
      z_multiplier: z,
    }),
};
