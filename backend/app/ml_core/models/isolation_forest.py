import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from app.ml_core.models.base import AnomalyModel


class IFModel(AnomalyModel):
    algorithm = "IF"

    def __init__(self, contamination: float = 0.01, n_estimators: int = 100, random_state: int = 42):
        self.contamination = contamination
        self.model = IsolationForest(
            n_estimators=n_estimators,
            contamination=contamination,
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
