import argparse
import requests
import os
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from google.cloud import storage
from dotenv import load_dotenv
import shutil

load_dotenv()


def download_data(url, filename):
    """
    Download data from a given URL and save it to a specified filename.

    Args:
        url (str): The URL to download the data from.
        filename (str or Path): The path where the downloaded file will be saved.

    Returns:
        bool: True if the download was successful, False otherwise.
    """
    response = requests.get(url)
    if response.status_code == 200:
        with open(filename, "wb") as file:
            file.write(response.content)
        print(f"Data downloaded successfully: {filename}")
        return True
    else:
        print(f"Failed to download data from URL: {url}")
        return False


def process_data(zip_path):
    """
    Process the downloaded ZIP file and extract relevant data.

    Reads the CSV file from the ZIP archive, parses the data, and returns a DataFrame
    containing the 'Datetime', 'Open', 'High', 'Low', and 'Close' columns.

    Args:
        zip_path (str or Path): The path to the ZIP file containing the data.

    Returns:
        pandas.DataFrame: A DataFrame with the processed data, indexed by 'DateTime'.
    """
    new_data = pd.read_csv(
        zip_path,
        header=None,
        names=[
            "Open time",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
            "Close time",
            "Quote asset volume",
            "Number of trades",
            "Taker buy base asset volume",
            "Taker buy quote asset volume",
            "Ignore",
        ],
    )

    new_data["Datetime"] = pd.to_datetime(new_data["Open time"], unit="ms", utc=True)
    new_data = new_data[["Datetime", "Open", "High", "Low", "Close"]]
    new_data.set_index("Datetime", inplace=True)
    new_data.index = new_data.index.tz_localize(None)
    new_data.index.name = "DateTime"

    return new_data


def fetch_batch_data(symbol, start_date, end_date):
    """
    Fetch batch data for a given symbol between specified start and end dates.

    Downloads data for each day within the date range and concatenates it into a single DataFrame.

    Args:
        symbol (str): The trading pair symbol (e.g., 'BTCUSDT').
        start_date (str): The start date in 'YYYY-MM-DD' format.
        end_date (str): The end date in 'YYYY-MM-DD' format.

    Returns:
        pandas.DataFrame: A DataFrame containing the concatenated data for the date range.
    """
    interval = "1m"
    start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")

    base_url = "https://data.binance.vision/data/spot/daily/klines"

    batch_data = pd.DataFrame()

    current_date = start_date_obj

    temp_dir = Path("tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)

    while current_date <= end_date_obj:
        date_str = current_date.strftime("%Y-%m-%d")
        url = f"{base_url}/{symbol}/{interval}/{symbol}-{interval}-{date_str}.zip"
        zip_filename = f"{symbol}-{interval}-{date_str}.zip"
        zip_path = temp_dir / zip_filename

        if download_data(url, zip_path):
            daily_data = process_data(zip_path)
            batch_data = pd.concat([batch_data, daily_data])
            os.remove(zip_path)
        else:
            print(f"Failed to download data for date: {date_str}")

        current_date += timedelta(days=1)

    return batch_data


def save_to_bucket(batch_data, blob_name, bucket_name):
    """
    Save the batch data to a Google Cloud Storage bucket.

    Args:
        batch_data (pandas.DataFrame): The DataFrame containing the batch data to save.
        blob_name (str): The name of the blob (object) in the bucket.
        bucket_name (str): The name of the Google Cloud Storage bucket.

    Returns:
        None
    """
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    csv_data = batch_data.to_csv(index=True, index_label="DateTime")
    blob.upload_from_string(csv_data)

    print(f"Batch data uploaded successfully: {blob_name}")


def save_to_csv(batch_data, csv_path):
    """
    Save the batch data to a CSV file, ensuring no duplicates and correct formatting.

    Args:
        batch_data (pandas.DataFrame): The DataFrame containing the batch data to save.
        csv_path (str or Path): The path to the CSV file where data will be saved.

    Returns:
        None
    """
    if csv_path.exists():
        existing_data = pd.read_csv(csv_path, index_col="DateTime", parse_dates=True)
        existing_data.index = existing_data.index.tz_localize(None)
        merged_data = pd.concat([existing_data, batch_data])
        merged_data = merged_data[~merged_data.index.duplicated(keep="first")]
    else:
        merged_data = batch_data

    merged_data.sort_index(inplace=True)
    merged_data.to_csv(csv_path, index_label="DateTime")
    print(f"Batch data saved successfully: {csv_path}")


def fetch_data(symbol, start_date, end_date, use_bucket=False):
    """
    Fetch data for a given symbol and date range, and save it locally or to a bucket.

    Splits the date range into weekly batches, fetches the data, processes it, and saves
    the results either locally or to a Google Cloud Storage bucket.

    Args:
        symbol (str): The trading pair symbol (e.g., 'BTCUSDT').
        start_date (str): The start date in 'YYYY-MM-DD' format.
        end_date (str): The end date in 'YYYY-MM-DD' format.
        use_bucket (bool, optional): If True, save data to a Google Cloud Storage bucket.
                                     If False, save data locally. Defaults to False.

    Returns:
        None
    """
    interval = "1m"

    if use_bucket:
        bucket_name = os.getenv("BUCKET_NAME")
        if not bucket_name:
            raise ValueError("Bucket name not specified in environment variables.")
    else:
        output_dir = Path("data")
        output_dir.mkdir(parents=True, exist_ok=True)

    csv_filename = f"{symbol}_{interval}.csv"
    csv_path = None if use_bucket else output_dir / csv_filename

    start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")

    current_start_date = start_date_obj
    batch_size = timedelta(weeks=1)

    while current_start_date <= end_date_obj:
        current_end_date = min(
            current_start_date + batch_size - timedelta(days=1), end_date_obj
        )
        batch_start_str = current_start_date.strftime("%Y-%m-%d")
        batch_end_str = current_end_date.strftime("%Y-%m-%d")
        print(f"Fetching data for batch: {batch_start_str} to {batch_end_str}")

        batch_data = fetch_batch_data(symbol, batch_start_str, batch_end_str)

        if batch_data is not None and not batch_data.empty:
            batch_data.index = batch_data.index.tz_localize(None)
            batch_data.index.name = "DateTime"

            interval_mapping = {
                "1m": "1min",
            }
            freq = interval_mapping[interval]
            expected_index = pd.date_range(
                start=batch_data.index.min(),
                end=batch_data.index.max(),
                freq=freq,
            )
            batch_data = batch_data.reindex(expected_index)
            batch_data.index.name = "DateTime"

            missing_timestamps = batch_data[batch_data.isnull().any(axis=1)]
            if not missing_timestamps.empty:
                print(
                    f"Warning: Missing data for timestamps:\n{missing_timestamps.index}"
                )

            batch_data = batch_data[~batch_data.index.duplicated(keep="first")]

            if use_bucket:
                blob_name = f"{symbol}_{interval}/{batch_start_str}_{batch_end_str}.csv"
                save_to_bucket(batch_data, blob_name, bucket_name)
            else:
                save_to_csv(batch_data, csv_path)
        else:
            print(f"No data fetched for batch: {batch_start_str} to {batch_end_str}")

        current_start_date = current_end_date + timedelta(days=1)

    print(f"Data fetching completed.")
    temp_dir = Path("tmp")
    shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    """
    The main function that parses command-line arguments and initiates the data fetching process.

    Command-line Arguments:
        --start-date (str): Start date in 'YYYY-MM-DD' format (default: '2021-01-01').
        --end-date (str): End date in 'YYYY-MM-DD' format (default: current date).
        --symbol (str): Trading pair symbol (e.g., 'BTCUSDT') (default: 'BTCUSDT').
        --output-dir (str): Output directory for saving data (default: 'data').
        --use-bucket (bool): Flag to save data to a Google Cloud Storage bucket.

    Returns:
        None
    """
    parser = argparse.ArgumentParser(description="Fetch data from Binance API")
    parser.add_argument(
        "--start-date", help="Start date (YYYY-MM-DD)", default="2021-01-01"
    )
    parser.add_argument(
        "--end-date",
        help="End date (YYYY-MM-DD)",
        default=datetime.now().strftime("%Y-%m-%d"),
    )
    parser.add_argument(
        "--symbol", help="Trading pair symbol (e.g., BTCUSDT)", default="BTCUSDT"
    )
    parser.add_argument(
        "--output-dir", help="Output directory (default: data)", default="data"
    )
    parser.add_argument(
        "--use-bucket",
        action="store_true",
        help="Store data in Google Cloud Storage bucket",
    )

    args = parser.parse_args()

    fetch_data(
        args.symbol,
        args.start_date,
        args.end_date,
        use_bucket=args.use_bucket,
    )


if __name__ == "__main__":
    main()
