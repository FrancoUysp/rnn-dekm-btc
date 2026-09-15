import csv
import os
from datetime import datetime, timedelta


class RSI:
    def __init__(self):
        self.current_price = 0
        self.in_trade = False
        self.trade_type = None  # 'Long' or 'Short'
        self.operational = True

        self.rsi_period = 14
        self.prev_rsi = None
        self.close_prices = []

        self.entry_price = None
        self.entry_time = None
        self.exit_price = None
        self.exit_time = None
        self.current_trade = None  # To store the current trade details

        self.trades = []
        self.cumulative_return = 0

        self.oversold_level = 30
        self.overbought_level = 70

        self.name = "RSI"

        # Prepare trades file name
        self.trades_file = f"trades_{self.name}.csv"

    def execute(self, data):
        if not self.operational:
            return

        self.current_price = data.iloc[0]["close"]
        self.close_prices.append(self.current_price)

        # Keep only the necessary number of prices
        if len(self.close_prices) > self.rsi_period + 1:
            self.close_prices.pop(0)

        # Wait until we have enough data to compute RSI
        if len(self.close_prices) < self.rsi_period + 1:
            return

        current_rsi = self.calculate_rsi()
        if current_rsi is None:
            return

        if self.prev_rsi is not None:
            # Check for RSI crossing above oversold level to enter long
            if (
                self.prev_rsi < self.oversold_level
                and current_rsi >= self.oversold_level
            ):
                if not self.in_trade:
                    self.enter_long()
                elif self.trade_type == "Short":
                    self.exit_short()
                    self.enter_long()

            elif (
                self.prev_rsi > self.overbought_level
                and current_rsi <= self.overbought_level
            ):
                if not self.in_trade:
                    self.enter_short()
                elif self.trade_type == "Long":
                    self.exit_long()
                    self.enter_short()

            if self.trade_type == "Long" and current_rsi >= self.overbought_level:
                self.exit_long()

            # Exit short position when RSI crosses below oversold level
            if self.trade_type == "Short" and current_rsi <= self.oversold_level:
                self.exit_short()

        self.prev_rsi = current_rsi

    def calculate_rsi(self):
        # Ensure we have enough data
        if len(self.close_prices) < self.rsi_period + 1:
            return None

        # Calculate price differences
        price_diffs = [
            self.close_prices[i] - self.close_prices[i - 1]
            for i in range(1, len(self.close_prices))
        ]

        # Get the last self.rsi_period price differences
        price_diffs = price_diffs[-self.rsi_period :]

        gains = [diff if diff > 0 else 0 for diff in price_diffs]
        losses = [-diff if diff < 0 else 0 for diff in price_diffs]

        average_gain = sum(gains) / self.rsi_period
        average_loss = sum(losses) / self.rsi_period

        if average_loss == 0:
            return 100  # Avoid division by zero; RSI is 100
        else:
            rs = average_gain / average_loss
            rsi = 100 - (100 / (1 + rs))
            return rsi

    def enter_long(self):
        self.in_trade = True
        self.trade_type = "Long"
        self.entry_price = self.current_price
        self.entry_time = datetime.now().replace(second=0, microsecond=0) - timedelta(
            minutes=1
        )
        self.current_trade = {
            "Position ID": self.generate_position_id(),
            "Type": self.trade_type,
            "Entry Time": self.entry_time.strftime("%Y-%m-%d %H:%M:%S"),
            "Exit Time": None,
            "Volume": 1.0,
            "Entry Price": self.entry_price,
            "Exit Price": None,
            "Profit (USD)": None,
            "Percentage Return (%)": None,
        }

    def exit_long(self):
        if not self.in_trade or self.trade_type != "Long":
            return
        self.in_trade = False
        self.exit_price = self.current_price
        self.exit_time = datetime.now().replace(second=0, microsecond=0) - timedelta(
            minutes=1
        )
        if self.entry_price != 0:
            trade_return = (self.exit_price - self.entry_price) / self.entry_price
        else:
            trade_return = 0  # Avoid division by zero
        profit = (self.exit_price - self.entry_price) * self.current_trade["Volume"]
        self.cumulative_return += trade_return

        # Update current trade record
        self.current_trade["Exit Time"] = self.exit_time.strftime("%Y-%m-%d %H:%M:%S")
        self.current_trade["Exit Price"] = self.exit_price
        self.current_trade["Profit (USD)"] = profit
        self.current_trade["Percentage Return (%)"] = trade_return * 100

        # Record trade and write to CSV
        self.trades.append(self.current_trade)
        self.write_trade_to_csv(self.current_trade)

        # Reset current trade
        self.entry_price = None
        self.entry_time = None
        self.current_trade = None
        self.trade_type = None

    def enter_short(self):
        self.in_trade = True
        self.trade_type = "Short"
        self.entry_price = self.current_price
        self.entry_time = datetime.now().replace(second=0, microsecond=0) - timedelta(
            minutes=1
        )
        self.current_trade = {
            "Position ID": self.generate_position_id(),
            "Type": self.trade_type,
            "Entry Time": self.entry_time.strftime("%Y-%m-%d %H:%M:%S"),
            "Exit Time": None,
            "Volume": 1.0,
            "Entry Price": self.entry_price,
            "Exit Price": None,
            "Profit (USD)": None,
            "Percentage Return (%)": None,
        }

    def exit_short(self):
        if not self.in_trade or self.trade_type != "Short":
            return
        self.in_trade = False
        self.exit_price = self.current_price
        self.exit_time = datetime.now().replace(second=0, microsecond=0) - timedelta(
            minutes=1
        )
        if self.entry_price != 0:
            trade_return = (self.entry_price - self.exit_price) / self.entry_price
        else:
            trade_return = 0  # Avoid division by zero
        profit = (self.entry_price - self.exit_price) * self.current_trade["Volume"]
        self.cumulative_return += trade_return

        # Update current trade record
        self.current_trade["Exit Time"] = self.exit_time.strftime("%Y-%m-%d %H:%M:%S")
        self.current_trade["Exit Price"] = self.exit_price
        self.current_trade["Profit (USD)"] = profit
        self.current_trade["Percentage Return (%)"] = trade_return * 100

        # Record trade and write to CSV
        self.trades.append(self.current_trade)
        self.write_trade_to_csv(self.current_trade)

        # Reset current trade
        self.entry_price = None
        self.entry_time = None
        self.current_trade = None
        self.trade_type = None

    def write_trade_to_csv(self, trade):
        file_exists = os.path.isfile(self.trades_file)
        with open(self.trades_file, "a", newline="") as csvfile:
            fieldnames = [
                "Position ID",
                "Type",
                "Entry Time",
                "Exit Time",
                "Volume",
                "Entry Price",
                "Exit Price",
                "Profit (USD)",
                "Percentage Return (%)",
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            if not file_exists:
                writer.writeheader()
            writer.writerow(
                {
                    "Position ID": trade["Position ID"],
                    "Type": trade["Type"],
                    "Entry Time": trade["Entry Time"],
                    "Exit Time": trade["Exit Time"],
                    "Volume": trade["Volume"],
                    "Entry Price": trade["Entry Price"],
                    "Exit Price": trade["Exit Price"]
                    if trade["Exit Price"] is not None
                    else "",
                    "Profit (USD)": trade["Profit (USD)"]
                    if trade["Profit (USD)"] is not None
                    else "",
                    "Percentage Return (%)": trade["Percentage Return (%)"]
                    if trade["Percentage Return (%)"] is not None
                    else "",
                }
            )

    def generate_position_id(self):
        # For simplicity, generate a unique position ID using the timestamp
        return int(datetime.now().timestamp() * 1000000)

    def get_fixed_parameters(self):
        if self.in_trade:
            trade_status = self.trade_type
            current_units = self.current_trade["Volume"]
        else:
            trade_status = "Neutral"
            current_units = 0.0

        model_state = "On" if self.operational else "Off"

        params = {
            "Status": trade_status,
            "Model Status": model_state,
            "Current Units": current_units,
        }
        return params

    def get_dynamic_parameters(self):
        params = {
            "RSI Period": self.rsi_period,
            "Oversold Level": self.oversold_level,
            "Overbought Level": self.overbought_level,
        }
        return params

    def get_active_trade(self):
        if self.current_trade is None:
            return None
        else:
            trade_id = self.current_trade["Position ID"]
            trade_type = self.trade_type  # "Long" or "Short"
            entry_price = self.entry_price
            entry_time = int(
                self.entry_time.timestamp()
            )  # Convert to integer timestamp
            print(entry_time)
            units = self.current_trade["Volume"]
            current_price = self.current_price

            # Calculate profit
            if current_price is not None:
                if trade_type == "Long":
                    profit = (current_price - entry_price) * units
                elif trade_type == "Short":
                    profit = (entry_price - current_price) * units
                else:
                    profit = 0
            else:
                profit = 0

            # Calculate percentage return
            if entry_price != 0 and units != 0:
                percentage_return = (profit / (entry_price * units)) * 100
            else:
                percentage_return = 0

            # Map trade_type to integer: Long = 1, Short = 0
            trade_type_int = (
                1 if trade_type == "Long" else 0 if trade_type == "Short" else -1
            )

            return {
                "trade_id": trade_id,
                "trade_type": trade_type_int,
                "entry_price": entry_price,
                "entry_time": entry_time,
                "units": units,
                "profit": profit,
                "percentage": percentage_return,
            }


if __name__ == "__main__":
    pass
