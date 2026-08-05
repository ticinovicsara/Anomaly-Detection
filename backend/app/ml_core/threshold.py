from typing import Dict

import numpy as np


def calibrate_threshold(val_scores: np.ndarray, z: float = 3.0) -> Dict[str, float]:
    """Personalized threshold from validation reconstruction/anomaly scores.

    Uses the three-sigma rule: epsilon = mu + z * sigma.
    Returns mu, sigma, epsilon, z_multiplier so the caller can recompute
    epsilon later without needing to re-score the validation set.
    """
    if val_scores.size == 0:
        raise ValueError("Cannot calibrate threshold on empty score array")
    mu = float(np.mean(val_scores))
    sigma = float(np.std(val_scores))
    epsilon = mu + z * sigma
    return {"mu": mu, "sigma": sigma, "epsilon": float(epsilon), "z_multiplier": float(z)}


def recompute_epsilon(mu: float, sigma: float, z: float) -> float:
    return float(mu + z * sigma)
