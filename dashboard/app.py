import pandas as pd
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
from src.fetch_historical import *
import threading
from src.models.rsi import RSI
from src.models.rsisl import RSIsl
from datetime import datetime
import os
import signal
from src.constants import *
from src.utils import *
import websocket
import json
from datetime import datetime
import warnings

warnings.filterwarnings("ignore")

app = Flask(__name__)
socketio = SocketIO(app)

fetch_klines(filename=DATAPATH, limit=DATA_BLOCK_SIZE + 1)

rsi = RSI()
rsisl = RSIsl()
models = [rsi, rsisl]

stop_event = threading.Event()
data_block = read_df(DATAPATH, n=DATA_BLOCK_SIZE)


data_with_clusters = assign_clusters(data_block.copy())
data_block = data_with_clusters.copy()
data_block.dropna(inplace=True)


@app.route("/")
def index():
    """
    Render the main index page.

    Returns:
        Rendered template for the index page.
    """
    return render_template("index.html")


@app.route("/returns")
def returns_page():
    """
    Render the returns page.

    Returns:
        Rendered template for the returns page.
    """
    return render_template("returns.html")


@app.route("/get_model_names")
def get_model_names():
    """
    API endpoint to get the names of all models.

    Returns:
        flask.Response: JSON response containing a list of model names.
    """
    return jsonify([model.name for model in models])


@app.route("/get_active_trade")
def get_active_trade():
    """
    API endpoint to get the active trade for a specific model.

    Query Parameters:
        model (str): The name of the model.

    Returns:
        flask.Response: JSON response containing the active trade details or an error message.
    """
    model_name = request.args.get("model")
    model = next((m for m in models if m.name == model_name), None)
    if not model:
        return jsonify({"error": "Model not found"}), 404

    active_trade = model.get_active_trade()

    if not active_trade:
        return jsonify({"active_trade": None})
    else:
        return jsonify({"active_trade": active_trade})


@app.route("/get_returns")
def get_returns_route():
    """
    API endpoint to get the returns data for a specific model.

    Query Parameters:
        model (str): The name of the model.

    Returns:
        flask.Response: JSON response containing returns data or an error message.
    """
    model_name = request.args.get("model")

    returns_data = get_returns(models, model_name)
    if returns_data is None:
        return jsonify({"error": "Failed to retrieve returns data"}), 500

    return jsonify(returns_data)


@app.route("/model_dash")
def model_dash():
    """
    Render the model dashboard page.

    Query Parameters:
        model (str): The name of the model.

    Returns:
        Rendered template for the model dashboard.
    """
    selected_model = request.args.get("model", default="Err 500")
    return render_template("model_dash.html", model=selected_model)


@app.route("/get_latest")
def get_latest():
    """
    API endpoint to get the latest data point.

    Returns:
        flask.Response: JSON response containing the latest data point.
    """
    historical_data = data_block.tail(1).copy()
    historical_data = convert_format(historical_data)

    combined_data = {
        "data": historical_data.to_dict("records"),
    }

    return jsonify(combined_data)


@app.route("/get_range")
def get_range():
    """
    API endpoint to get the data range.

    Returns:
        flask.Response: JSON response containing the data range.
    """
    return jsonify({"range": RANGE})


@app.route("/fetch")
def history():
    """
    API endpoint to fetch historical data.

    Returns:
        flask.Response: JSON response containing historical data records.
    """
    historical_data = data_block.tail(min(RANGE, len(data_block))).copy()
    historical_data = convert_format(historical_data)
    historical_data = historical_data[
        ["time", "open", "high", "low", "close", "cluster"]
    ]
    historical_data = historical_data.dropna(
        subset=["time", "open", "high", "low", "close"]
    )
    historical_data = historical_data.drop_duplicates(subset=["time"], keep="first")
    historical_data = historical_data.sort_values("time", ascending=True)

    return jsonify(historical_data.to_dict("records"))


@app.route("/get_model_params")
def get_model_params():
    """
    API endpoint to get the parameters of a specific model.

    Query Parameters:
        model (str): The name of the model.

    Returns:
        flask.Response: JSON response containing fixed and dynamic parameters of the model.
    """
    model_name = request.args.get("model")

    model = next((m for m in models if m.name == model_name), None)

    fixed_params = model.get_fixed_parameters()
    dynamic_params = model.get_dynamic_parameters()

    return jsonify({"fixed": fixed_params, "dynamic": dynamic_params})


@app.route("/submit_trade", methods=["POST"])
def submit_trade():
    """
    API endpoint to submit a trade for a specific model.

    Request JSON Parameters:
        model (str): The name of the model.
        trade_type (str): The type of trade ('long' or 'short').
        trade_units (float): The number of units to trade.

    Returns:
        flask.Response: JSON response indicating the status of the trade submission.
    """
    data = request.json
    model_name = data.get("model")
    if not model_name:
        return jsonify({"status": "error", "message": "Model name is required"}), 400

    trade_type = data.get("trade_type")
    if trade_type not in ["long", "short"]:
        return jsonify({"status": "error", "message": "Invalid trade type"}), 400

    try:
        trade_units = float(data.get("trade_units"))
        if trade_units <= 0:
            return jsonify(
                {"status": "error", "message": "Trade units must be positive"}
            ), 400
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Invalid trade units"}), 400

    model = next((m for m in models if m.name == model_name), None)
    if not model:
        return jsonify({"status": "error", "message": "Model not found"}), 404

    if model.in_trade:
        return jsonify({"status": "error", "message": "Model is already in trade"}), 400

    if trade_type == "long":
        model.enter_long()
    else:
        model.enter_short()

    return jsonify(
        {
            "status": "success",
            "message": f"Entered {trade_type} trade with {trade_units} units",
            "action": "updateNextUnitsChart",
        }
    )


@app.route("/exit_position", methods=["POST"])
def exit_position():
    """
    API endpoint to exit an active position for a specific model.

    Request JSON Parameters:
        model (str): The name of the model.

    Returns:
        flask.Response: JSON response indicating the status of the exit operation.
    """
    data = request.json
    model_name = data.get("model")

    model = next((m for m in models if m.name == model_name), None)

    if not model:
        return jsonify({"status": "error", "message": "Model not found"}), 404

    if not model.in_trade:
        return jsonify({"status": "error", "message": "No active trade to exit"}), 400

    if model.trade_type == "Long":
        model.exit_long()
    elif model.trade_type == "Short":
        model.exit_short()
    else:
        return jsonify({"status": "error", "message": "No active trade to exit"}), 400

    return jsonify({"status": "success", "action": "updateNextUnitsChart"}), 200


@app.route("/switch_trade", methods=["POST"])
def switch_trade():
    """
    API endpoint to switch the trade type for a specific model.

    Request JSON Parameters:
        model (str): The name of the model.

    Returns:
        flask.Response: JSON response indicating the status of the switch operation.
    """
    data = request.json
    model_name = data.get("model")

    model = next((m for m in models if m.name == model_name), None)

    if not model:
        return jsonify({"status": "error", "message": "Model not found"}), 404

    if not model.in_trade:
        return jsonify({"status": "error", "message": "No active trade to exit"}), 400

    if model.trade_type == "Long":
        model.exit_long()
        model.enter_short()
    elif model.trade_type == "Short":
        model.exit_short()
        model.enter_long()
    else:
        return jsonify({"status": "error", "message": "No active trade to switch"}), 400

    return jsonify({"status": "success", "action": "updateNextUnitsChart"}), 200


@app.route("/update_model_status", methods=["POST"])
def update_model_status():
    """
    API endpoint to update the operational status of a specific model.

    Request JSON Parameters:
        model (str): The name of the model.
        status (str): The desired status ('on' or 'off').

    Returns:
        flask.Response: JSON response indicating the status of the update operation.
    """
    data = request.json
    model_name = data.get("model")
    status = data.get("status")

    model = next((m for m in models if m.name == model_name), None)

    if not model:
        return jsonify({"status": "error", "message": "Model not found"}), 404

    if status == "off" and model.operational:
        if model.in_trade:
            if model.trade_type == "Long":
                model.exit_long()
            elif model.trade_type == "Short":
                model.exit_short()
        model.operational = False
    elif status == "on" and not model.operational:
        model.operational = True
    else:
        return jsonify({"status": "error", "message": "invalid"}), 404

    return jsonify({"status": "success", "action": "updateNextUnitsChart"}), 200


@app.route("/update_dynamic_param", methods=["POST"])
def update_dynamic_param():
    """
    API endpoint to update a dynamic parameter of a specific model.

    Request JSON Parameters:
        model (str): The name of the model.
        param (str): The parameter to update.
        value (float): The new value for the parameter.

    Returns:
        flask.Response: JSON response indicating the status of the update operation.
    """
    data = request.json
    model_name = data.get("model")
    param = data.get("param")
    value = float(data.get("value"))

    model = next((m for m in models if m.name == model_name), None)

    if model_name == "RSIsl":
        if param == "Overbought Level":
            model.overbought_level = value
        if param == "Oversold Level":
            model.oversold_level = value
        if param == "RSI Period":
            model.rsi_period = value
        if param == "Stop Loss":
            if model.trade_type == "Short":
                model.trailing_stop_loss_pct = 1 + (value / model.lowest_price)
            elif model.trade_type == "Long":
                model.trailing_stop_loss_pct = 1 - (value / model.highest_price)
            else:
                return jsonify(
                    {"status": "error", "message": "Model not in trade"}
                ), 404
    elif model_name == "RSI":
        if param == "Overbought Level":
            model.overbought_level = value
        if param == "Oversold Level":
            model.oversold_level = value
        if param == "RSI Period":
            model.rsi_period = value
    else:
        return jsonify({"status": "error", "message": "Invalid model name"}), 404

    return jsonify({"status": "success", "action": "updateNextUnitsChart"}), 200


def convert_format(historical_data):
    """
    Convert historical data into the required format.

    Parameters:
        historical_data (pd.DataFrame): The historical data to convert.

    Returns:
        pd.DataFrame: The converted historical data.
    """
    historical_data = historical_data.copy()
    historical_data["datetime"] = pd.to_datetime(historical_data["datetime"])
    historical_data["datetime"] = historical_data["datetime"].apply(
        lambda x: x.replace(second=0)
    )
    historical_data["time"] = historical_data["datetime"].apply(
        lambda x: int(x.timestamp())
    )
    historical_data.drop("datetime", axis=1, inplace=True)
    for col in historical_data.columns:
        if col != "time" and col != "cluster":
            historical_data[col] = historical_data[col].astype(float)
    historical_data["time"] = historical_data["time"].astype(int)
    if "cluster" in historical_data.columns:
        historical_data["cluster"] = historical_data["cluster"].astype("Int64")
    else:
        historical_data["cluster"] = pd.NA
    return historical_data


def get_latest_data(data):
    """
    Process new incoming data and update models.

    Parameters:
        data (pd.DataFrame): The new data to process.
    """
    try:
        if not data.empty:
            global data_block
            data_block = pd.concat([data_block, data], ignore_index=True)
            if len(data_block) > DATA_BLOCK_SIZE:
                data_block = data_block.iloc[-DATA_BLOCK_SIZE:]

            data_block_with_clusters = assign_clusters(data_block.copy())
            data_block = data_block_with_clusters.copy()

            if "cluster" not in data_block.columns:
                data_block["cluster"] = pd.NA

            latest_data_with_clusters = data_block.tail(1)

            historical_data = convert_format(latest_data_with_clusters)

            for model in models:
                model.execute(historical_data)
    except Exception as e:
        print(f"Error processing data: {e}")


class BinanceWebSocketClient:
    """
    A client to connect to Binance WebSocket and process kline data.
    """

    def __init__(self, symbol, interval):
        """
        Initialize the BinanceWebSocketClient.

        Parameters:
            symbol (str): The trading pair symbol (e.g., 'btcusdt').
            interval (str): The kline interval (e.g., '1m').
        """
        self.symbol = symbol.lower()
        self.interval = interval
        self.ws = None
        self.thread = None
        self.stop_event = threading.Event()

    def start(self):
        """
        Start the WebSocket client in a separate thread.
        """
        self.thread = threading.Thread(target=self._run_websocket)
        self.thread.start()

    def stop(self):
        """
        Stop the WebSocket client and the associated thread.
        """
        self.stop_event.set()
        if self.ws:
            self.ws.close()
        if self.thread:
            self.thread.join()

    def _run_websocket(self):
        """
        Internal method to run the WebSocket connection.
        """

        def on_message(ws, message):
            """
            Handle incoming WebSocket messages.

            Parameters:
                ws (websocket.WebSocketApp): The WebSocket app instance.
                message (str): The incoming message.
            """
            data = json.loads(message)
            kline = data["k"]
            if kline["x"]:
                timestamp = kline["t"]
                open_price = kline["o"]
                high_price = kline["h"]
                low_price = kline["l"]
                close_price = kline["c"]

                dt = datetime.utcfromtimestamp(timestamp / 1000).replace(
                    second=0, microsecond=0
                )
                dt_str = dt.strftime("%Y-%m-%d %H:%M:%S")

                new_data = pd.DataFrame(
                    {
                        "datetime": [dt_str],
                        "open": [float(open_price)],
                        "high": [float(high_price)],
                        "low": [float(low_price)],
                        "close": [float(close_price)],
                    }
                )

                new_data.to_csv(
                    DATAPATH, mode="a", header=not os.path.exists(DATAPATH), index=False
                )
                print(f"{dt_str}:\tNew data appended...")

                get_latest_data(new_data)

        def on_error(ws, error):
            """
            Handle WebSocket errors.

            Parameters:
                ws (websocket.WebSocketApp): The WebSocket app instance.
                error (str): The error message.
            """
            print(f"WebSocket error: {error}")

        def on_close(ws, close_status_code, close_msg):
            """
            Handle WebSocket closure.

            Parameters:
                ws (websocket.WebSocketApp): The WebSocket app instance.
                close_status_code (int): The status code.
                close_msg (str): The close message.
            """
            print("WebSocket closed")

            if not self.stop_event.is_set():
                print("Reconnecting...")
                self._run_websocket()

        def on_open(ws):
            """
            Handle WebSocket opening.

            Parameters:
                ws (websocket.WebSocketApp): The WebSocket app instance.
            """
            print("WebSocket connection opened")

        stream_url = (
            f"wss://stream.binance.com:9443/ws/{self.symbol}@kline_{self.interval}"
        )
        self.ws = websocket.WebSocketApp(
            stream_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open,
        )

        self.ws.run_forever()


def signal_handler(sig, frame):
    """
    Handle termination signals to gracefully shut down the application.

    Parameters:
        sig (int): Signal number.
        frame (frame object): Current stack frame.
    """
    print("Ctrl+C pressed. Shutting down forcefully...")
    stop_event.set()
    if binance_ws_client:
        binance_ws_client.stop()
    socketio.stop()
    threading.Timer(5, force_exit).start()


def force_exit():
    """
    Forcefully exit the application.
    """
    print("Forcing exit...")
    os._exit(1)


if __name__ == "__main__":
    binance_ws_client = None
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    binance_ws_client = BinanceWebSocketClient(symbol="btcusdt", interval="1m")
    binance_ws_client.start()

    try:
        socketio.run(app, debug=False, host="0.0.0.0", port=8080)
    except KeyboardInterrupt:
        print("KeyboardInterrupt caught in main thread")
    finally:
        print("Initiating shutdown...")
        stop_event.set()
        binance_ws_client.stop()
        force_exit()
