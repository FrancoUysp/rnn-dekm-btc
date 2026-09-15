import pandas as pd
import numpy as np
import tensorflow as tf
from sklearn.cluster import KMeans
import pickle
import os
import ta


class DEKM_RNN:
    """
    Deep Embedded K-Means with RNN Autoencoder for clustering time series data.
    """

    def __init__(self, sequence_length=60):
        """
        Initialize the DEKM_RNN model.

        Parameters:
            sequence_length (int): The length of the input sequences for the RNN encoder.
        """
        self.models_dir = os.path.join(os.path.dirname(__file__), "..", "..", "models")
        self.scaler_path = os.path.join(self.models_dir, "scaler_rnn.pkl")
        self.rnn_weights_file = os.path.join(
            self.models_dir, "rnn_autoencoder.weights.h5"
        )
        self.sequence_length = sequence_length

        self.scaler = self.load_scaler(self.scaler_path)

        self.encoder = self.load_rnn_encoder(
            self.sequence_length,
            input_dim=self.scaler.n_features_in_,
            weights_file=self.rnn_weights_file,
        )

    def load_scaler(self, file_name):
        """
        Load the StandardScaler from a pickle file.

        Parameters:
            file_name (str): The path to the scaler pickle file.

        Returns:
            StandardScaler: The loaded StandardScaler object.
        """
        with open(file_name, "rb") as f:
            scaler = pickle.load(f)
        print(f"Scaler loaded from {file_name}")
        return scaler

    def load_rnn_encoder(self, sequence_length, input_dim, weights_file):
        """
        Build and load weights into the RNN encoder.

        Parameters:
            sequence_length (int): The length of the input sequences.
            input_dim (int): The number of features in the input data.
            weights_file (str): The path to the weights file.

        Returns:
            Model: The loaded RNN encoder model.
        """
        encoder = self.build_rnn_encoder(
            sequence_length=sequence_length, input_dim=input_dim
        )
        if os.path.exists(weights_file):
            encoder.load_weights(weights_file)
            print(f"Loaded RNN encoder weights from {weights_file}")
        else:
            raise FileNotFoundError(f"RNN weights file {weights_file} not found.")
        return encoder

    def build_rnn_encoder(self, sequence_length, input_dim, latent_dim=16):
        """
        Build the RNN encoder model architecture.

        Parameters:
            sequence_length (int): The length of the input sequences.
            input_dim (int): The number of features in the input data.
            latent_dim (int, optional): The dimension of the latent space. Defaults to 16.

        Returns:
            Model: The RNN encoder model.
        """
        inputs = tf.keras.layers.Input(shape=(sequence_length, input_dim))
        x = tf.keras.layers.GRU(32, activation="relu", return_sequences=True)(inputs)
        x = tf.keras.layers.GRU(16, activation="relu")(x)
        encoded = tf.keras.layers.Dense(latent_dim, activation="relu", name="encoded")(
            x
        )
        encoder_model = tf.keras.Model(inputs=inputs, outputs=encoded)
        return encoder_model

    def resample_candlestick_data(self, df, frequency="5T"):
        """
        Resample candlestick data to a specified frequency.

        Parameters:
            df (DataFrame): The original candlestick data.
            frequency (str, optional): The frequency to resample the data to. Defaults to '5T' (5 minutes).

        Returns:
            DataFrame: The resampled candlestick data.
        """
        df_resampled = df.copy()
        df_resampled.set_index("datetime", inplace=True)
        df_resampled.index = pd.to_datetime(df_resampled.index)
        df_resampled = (
            df_resampled.resample(frequency)
            .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
            .dropna()
        )
        df_resampled.reset_index(inplace=True)
        return df_resampled

    def extract_features(self, data):
        """
        Extract technical indicators as features from the data.

        Parameters:
            data (DataFrame): The input data containing 'open', 'high', 'low', 'close' prices.

        Returns:
            DataFrame: The extracted features dataframe.
        """
        WINDOWS = {"long": 200, "medium": 100, "short": 50}
        features = {}
        for window_name, window_size in WINDOWS.items():
            close = data["close"]
            high = data["high"]
            low = data["low"]

            ema_indicator = ta.trend.EMAIndicator(close=close, window=window_size)
            ema = ema_indicator.ema_indicator()

            sma_indicator = ta.trend.SMAIndicator(close=close, window=window_size)
            sma = sma_indicator.sma_indicator()

            macd_indicator = ta.trend.MACD(
                close=close,
                window_slow=window_size,
                window_fast=window_size // 2,
                window_sign=window_size // 3,
            )
            macd = macd_indicator.macd()

            rsi_indicator = ta.momentum.RSIIndicator(close=close, window=window_size)
            rsi = rsi_indicator.rsi()

            momentum = rsi - rsi

            proc_indicator = ta.momentum.ROCIndicator(close=close, window=window_size)
            proc = proc_indicator.roc()

            stoch_indicator = ta.momentum.StochasticOscillator(
                high=high,
                low=low,
                close=close,
                window=window_size,
                smooth_window=window_size // 3,
            )
            stoch_k = stoch_indicator.stoch()

            cci_indicator = ta.trend.CCIIndicator(
                high=high, low=low, close=close, window=window_size
            )
            cci = cci_indicator.cci()

            atr_indicator = ta.volatility.AverageTrueRange(
                high=high, low=low, close=close, window=window_size
            )
            atr = atr_indicator.average_true_range()

            bollinger = ta.volatility.BollingerBands(
                close=close, window=window_size, window_dev=2
            )
            upperband = bollinger.bollinger_hband()
            lowerband = bollinger.bollinger_lband()

            features[f"EMA_{window_name}"] = (ema - close) / close
            features[f"SMA_{window_name}"] = (sma - close) / close
            features[f"MACD_{window_name}"] = (macd - close) / close
            features[f"RSI_{window_name}"] = (rsi - close) / close
            features[f"Momentum_{window_name}"] = (momentum - close) / close
            features[f"PROC_{window_name}"] = (proc - close) / close
            features[f"Stochastic_K_{window_name}"] = (stoch_k - close) / close
            features[f"CCI_{window_name}"] = (cci - close) / close
            features[f"ATR_{window_name}"] = (atr - close) / close
            features[f"Bollinger_Upper_{window_name}"] = (upperband - close) / close
            features[f"Bollinger_Lower_{window_name}"] = (lowerband - close) / close

            features[f"EMA_diff_{window_name}"] = (ema.diff() - close) / close
            features[f"SMA_diff_{window_name}"] = (sma.diff() - close) / close
            features[f"MACD_diff_{window_name}"] = (macd.diff() - close) / close
            features[f"RSI_diff_{window_name}"] = (rsi.diff() - close) / close
            features[f"Momentum_diff_{window_name}"] = (momentum.diff() - close) / close
            features[f"PROC_diff_{window_name}"] = (proc.diff() - close) / close
            features[f"Stochastic_K_diff_{window_name}"] = (
                stoch_k.diff() - close
            ) / close
            features[f"CCI_diff_{window_name}"] = (cci.diff() - close) / close
            features[f"ATR_diff_{window_name}"] = (atr.diff() - close) / close
            features[f"Bollinger_Upper_diff_{window_name}"] = (
                upperband.diff() - close
            ) / close
            features[f"Bollinger_Lower_diff_{window_name}"] = (
                lowerband.diff() - close
            ) / close

        features_df = pd.DataFrame(features, index=data.index)
        features_df.dropna(inplace=True)
        return features_df

    def transform_data(self, data):
        """
        Transform the input data by resampling, extracting features, and scaling.

        Parameters:
            data (DataFrame): The input data containing 'datetime', 'open', 'high', 'low', 'close'.

        Returns:
            tuple: A tuple containing:
                - data_scaled (ndarray): The scaled feature data.
                - feature_index (Index): The index corresponding to the scaled data.
        """
        data_resampled = data.copy()
        data_resampled.set_index("datetime", inplace=True)

        features_df = self.extract_features(data_resampled)

        features_df.dropna(inplace=True)
        if features_df.empty:
            return None, None

        data_scaled = self.scaler.transform(features_df.values)

        return data_scaled, features_df.index

    def create_sequences(self, data_scaled):
        """
        Create sequences from the scaled data for RNN input.

        Parameters:
            data_scaled (ndarray): The scaled feature data.

        Returns:
            ndarray: The array of sequences for RNN input.
        """
        num_sequences = len(data_scaled) - self.sequence_length + 1
        if num_sequences <= 0:
            return np.array([])
        sequences = np.array(
            [data_scaled[i : i + self.sequence_length] for i in range(num_sequences)]
        )
        return sequences

    def predict(self, data):
        """
        Predict clusters for the input data.

        Parameters:
            data (DataFrame): The input data containing 'datetime', 'open', 'high', 'low', 'close'.

        Returns:
            DataFrame: The input data with an additional 'cluster' column.
        """
        data_scaled, feature_index = self.transform_data(data)
        if data_scaled is None:
            data["cluster"] = np.nan
            return data

        sequences = self.create_sequences(data_scaled)
        if sequences.size == 0:
            data["cluster"] = np.nan
            return data

        latent_representations = self.encoder.predict(sequences)

        kmeans = KMeans(n_clusters=2, random_state=42)
        kmeans.fit(latent_representations)
        clusters = kmeans.labels_

        cluster_indices = feature_index[self.sequence_length - 1 :]
        cluster_df = pd.DataFrame({"datetime": cluster_indices, "cluster": clusters})
        cluster_df.set_index("datetime", inplace=True)

        data.set_index("datetime", inplace=True)
        data["cluster"] = np.nan

        data.update(cluster_df)

        data.reset_index(inplace=True)

        return data
