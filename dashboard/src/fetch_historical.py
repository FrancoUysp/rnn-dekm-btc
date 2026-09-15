import pandas as pd
from datetime import datetime, timedelta
import pytz
from tqdm import tqdm
import os
import requests
from .constants import *


def get_latest_datetime_from_csv(filename):
    """
    Check if the file exists and find the latest datetime.

    Parameters:
        filename (str): The path to the CSV file.

    Returns:
        datetime.datetime or None: The latest datetime in the CSV file, or None if not found.
    """
    latest_datetime = None

    if os.path.exists(filename):
        try:
            df = pd.read_csv(filename, parse_dates=["datetime"])
            if not df.empty:
                latest_datetime = df["datetime"].max()
                latest_datetime = latest_datetime.to_pydatetime()
                latest_datetime = latest_datetime.replace(tzinfo=pytz.utc)
        except (pd.errors.EmptyDataError, KeyError):
            pass

    return latest_datetime


def save_to_csv(df, filename=DATAPATH):
    """
    Save a DataFrame to a CSV file, avoiding duplicates.

    Parameters:
        df (pd.DataFrame): The DataFrame to save.
        filename (str): The path to the CSV file.
    """
    df = df.drop_duplicates(subset="datetime", keep="first")
    if os.path.exists(filename):
        existing_last_row = pd.read_csv(filename, nrows=1)
        if not existing_last_row.empty:
            last_datetime = pd.to_datetime(existing_last_row["datetime"].iloc[0])

            new_data = df[pd.to_datetime(df["datetime"]) > last_datetime]

            if not new_data.empty:
                new_data.to_csv(filename, mode="a", header=False, index=False)
                print(f"New data appended to {filename}.")
            else:
                print("No new data to append.")
        else:
            df.to_csv(filename, index=False)
            print(f"Data saved to empty {filename}.")
    else:
        df.to_csv(filename, index=False)
        print(f"New file created: {filename}.")


def fetch_klines(symbol="BTCUSDT", interval="1m", limit=3200000, filename=DATAPATH):
    """
    Fetch historical kline data from Binance API and save to CSV.

    Parameters:
        symbol (str): The trading pair symbol.
        interval (str): The interval for klines.
        limit (int): The number of data points to fetch.
        filename (str): The path to the CSV file.
    """
    url = "https://api.binance.com/api/v3/klines"
    all_klines = []

    utc_now = datetime.now(pytz.utc).replace(second=0, microsecond=0) + timedelta(
        hours=1
    )
    latest_datetime = get_latest_datetime_from_csv(filename)

    if latest_datetime:
        limit = int((utc_now - latest_datetime).total_seconds() / 60 - 1)

    num_batches = (limit - 1) // 1000 + 1

    for batch in tqdm(range(num_batches), desc="Fetching batches"):
        start_time = (
            latest_datetime + timedelta(minutes=1)
            if latest_datetime and batch == 0
            else utc_now - timedelta(minutes=(num_batches - batch) * 1000)
        )
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": min(1000, limit - batch * 1000),
            "startTime": int(start_time.timestamp() * 1000),
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            klines = response.json()
            all_klines.extend(
                [
                    [
                        datetime.fromtimestamp(kline[0] / 1000, pytz.utc).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        *kline[1:5],
                    ]
                    for kline in klines
                ]
            )
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data: {e}")
            break

    df = pd.DataFrame(
        all_klines, columns=["datetime", "open", "high", "low", "close"]
    ).round({"open": 2, "high": 2, "low": 2, "close": 2})

    save_to_csv(df[:-1])


if __name__ == "__main__":
    filename = DATAPATH
    latest_datetime = get_latest_datetime_from_csv(filename)
    print(f"Latest datetime in {filename}: {latest_datetime}")

    fetch_klines(symbol="BTCUSDT", interval="1m", filename=filename)

    if os.path.exists(filename):
        df = pd.read_csv(filename)
        print(df.tail())
    else:
        print(f"File {filename} does not exist.")
