import axios, { AxiosRequestConfig } from "axios";
import type { components } from "@/types/api.generated";
import type {
  AnalyzeResult,
  Anomaly,
  CommitBody,
  CommitResult,
  Dataset,
  DataReviewCandidate,
  EvaluationSummary,
  ExperimentResult,
  ModelInfo,
  PredictResult,
  PresetDemoResult,
  Profile,
  RetrainReviewRequired,
  Subject,
  SubjectDetail,
  SubjectModel,
  ThresholdResource,
} from "./types";

export * from "./types";

// Single source of truth for request timeouts -- override per-call with
// `{ timeout: REQUEST_TIMEOUT_MS }` (or a multiple of it) rather than a
// new hardcoded number, so every override moves together if this changes.
export const REQUEST_TIMEOUT_MS = 120000000;

const api = axios.create({
  baseURL: "/api",
  timeout: REQUEST_TIMEOUT_MS,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Dev-visibility logging -- every request/response goes to the browser
// console so app behavior (training kicked off, polling, failures) is
// visible without attaching a debugger.
api.interceptors.request.use((config) => {
  console.log(
    `%c→ ${(config.method ?? "get").toUpperCase()} ${config.url}`,
    "color:#60a5fa",
    config.params ?? config.data ?? "",
  );
  return config;
});

const MAX_RETRIES = 3;
const RETRY_BASE_DELAY_MS = 300;

type RetryableConfig = AxiosRequestConfig & { _retryCount?: number };

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

api.interceptors.response.use(
  (r) => {
    console.log(`%c← ${r.status} ${r.config.url}`, "color:#4ade80", r.data);
    return r;
  },
  async (err) => {
    console.error(
      `%c✕ ${err.response?.status ?? "ERR"} ${err.config?.url}`,
      "color:#f87171",
      err.response?.data ?? err.message,
    );
    if (err.response?.status === 401) {
      localStorage.removeItem("token");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
      return Promise.reject(err);
    }

    const config = err.config as RetryableConfig | undefined;
    const status = err.response?.status;
    // Only idempotent GETs: retrying a POST/PATCH on 5xx risks duplicate side effects.
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
  if (axios.isAxiosError<{ detail?: string | RetrainReviewRequired }>(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "message" in detail)
      return detail.message;
    return fallback;
  }
  return fallback;
}

// Pulls the structured detail out of a blocked /retrain (422) response.
export function reviewRequired(
  err: unknown,
): RetrainReviewRequired | undefined {
  if (
    axios.isAxiosError<{ detail?: string | RetrainReviewRequired }>(err) &&
    err.response?.status === 422 &&
    err.response?.data?.detail &&
    typeof err.response.data.detail === "object"
  ) {
    return err.response.data.detail as RetrainReviewRequired;
  }
  return undefined;
}

export function isCancelled(err: unknown): boolean {
  return axios.isCancel(err);
}

type RequestOpts = { signal?: AbortSignal };

export const auth = {
  register: (email: string, password: string) =>
    api.post("/auth/register", { email, password }),
  login: (email: string, password: string) =>
    api.post<components["schemas"]["TokenOut"]>("/auth/login", {
      email,
      password,
    }),
  me: () => api.get<components["schemas"]["UserOut"]>("/auth/me"),
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
  // Large CSVs (autocorrelation/FFT/ADF stationarity over every numeric
  // column) can take a while -- explicit here (same value as the api
  // default today) so it stays correct if the shared default ever drops.
  analyze: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return api.post<AnalyzeResult>("/upload/analyze", fd, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: REQUEST_TIMEOUT_MS,
    });
  },
  commit: (body: CommitBody) =>
    api.post<CommitResult>("/upload/commit", body, {
      timeout: REQUEST_TIMEOUT_MS,
    }),
};

export const subjects = {
  list: (opts?: RequestOpts) =>
    api.get<Subject[]>("/subjects", { signal: opts?.signal }),
  create: (name: string, description?: string) =>
    api.post<Subject>("/subjects", { name, description }),
  detail: (id: number, opts?: RequestOpts) =>
    api.get<SubjectDetail>(`/subjects/${id}`, { signal: opts?.signal }),
  update: (id: number, data: components["schemas"]["SubjectUpdate"]) =>
    api.patch<Subject>(`/subjects/${id}`, data),
  delete: (id: number) => api.delete(`/subjects/${id}`),
  retrain: (id: number, force = false) =>
    api.post<components["schemas"]["RetrainOut"]>(
      `/subjects/${id}/retrain`,
      undefined,
      { params: force ? { force: true } : undefined },
    ),
  trainAlternative: (id: number, algorithm: "IF" | "LSTM") =>
    api.post<components["schemas"]["TrainAlternativeOut"]>(
      `/subjects/${id}/train-alternative`,
      {
        algorithm,
      },
    ),
  activateModel: (subjectId: number, modelId: number) =>
    api.post<SubjectModel>(`/subjects/${subjectId}/models/${modelId}/activate`),
};

export const dataReview = {
  precheck: (subjectId: number) =>
    api.post<DataReviewCandidate[]>(
      `/subjects/${subjectId}/data-review/precheck`,
    ),
  list: (subjectId: number, opts?: RequestOpts) =>
    api.get<DataReviewCandidate[]>(
      `/subjects/${subjectId}/data-review/candidates`,
      { signal: opts?.signal },
    ),
  label: (
    subjectId: number,
    candidateId: number,
    label: "confirmed" | "false_positive" | "unlabeled",
  ) =>
    api.patch<DataReviewCandidate>(
      `/subjects/${subjectId}/data-review/candidates/${candidateId}`,
      { label },
    ),
};

export const experiments = {
  run: (subjectIds: number[]) =>
    api.post<ExperimentResult>("/experiments/personalization", {
      subject_ids: subjectIds,
    }),
  presetDemo: () => api.post<PresetDemoResult>("/experiments/preset-demo"),
  evaluationSummary: (opts?: RequestOpts) =>
    api.get<EvaluationSummary>("/experiments/evaluation-summary", {
      signal: opts?.signal,
    }),
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
    params?: {
      model_id?: number;
      subject_id?: number;
      label?: string;
      limit?: number;
    },
    opts?: RequestOpts,
  ) => api.get<Anomaly[]>("/anomalies", { params, signal: opts?.signal }),
  label: (eventId: number, label: string, note?: string) =>
    api.patch<Anomaly>(`/anomalies/${eventId}`, { label, note }),
};

export const thresholds = {
  get: (modelId: number) =>
    api.get<ThresholdResource>(`/settings/threshold/${modelId}`),
  update: (modelId: number, z: number) =>
    api.patch<ThresholdResource>(`/settings/threshold/${modelId}`, {
      z_multiplier: z,
    }),
};
