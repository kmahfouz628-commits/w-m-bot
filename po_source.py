import time
import pandas as pd
from pocketoptionapi import PocketOption


class PocketOptionFeed:
    def __init__(self, ssid):
        self.ssid = ssid
        self.api = PocketOption(ssid)

    def connect(self):
        self.api.connect()

        for _ in range(20):
            if self.api.check_connect():
                return True
            time.sleep(1)

        return False

    def candles_m1(self, symbol, count=100):
        candles = self.api.get_historical_candles(
            symbol,
            60,
            int(time.time()),
            None,
            1
        )

        if not candles:
            return pd.DataFrame()

        df = pd.DataFrame(candles)

        # توحيد أسماء الأعمدة
        rename_map = {
            "from": "timestamp",
            "time": "timestamp",
            "at": "timestamp",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close"
        }

        df = df.rename(columns=rename_map)

        required = ["open", "high", "low", "close"]

        if not all(col in df.columns for col in required):
            return pd.DataFrame()

        for col in required:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=required)

        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_numeric(
                df["timestamp"],
                errors="coerce"
            )

        df = df.sort_values(
            "timestamp" if "timestamp" in df.columns else df.index
        )

        return df.tail(count).reset_index(drop=True)

    def close(self):
        try:
            self.api.disconnect_websocket()
        except Exception:
            pass
