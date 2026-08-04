import numpy as np

from app.ml_core.models.base import AnomalyModel


class LSTMAutoencoder(AnomalyModel):
    """LSTM Autoencoder trained on normal sequential windows.

    TensorFlow is imported lazily so unit tests that only need Isolation Forest
    do not pay the ~2-second TensorFlow import cost.
    """

    algorithm = "LSTM"

    def __init__(self, window_size: int = 50, n_features: int = 1, latent_dim: int = 32):
        self.window_size = window_size
        self.n_features = n_features
        self.latent_dim = latent_dim
        self.model = self._build()

    def _build(self):
        import tensorflow as tf
        from tensorflow.keras import layers, models

        inp = layers.Input(shape=(self.window_size, self.n_features))
        encoded = layers.LSTM(self.latent_dim, activation="tanh")(inp)
        repeated = layers.RepeatVector(self.window_size)(encoded)
        decoded = layers.LSTM(self.latent_dim, activation="tanh", return_sequences=True)(repeated)
        output = layers.TimeDistributed(layers.Dense(self.n_features))(decoded)
        model = models.Model(inp, output)
        model.compile(optimizer="adam", loss="mae")
        return model

    def train(self, X: np.ndarray, epochs: int = 20, batch_size: int = 64, verbose: int = 0) -> None:
        X = X.astype("float32")
        self.model.fit(X, X, epochs=epochs, batch_size=batch_size, verbose=verbose)

    def score(self, X: np.ndarray) -> np.ndarray:
        X = X.astype("float32")
        recon = self.model.predict(X, verbose=0)
        # MAE per window, averaged over timesteps and features
        return np.mean(np.abs(X - recon), axis=(1, 2))

    def save(self, path: str) -> None:
        self.model.save(path)

    def load(self, path: str) -> None:
        import tensorflow as tf
        self.model = tf.keras.models.load_model(path)
