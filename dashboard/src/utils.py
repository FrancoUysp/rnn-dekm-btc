import pandas as pd
from .constants import *
import os
from datetime import datetime, timedelta
import csv
from src.ml.rnndekm import DEKM_RNN


def read_df(file_loc, n=None):
    """
    Read a CSV file and return a pandas DataFrame.

    Parameters:
        file_loc (str): The path to the CSV file to read.
        n (int, optional): The number of rows to read from the end of the file. If None, read the entire file.

    Returns:
        pandas.DataFrame: The DataFrame containing the data read from the CSV file.
    """
    if n is None:
        data = pd.read_csv(
            file_loc,
            dtype={"Open": float, "High": float, "Low": float, "Close": float},
            low_memory=False,
        )
    else:
        with open(file_loc, "r") as f:
            total_rows = sum(1 for _ in f) - 1
        if n < total_rows:
            data = pd.read_csv(
                file_loc,
                skiprows=range(1, total_rows - n + 1),
                dtype={"Open": float, "High": float, "Low": float, "Close": float},
                low_memory=False,
            )
        else:
            data = pd.read_csv(
                file_loc,
                dtype={"Open": float, "High": float, "Low": float, "Close": float},
                low_memory=False,
            )

    data.columns = data.columns.str.lower()

    data["datetime"] = pd.to_datetime(
        data["datetime"], format="%Y-%m-%d %H:%M:%S", errors="coerce"
    )

    data.dropna(subset=["datetime"], inplace=True)

    data = data.sort_values(by=["datetime"]).reset_index(drop=True)
    print(data.tail(4))

    return data


def get_returns(models, model_name=None):
    """
    Calculate returns based on trade data from models.

    Parameters:
        models (list): A list of model instances.
        model_name (str, optional): The name of a specific model to calculate returns for. If None or 'all_models', returns for all models are calculated.

    Returns:
        dict: A dictionary containing the positions and return statistics.
    """
    if model_name and model_name != "all_models":
        model_names = [model_name]
    else:
        model_names = [m.name for m in models]

    closed_positions = []

    for name in model_names:
        trades_file = f"trades_{name}.csv"

        if not os.path.exists(trades_file):
            continue

        with open(trades_file, "r", newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                try:
                    position_id = int(row["Position ID"])
                    type_str = row["Type"]
                    entry_time_str = row["Entry Time"]
                    exit_time_str = row["Exit Time"]
                    volume = float(row["Volume"])
                    entry_price = float(row["Entry Price"])
                    exit_price = float(row["Exit Price"])
                    profit = float(row["Profit (USD)"])
                    percentage_return_str = row["Percentage Return (%)"]

                    percentage_return = (
                        float(percentage_return_str.replace("%", "")) / 100.0
                    )

                    if type_str == "Long":
                        position_type = 0
                    elif type_str == "Short":
                        position_type = 1
                    else:
                        position_type = -1

                    entry_time = datetime.strptime(entry_time_str, "%Y-%m-%d %H:%M:%S")
                    exit_time = datetime.strptime(exit_time_str, "%Y-%m-%d %H:%M:%S")

                    position = {
                        "position_id": position_id,
                        "type": position_type,
                        "entry_time": entry_time,
                        "exit_time": exit_time,
                        "volume": volume,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "profit": profit,
                        "percentage_return": percentage_return,
                        "magic": name,
                    }

                    closed_positions.append(position)
                except Exception as e:
                    print(f"Error parsing row in {trades_file}: {e}")
                    continue

    all_time_profit = sum(p["profit"] for p in closed_positions)
    all_time_percentage = sum(p["percentage_return"] for p in closed_positions)

    current_date = datetime.now()

    current_month_start = current_date.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    current_week_start = (
        current_date - timedelta(days=current_date.weekday())
    ).replace(hour=0, minute=0, second=0, microsecond=0)

    current_day_start = current_date.replace(hour=0, minute=0, second=0, microsecond=0)

    monthly_positions = [
        p for p in closed_positions if p["exit_time"] >= current_month_start
    ]
    weekly_positions = [
        p for p in closed_positions if p["exit_time"] >= current_week_start
    ]
    daily_positions = [
        p for p in closed_positions if p["exit_time"] >= current_day_start
    ]

    def calculate_period_returns(positions):
        total_profit = sum(p["profit"] for p in positions)
        total_percentage_return = sum(p["percentage_return"] for p in positions)
        return round(total_profit, 3), round(total_percentage_return, 5)

    monthly_return, monthly_percentage = calculate_period_returns(monthly_positions)
    weekly_return, weekly_percentage = calculate_period_returns(weekly_positions)
    daily_return, daily_percentage = calculate_period_returns(daily_positions)

    result = {
        "positions": [
            {
                "position_id": p["position_id"],
                "type": p["type"],
                "entry_time": p["entry_time"].strftime("%Y-%m-%d %H:%M:%S"),
                "exit_time": p["exit_time"].strftime("%Y-%m-%d %H:%M:%S"),
                "volume": p["volume"],
                "entry_price": round(p["entry_price"], 3),
                "exit_price": round(p["exit_price"], 3),
                "profit": round(p["profit"], 3),
                "percentage_return": round(p["percentage_return"], 5),
                "magic": p["magic"],
            }
            for p in closed_positions
        ],
        "all_time_return": round(all_time_profit, 3),
        "all_time_percentage": round(all_time_percentage, 5),
        "monthly_return": monthly_return,
        "monthly_percentage": monthly_percentage,
        "weekly_return": weekly_return,
        "weekly_percentage": weekly_percentage,
        "daily_return": daily_return,
        "daily_percentage": daily_percentage,
    }

    return result


dekm_rnn_instance = DEKM_RNN(sequence_length=50)


def assign_clusters(data):
    """
    Assign clusters to the data using the DEKM_RNN model.

    Parameters:
        data (pandas.DataFrame): The input data to cluster.

    Returns:
        pandas.DataFrame: The data with cluster assignments.
    """
    global dekm_rnn_instance
    data_with_clusters = dekm_rnn_instance.predict(data)
    return data_with_clusters
