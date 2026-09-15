import numpy as np
import tensorflow as tf
from tensorflow.keras import layers, regularizers, Model, losses
from tensorflow.keras.callbacks import EarlyStopping
from sklearn.cluster import KMeans, SpectralClustering
from sklearn.metrics import silhouette_score, davies_bouldin_score
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from scipy.optimize import linear_sum_assignment as linear_assignment
import matplotlib.pyplot as plt
import os
import time
import csv
from tqdm import tqdm
import pickle
import pandas as pd
import talib
import argparse
from sklearn.mixture import GaussianMixture
from tensorflow.keras.models import load_model
from sklearn.neighbors import kneighbors_graph

WINDOWS = {
    "long": 60,  # 30 minutes
    "medium": 20,
    "short": 5,  # 10 minutes
}
PATH = os.path.join("..", "data", "combined.csv")


def get_data(file_loc, n=None):
    "Used to read main.csv etc"
    if n is None:
        data = pd.read_csv(file_loc)
    else:
        data = pd.read_csv(file_loc, nrows=n)

    data["datetime"] = pd.to_datetime(
        data["datetime"], format="%Y-%m-%d %H:%M:%S", errors="coerce"
    )

    data.dropna(inplace=True, axis=0)

    data.columns = data.columns.str.lower()

    data = data.sort_values(by=["datetime"])

    if "volume" in data.columns:
        data.drop("volume", axis=1, inplace=True)

    return data


def extract_features(data):
    features = {}
    for window_name, window_size in WINDOWS.items():
        ema = talib.EMA(data["close"], timeperiod=window_size)
        sma = talib.SMA(data["close"], timeperiod=window_size)
        macd, macdsignal, macdhist = talib.MACD(
            data["close"],
            fastperiod=window_size // 2,
            slowperiod=window_size,
            signalperiod=window_size // 3,
        )
        rsi = talib.RSI(data["close"], timeperiod=window_size)
        momentum = talib.MOM(data["close"], timeperiod=window_size)
        proc = talib.ROCP(data["close"], timeperiod=window_size)
        stoch_k, stoch_d = talib.STOCH(
            data["high"],
            data["low"],
            data["close"],
            fastk_period=window_size,
            slowk_period=window_size // 3,
            slowd_period=window_size // 3,
        )
        cci = talib.CCI(
            data["high"], data["low"], data["close"], timeperiod=window_size
        )
        atr = talib.ATR(
            data["high"], data["low"], data["close"], timeperiod=window_size
        )
        upperband, middleband, lowerband = talib.BBANDS(
            data["close"], timeperiod=window_size, nbdevup=2, nbdevdn=2, matype=0
        )

        # Standardize features with respect to the closing price
        features[f"EMA_{window_name}"] = (ema - data["close"]) / data["close"]
        features[f"SMA_{window_name}"] = (sma - data["close"]) / data["close"]
        features[f"MACD_{window_name}"] = (macd - data["close"]) / data["close"]
        features[f"RSI_{window_name}"] = (rsi - data["close"]) / data["close"]
        features[f"Momentum_{window_name}"] = (momentum - data["close"]) / data["close"]
        features[f"PROC_{window_name}"] = (proc - data["close"]) / data["close"]
        features[f"Stochastic_K_{window_name}"] = (stoch_k - data["close"]) / data[
            "close"
        ]
        features[f"CCI_{window_name}"] = (cci - data["close"]) / data["close"]
        features[f"ATR_{window_name}"] = (atr - data["close"]) / data["close"]
        features[f"Bollinger_Upper_{window_name}"] = (upperband - data["close"]) / data[
            "close"
        ]
        features[f"Bollinger_Lower_{window_name}"] = (lowerband - data["close"]) / data[
            "close"
        ]

        # Difference features
        features[f"EMA_diff_{window_name}"] = (
            np.diff(ema, prepend=np.nan) - data["close"]
        ) / data["close"]
        features[f"SMA_diff_{window_name}"] = (
            np.diff(sma, prepend=np.nan) - data["close"]
        ) / data["close"]
        features[f"MACD_diff_{window_name}"] = (
            np.diff(macd, prepend=np.nan) - data["close"]
        ) / data["close"]
        features[f"RSI_diff_{window_name}"] = (
            np.diff(rsi, prepend=np.nan) - data["close"]
        ) / data["close"]
        features[f"Momentum_diff_{window_name}"] = (
            np.diff(momentum, prepend=np.nan) - data["close"]
        ) / data["close"]
        features[f"PROC_diff_{window_name}"] = (
            np.diff(proc, prepend=np.nan) - data["close"]
        ) / data["close"]
        features[f"Stochastic_K_diff_{window_name}"] = (
            np.diff(stoch_k, prepend=np.nan) - data["close"]
        ) / data["close"]
        features[f"CCI_diff_{window_name}"] = (
            np.diff(cci, prepend=np.nan) - data["close"]
        ) / data["close"]
        features[f"ATR_diff_{window_name}"] = (
            np.diff(atr, prepend=np.nan) - data["close"]
        ) / data["close"]
        features[f"Bollinger_Upper_diff_{window_name}"] = (
            np.diff(upperband, prepend=np.nan) - data["close"]
        ) / data["close"]
        features[f"Bollinger_Lower_diff_{window_name}"] = (
            np.diff(lowerband, prepend=np.nan) - data["close"]
        ) / data["close"]

    features_df = pd.DataFrame(features, index=data.index)
    features_df.dropna(inplace=True)

    return features_df


def create_model_df(data):
    # Extract features
    print("### data before feature extract ###")
    print(data.head())
    features = extract_features(data.copy())

    # Align the OHLC data with the features dataframe
    ohlc_data = data.loc[features.index, ["datetime", "open", "high", "low", "close"]]

    model_df = features
    model_df.dropna(inplace=True)
    ohlc_data.dropna(inplace=True)
    print("### data after feature extract ###")
    print(model_df.head())

    return model_df, ohlc_data


def create_datasets(df, batch_size=256, validation_split=0.2, shuffle_seed=None):
    # Split into training and validation sets
    train_df, val_df = train_test_split(
        df, test_size=validation_split, random_state=shuffle_seed
    )

    # Initialize the scaler
    scaler = StandardScaler()

    # Fit the scaler on the training data and transform both training and validation sets
    train_df_scaled = scaler.fit_transform(train_df)
    val_df_scaled = scaler.transform(val_df)

    # Convert back to DataFrame for consistency
    train_df_scaled = pd.DataFrame(train_df_scaled, columns=train_df.columns)
    val_df_scaled = pd.DataFrame(val_df_scaled, columns=val_df.columns)

    # Create tf.data.Dataset objects
    ds_xx = (
        tf.data.Dataset.from_tensor_slices(
            (train_df_scaled.values, train_df_scaled.values)
        )
        .shuffle(len(train_df_scaled), seed=shuffle_seed)
        .batch(batch_size)
    )
    ds_val = tf.data.Dataset.from_tensor_slices(
        (val_df_scaled.values, val_df_scaled.values)
    ).batch(batch_size)

    return ds_xx, ds_val, scaler


def train_base(
    df,
    patience=100,
    batch_size=64,
    validation_split=0.2,
    shuffle_seed=None,
    pretrain_epochs=500,
):
    ds_xx, ds_val, scaler = create_datasets(
        df,
        batch_size=batch_size,
        validation_split=validation_split,
        shuffle_seed=shuffle_seed,
    )

    model = auto_encoder(load_weights=False)
    optimizer = tf.keras.optimizers.Adam(learning_rate=0.0001)

    model.compile(optimizer=optimizer, loss=tf.keras.losses.MeanSquaredError())
    early_stopping = EarlyStopping(
        monitor="val_loss", patience=patience, restore_best_weights=True
    )

    history = model.fit(
        ds_xx,
        validation_data=ds_val,
        epochs=pretrain_epochs,
        verbose=1,
        callbacks=[early_stopping],
    )

    weights_file = "weight_base.weights.h5"
    model.save_weights(weights_file)
    return history, scaler


def plot_training_history(history):
    plt.plot(history.history["loss"], label="Training Loss")
    plt.plot(history.history["val_loss"], label="Validation Loss")
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.legend()
    plt.show()


def save_scaler(scaler, file_name="scaler.pkl"):
    with open(file_name, "wb") as f:
        pickle.dump(scaler, f)
    print(f"Scaler saved to {file_name}")


def load_scaler(file_name="scaler.pkl"):
    with open(file_name, "rb") as f:
        scaler = pickle.load(f)
    print(f"Scaler loaded from {file_name}")
    return scaler


def auto_encoder(load_weights=True, weights_file=None):
    filters = [45, 33, 16, hidden_units]  # Adjust filters as needed
    init = "uniform"
    activation = "relu"
    input_shape = (input_dim,)
    l2_reg = tf.keras.regularizers.L1L2(l1=0.01, l2=0.01)  # L2 regularization

    input = tf.keras.layers.Input(shape=input_shape)
    x = input

    # Encoder
    for i in range(len(filters)):
        x = tf.keras.layers.Dense(
            filters[i],
            activation=activation,
            kernel_initializer=init,
            kernel_regularizer=l2_reg,
        )(x)
        x = tf.keras.layers.Dropout(0.1)(x)
        x = tf.keras.layers.BatchNormalization()(x)

    h = x  # bottleneck layer

    # Decoder
    for i in range(len(filters) - 1, 0, -1):
        x = tf.keras.layers.Dense(
            filters[i],
            activation=activation,
            kernel_initializer=init,
            kernel_regularizer=l2_reg,
        )(x)
        x = tf.keras.layers.Dropout(0.1)(x)
        x = tf.keras.layers.BatchNormalization()(x)

    y = tf.keras.layers.Dense(
        input_shape[0], kernel_initializer=init, kernel_regularizer=l2_reg
    )(x)

    model = tf.keras.Model(inputs=input, outputs=y)

    if load_weights and weights_file and os.path.exists(weights_file):
        model.load_weights(weights_file)
        print("autoencoder: weights were loaded")
    else:
        print("autoencoder: weights file not found, training from scratch")

    return model


def get_sil_db(assignments, features):
    sil_score = silhouette_score(features, assignments)
    db_score = davies_bouldin_score(features, assignments)
    return sil_score, db_score


def log_csv(strToWrite, file_name):
    path = r"log_history/"
    if not os.path.exists(path):
        os.makedirs(path)
    with open(path + file_name + ".csv", "a+", encoding="utf-8") as f:
        csv_writer = csv.writer(f)
        csv_writer.writerow(strToWrite)


def sorted_eig(X):
    e_vals, e_vecs = np.linalg.eig(X)
    idx = np.argsort(e_vals)
    e_vecs = e_vecs[:, idx]
    e_vals = e_vals[idx]
    return e_vals, e_vecs


def train(x, clustering_method="kmeans"):
    ds_name = clustering_method
    log_str = f'iter; sil_score, db_score, ri ; loss; n_changed_assignment; time:{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}'
    log_csv(log_str.split(";"), file_name=ds_name)
    model = auto_encoder(weights_file="weight_base.weights.h5")

    optimizer = tf.keras.optimizers.Adam()
    loss_value = 0
    index = 0
    kmeans_n_init = 100
    assignment = np.array([-1] * len(x))
    index_array = np.arange(x.shape[0])
    update_interval = 10
    sil_score, db_index = 0, 0
    n_clusters = 6
    time_start = time.time()

    # Use tqdm for progress tracking
    for ite in tqdm(range(int(27000)), desc="Training Progress"):
        # Recalculate V every 10 steps
        if ite % update_interval == 0:
            H = model(x).numpy()[:, :hidden_units]  # Gets H

            if clustering_method == "kmeans":
                ans_kmeans = KMeans(n_clusters=n_clusters, n_init=kmeans_n_init).fit(
                    H
                )  # Fits KMeans to H
                kmeans_n_init = int(
                    ans_kmeans.n_iter_ * 2
                )  # Number of times to run on different seeds (optional)
                U = ans_kmeans.cluster_centers_  # Obtains mu, the centers
                assignment_new = (
                    ans_kmeans.labels_
                )  # Array containing assignments for each element
            elif clustering_method == "gmm":
                ans_gmm = GaussianMixture(n_components=n_clusters).fit(
                    H
                )  # Fits GMM to H
                U = ans_gmm.means_  # Obtains mu, the centers
                assignment_new = ans_gmm.predict(
                    H
                )  # Array containing assignments for each element
            elif clustering_method == "spectral":
                affinity_matrix = kneighbors_graph(
                    H, n_neighbors=30, include_self=True
                )  # Sparse matrix
                ans_spectral = SpectralClustering(
                    n_clusters=n_clusters,
                    affinity="nearest_neighbors",
                    assign_labels="discretize",
                    n_neighbors=30,
                ).fit(H)  # Fits Spectral Clustering to H
                U = np.array(
                    [
                        H[ans_spectral.labels_ == i].mean(axis=0)
                        for i in range(n_clusters)
                    ]
                )  # Approximates cluster centers
                assignment_new = (
                    ans_spectral.labels_
                )  # Array containing assignments for each element

            # This is the Hungarian algorithm for cluster assignment
            w = np.zeros(
                (n_clusters, n_clusters), dtype=np.int64
            )  # Sets up adjacency matrix
            for i in range(len(assignment_new)):
                w[assignment_new[i], assignment[i]] += 1

            # This does the Hungarian algorithm
            ind = linear_assignment(-w)

            # Changes the associated clusters
            temp = np.array(assignment)
            for i in range(n_clusters):
                assignment[temp == ind[1][i]] = i

            # Number of changes
            n_change_assignment = np.sum(assignment_new != assignment)
            assignment = assignment_new

            # Gets total within sum of squares matrix
            S_i = []
            for i in range(n_clusters):
                temp = H[assignment == i] - U[i]
                temp = np.matmul(np.transpose(temp), temp)
                S_i.append(temp)
            S_i = np.array(S_i)
            S = np.sum(S_i, 0)

            Evals, V = sorted_eig(S)
            H_vt = np.matmul(H, V)  # Finds y = Vh
            U_vt = np.matmul(U, V)  # Finds m = Vmu

            loss = np.round(np.mean(loss_value), 5)

            # Calculate Silhouette Score and Davies-Bouldin Index
            sil_score, db_index = (
                0,
                0,
            )

            # Log
            log_str = (
                f"iter {ite // update_interval}; sil_score, db_score, ri = {sil_score, db_index}; loss:"
                f"{loss}; n_changed_assignment:{n_change_assignment}; time:{time.time() - time_start:.3f}"
            )
            print(log_str)
            log_csv(log_str.split(";"), file_name=ds_name)

        # Stopping condition

        # Getting next batch
        idx = index_array[
            index * batch_size : min((index + 1) * batch_size, x.shape[0])
        ]

        # Creating y' from y & replacing last dimension of y' with m_i
        y_true = H_vt[idx]  # y: latent representations for the current batch
        temp = assignment[idx]  # m_i: cluster assignments for the current batch
        for i in range(len(idx)):
            y_true[i, -1] = U_vt[
                temp[i], -1
            ]  # Creating y': replacing last dimension with m_i

        # Update all model variables
        with tf.GradientTape() as tape:
            y_pred = model(x[idx])  # h
            y_pred_cluster = tf.matmul(y_pred[:, :hidden_units], V)  # y = Vh
            loss_value = tf.keras.losses.mse(y_true, y_pred_cluster)
        grads = tape.gradient(loss_value, model.trainable_variables)
        optimizer.apply_gradients(zip(grads, model.trainable_variables))

        index = index + 1 if (index + 1) * batch_size <= x.shape[0] else 0

        if n_change_assignment <= len(x) * 0.005:
            break

    model.save_weights(f"weight_final_{ds_name}15.weights.h5")
    print(f"end saved to weight_final_{ds_name}.weights.h5")


def resample_candlestick_data(df, frequency):
    df.set_index("datetime", inplace=True)

    resampled_df = (
        df.resample(frequency)
        .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
        .dropna()
    )

    resampled_df.reset_index(inplace=True)

    return resampled_df


data = get_data(PATH)
# data = resample_candlestick_data(data.copy(), "15min")
# print("\nResampled Data (15 Minutes):\n", data.head().to_string())
print(data.shape)
model_data, _ = create_model_df(data.copy())
pretrain_epochs = 200
pretrain_batch_size = 256
batch_size = 256
update_interval = 10
input_dim = model_data.shape[1]
global hidden_units, ds_name
hidden_units = 8
update_interval = 10
ds_name = "data"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Train model with KMeans, GMM, or Spectral clustering"
    )
    parser.add_argument(
        "--method",
        type=str,
        choices=["kmeans", "gmm", "spectral"],
        default="kmeans",
        help='Clustering method to use: "kmeans", "gmm", or "spectral"',
    )
    args = parser.parse_args()

    scaler = load_scaler("scaler.pkl")
    x_scaled = scaler.transform(model_data.copy())
    train(x_scaled, clustering_method=args.method)
