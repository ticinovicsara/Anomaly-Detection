import type { components } from "@/types/api.generated";

// Most types below alias the generated OpenAPI schema (npm run
// generate:types, see frontend/README.md). Endpoints with no
// response_model (see note further down) stay hand-written.

// --- No backend response_model for these -- hand-written, see note above ---

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

export type Confusion = components["schemas"]["ConfusionOut"];
export type CurvePoint = components["schemas"]["CurvePointOut"];
export type Evaluation = components["schemas"]["EvaluationOut"];

export type ModelMetrics = {
  error?: string;
  val_score_min?: number;
  val_score_max?: number;
  val_score_mean?: number;
  n_train_samples?: number;
  n_val_samples?: number;
  evaluation?: Evaluation | null;
};

export type ModelInfo = {
  id: number;
  dataset_id: number;
  subject_id: number;
  algorithm: "IF" | "LSTM";
  status: "pending" | "training" | "ready" | "failed";
  selection_reason: string | null;
  selection_mode: "auto" | "manual";
  is_active: boolean;
  trained_at: string | null;
  drift_status: string;
  metrics: ModelMetrics;
  threshold: Threshold | null;
};

export type PredictResult = {
  batch_id: string;
  model_id: number;
  algorithm: string;
  threshold: number;
  total_windows: number;
  anomaly_count: number;
  anomaly_rate: number;
  has_labels: boolean;
  results: {
    batch_id: string;
    window_idx: number;
    score: number;
    is_anomaly: boolean;
    actual: number | null;
  }[];
};

export type PredictBatchSummary = components["schemas"]["PredictBatchSummaryOut"];
export type PredictBatchDetail = components["schemas"]["PredictBatchDetailOut"];

export type SplitOptions = {
  n_rows: number;
  candidate_id_columns: { column: string; n_unique: number; example_values: string[] }[];
  candidate_time_columns: { column: string; sample_range: [string, string] }[];
  candidate_label_columns: { column: string; example_values: string[]; minority_ratio: number }[];
};

export type AnalyzeResult = {
  temp_id: string;
  n_rows: number;
  n_features: number;
  columns: string[];
  split_options: SplitOptions;
  profile: Profile;
};

export type CommitResult = {
  subject_ids: number[];
  dataset_ids: number[];
  training_queued: boolean;
};

// Opaque exception detail, not in OpenAPI -- stays hand-written.
export type RetrainReviewRequired = {
  message: string;
  pending_candidates: DataReviewCandidate[];
};

// --- Derived from app/api/*.py response_model schemas ---

export type Dataset = components["schemas"]["DatasetOut"];
export type SubjectDataset = components["schemas"]["DatasetOut"];

// Two legitimately different ThresholdOut shapes on the backend (subjects.py vs settings.py).
export type Threshold = components["schemas"]["app__api__subjects__ThresholdOut"];
export type ThresholdResource = components["schemas"]["app__api__settings__ThresholdOut"];

export type Anomaly = components["schemas"]["AnomalyOut"];

export type Subject = components["schemas"]["SubjectOut"];

export type DataReviewCandidate = Omit<components["schemas"]["DataReviewCandidateOut"], "row_preview" | "label"> & {
  row_preview: Record<string, number>;
  label: "unlabeled" | "confirmed" | "false_positive";
};

export type SubjectModel = components["schemas"]["ModelOut"];
export type SubjectDetail = components["schemas"]["SubjectDetailOut"];
export type ThresholdHistoryEntry = components["schemas"]["ThresholdHistoryOut"];

export type ExperimentStatistics = components["schemas"]["StatisticsOut"];
export type CrossApplication = components["schemas"]["CrossApplicationOut"];
export type ExperimentResult = components["schemas"]["ExperimentOut"];
export type PresetDemoResult = components["schemas"]["PresetDemoOut"];
export type EvaluationSummary = components["schemas"]["EvaluationSummaryOut"];

export type SplitPeriod = "hourly" | "daily" | "weekly" | "monthly";

export type SplitConfig =
  | { mode: "none" }
  | { mode: "by_column"; column: string }
  | { mode: "by_time"; column: string; period: SplitPeriod };

export type CommitBody = Omit<components["schemas"]["CommitIn"], "target" | "split" | "algorithm"> & {
  target: "new" | "existing";
  split: SplitConfig;
  algorithm?: "IF" | "LSTM";
};
