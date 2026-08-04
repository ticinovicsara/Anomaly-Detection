"""Rule-based router: pick the model based on data profile.

Returns (algorithm, human_readable_reason). The reason is stored in
`models.selection_reason` so the user can see WHY a model was chosen.
"""
from typing import Dict, Tuple


def choose_model(profile: Dict) -> Tuple[str, str]:
    n = int(profile.get("n_rows") or 0)
    dim = int(profile.get("n_features") or 0)
    ac = profile.get("autocorr_lag1")
    fft = profile.get("fft_peak")

    # Coerce None to sentinels so comparisons never crash
    ac = 0.0 if ac is None else float(ac)
    fft = 0.0 if fft is None else float(fft)

    # 1. Datasets too small to train LSTM properly → IF
    if n < 500:
        return "IF", f"Small dataset ({n} rows, need at least 500 for LSTM) → Isolation Forest"

    # 2. High-dimensional tabular data with weak temporal signal (e.g. Credit Card) → IF
    if ac < 0.3 and dim > 10:
        return (
            "IF",
            f"High-dimensional tabular data ({dim} features, autocorr={ac:.2f}) → Isolation Forest",
        )

    # 3. Strong temporal structure (e.g. ECG) → LSTM
    if ac > 0.5:
        return (
            "LSTM",
            f"Strong temporal structure (autocorr={ac:.2f}) → LSTM Autoencoder",
        )

    # 4. Detected periodic pattern (e.g. server metrics) → LSTM
    if fft > 0.01:
        return (
            "LSTM",
            f"Periodic pattern detected (FFT peak={fft:.3f}) → LSTM Autoencoder",
        )

    # 5. Safe default
    return "IF", "No strong sequential signal detected → Isolation Forest (default)"
