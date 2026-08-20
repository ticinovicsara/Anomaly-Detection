import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from app.ml_core.models.base import AnomalyModel


class IFModel(AnomalyModel):
    algorithm = "IF"

    def __init__(self, n_estimators: int = 100, random_state: int = 42):
        # No `contamination` param: this class only ever calls score_samples()
        # (see score() below), which sklearn computes independently of
        # contamination -- that knob only shifts the offset used by
        # decision_function()/predict(), which we never call. The real
        # anomaly cutoff is the calibrated epsilon (threshold.py), not this.
        self.model = IsolationForest(
            n_estimators=n_estimators,
            random_state=random_state,
            n_jobs=-1,
        )

    def train(self, X: np.ndarray) -> None:
        self.model.fit(X)

    def score(self, X: np.ndarray) -> np.ndarray:
        # score_samples returns log-density; negate so higher = more anomalous
        return -self.model.score_samples(X)

    def save(self, path: str) -> None:
        joblib.dump(self.model, path)

    def load(self, path: str) -> None:
        self.model = joblib.load(path)
