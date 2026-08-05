from abc import ABC, abstractmethod

import numpy as np


class AnomalyModel(ABC):
    """Common interface for every anomaly detection model."""

    algorithm: str = "base"

    @abstractmethod
    def train(self, X: np.ndarray) -> None:
        ...

    @abstractmethod
    def score(self, X: np.ndarray) -> np.ndarray:
        """Return a 1-D array of anomaly scores. Higher = more anomalous."""
        ...

    @abstractmethod
    def save(self, path: str) -> None:
        ...

    @abstractmethod
    def load(self, path: str) -> None:
        ...
