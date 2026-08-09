import axios, { AxiosRequestConfig } from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

const MAX_RETRIES = 3;
const RETRY_BASE_DELAY_MS = 300;

type RetryableConfig = AxiosRequestConfig & { _retryCount?: number };

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("token");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
      return Promise.reject(err);
    }

    const config = err.config as RetryableConfig | undefined;
    const status = err.response?.status;
    // Only retry idempotent GETs on server errors -- retrying POST/PATCH
    // (upload, train, label) on a 5xx risks duplicate side effects.
    const isServerError = typeof status === "number" && status >= 500;
    const isGet = (config?.method ?? "get").toLowerCase() === "get";
    if (config && isServerError && isGet) {
      config._retryCount = (config._retryCount ?? 0) + 1;
      if (config._retryCount <= MAX_RETRIES) {
        await wait(RETRY_BASE_DELAY_MS * 2 ** (config._retryCount - 1));
        return api(config);
      }
    }
    return Promise.reject(err);
  },
);

export default api;

export function errorMessage(
  err: unknown,
  fallback?: string,
): string | undefined {
  if (axios.isAxiosError<{ detail?: string }>(err)) {
    return err.response?.data?.detail ?? fallback;
  }
  return fallback;
}

export function isCancelled(err: unknown): boolean {
  return axios.isCancel(err);
}

type RequestOpts = { signal?: AbortSignal };

export type Profile = {
  n_rows: number;
  n_features: number;
  autocorr_lag1?: number | null;
  adf_pvalue?: number | null;
  fft_peak?: number | null;
  column_stats?: Record<
    string,
    { mean: number; std: number; min: number; max: number }
  >;
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

export type ModelMetrics = {
  error?: string;
  val_score_min?: number;
  val_score_max?: number;
  val_score_mean?: number;
  n_train_samples?: number;
  n_val_samples?: number;
};

export type ModelInfo = {
  id: number;
  dataset_id: number;
  subject_id: number;
  algorithm: "IF" | "LSTM";
  status: "pending" | "training" | "ready" | "failed";
  selection_reason: string | null;
  trained_at: string | null;
  drift_status: string;
  metrics: ModelMetrics;
  threshold: Threshold | null;
};

export type Anomaly = {
  id: number;
  prediction_id: number;
  model_id: number;
  subject_id: number;
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
  results: {
    batch_id: string;
    window_idx: number;
    score: number;
    is_anomaly: boolean;
  }[];
};

export type SplitOptions = {
  n_rows: number;
  candidate_id_columns: { column: string; n_unique: number; example_values: string[] }[];
  candidate_time_columns: { column: string; sample_range: [string, string] }[];
};

export type AnalyzeResult = {
  temp_id: string;
  n_rows: number;
  n_features: number;
  columns: string[];
  split_options: SplitOptions;
  profile: Profile;
};

export type SplitPeriod = "hourly" | "daily" | "weekly" | "monthly";

export type SplitConfig =
  | { mode: "none" }
  | { mode: "by_column"; column: string }
  | { mode: "by_time"; column: string; period: SplitPeriod };

export type CommitBody = {
  temp_id: string;
  target: "new" | "existing";
  subject_name?: string;
  subject_description?: string;
  subject_id?: number;
  split: SplitConfig;
};

export type CommitResult = {
  subject_ids: number[];
  dataset_ids: number[];
  training_queued: boolean;
};

export type Subject = {
  id: number;
  name: string;
  description: string | null;
  source_hint: string | null;
  is_default: boolean;
  created_at: string;
  n_datasets: number;
  n_models: number;
  n_anomalies: number;
  active_epsilon: number | null;
  active_algorithm: string | null;
};

export type SubjectDataset = {
  id: number;
  name: string;
  n_rows: number | null;
  n_features: number | null;
  uploaded_at: string;
};

export type SubjectModel = {
  id: number;
  algorithm: string;
  selection_reason: string | null;
  selection_mode: "auto" | "manual";
  status: string;
  is_active: boolean;
  trained_at: string | null;
  threshold: Threshold | null;
};

export type SubjectDetail = Subject & {
  datasets: SubjectDataset[];
  models: SubjectModel[];
};

export const auth = {
  register: (email: string, password: string) =>
    api.post("/auth/register", { email, password }),
  login: (email: string, password: string) =>
    api.post<{ access_token: string; token_type: string }>("/auth/login", {
      email,
      password,
    }),
  me: () => api.get<{ id: number; email: string }>("/auth/me"),
};

export const datasets = {
  upload: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return api.post<{
      dataset_id: number;
      name: string;
      n_rows: number;
      n_features: number;
      profile: Profile;
    }>("/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
  },
  list: () => api.get<Dataset[]>("/upload"),
  analyze: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return api.post<AnalyzeResult>("/upload/analyze", fd, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  commit: (body: CommitBody) => api.post<CommitResult>("/upload/commit", body),
};

export const subjects = {
  list: (opts?: RequestOpts) => api.get<Subject[]>("/subjects", { signal: opts?.signal }),
  create: (name: string, description?: string) =>
    api.post<Subject>("/subjects", { name, description }),
  detail: (id: number, opts?: RequestOpts) =>
    api.get<SubjectDetail>(`/subjects/${id}`, { signal: opts?.signal }),
  update: (id: number, data: { name?: string; description?: string }) =>
    api.patch<Subject>(`/subjects/${id}`, data),
  delete: (id: number) => api.delete(`/subjects/${id}`),
  retrain: (id: number) =>
    api.post<{ model_id: number; old_epsilon: number | null; new_epsilon: number; delta_pct: number | null }>(
      `/subjects/${id}/retrain`,
    ),
  trainAlternative: (id: number, algorithm: "IF" | "LSTM") =>
    api.post<{ model_id: number; algorithm: string; epsilon: number }>(`/subjects/${id}/train-alternative`, {
      algorithm,
    }),
  activateModel: (subjectId: number, modelId: number) =>
    api.post<SubjectModel>(`/subjects/${subjectId}/models/${modelId}/activate`),
};

export const models = {
  train: (datasetId: number) =>
    api.post<{ status: string; algorithm_chosen: string; reason: string }>(
      `/train/${datasetId}`,
    ),
  list: (opts?: RequestOpts) =>
    api.get<ModelInfo[]>("/train/models", { signal: opts?.signal }),
  predict: (modelId: number, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return api.post<PredictResult>(`/predict/${modelId}`, fd, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
};

export const anomalies = {
  list: (
    params?: { model_id?: number; label?: string; limit?: number },
    opts?: RequestOpts,
  ) => api.get<Anomaly[]>("/anomalies", { params, signal: opts?.signal }),
  label: (eventId: number, label: string, note?: string) =>
    api.patch<Anomaly>(`/anomalies/${eventId}`, { label, note }),
};

export const thresholds = {
  get: (modelId: number) =>
    api.get<Threshold & { calibrated_at: string }>(
      `/settings/threshold/${modelId}`,
    ),
  update: (modelId: number, z: number) =>
    api.patch<Threshold & { calibrated_at: string }>(
      `/settings/threshold/${modelId}`,
      {
        z_multiplier: z,
      },
    ),
};
