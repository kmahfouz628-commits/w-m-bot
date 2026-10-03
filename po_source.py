import time
import pandas as pd
from pocketoptionapi import PocketOption


class PocketOptionFeed:

    def __init__(self, ssid):
        self.ssid = ssid
        self.api = PocketOption(ssid)

    def connect(self):

        result = self.api.connect()

        if isinstance(result, tuple):
            if not result[0]:
                return False
        elif result is False:
            return False

        # انتظار الاتصال ومزامنة وقت السيرفر
        for _ in range(60):

            try:
                connected = self.api.check_connect()
                synced = self.api.is_time_synced()

                if connected and synced:
                    return True

            except Exception:
                pass

            time.sleep(1)

        return False

    def candles_m1(self, symbol, count=100):

        try:

            if not self.api.check_connect():
                return pd.DataFrame()

            if not self.api.is_time_synced():

                for _ in range(30):

                    try:
                        if self.api.is_time_synced():
                            break
                    except Exception:
                        pass

                    time.sleep(1)

            if not self.api.is_time_synced():
                return pd.DataFrame()

            # الاشتراك في بيانات الزوج M1
            try:
                self.api.subscribe(
                    symbol,
                    period=60
                )
            except Exception:
                pass

            time.sleep(1)

            candles = self.api.get_historical_candles(
                symbol,
                period=60,
                offset=45000,
                count_request=1
            )

            if not candles:
                return pd.DataFrame()

            df = pd.DataFrame(candles)

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

            if "timestamp" not in df.columns:
                return pd.DataFrame()

            df["time"] = pd.to_numeric(
                df["timestamp"],
                errors="coerce"
            )

            for col in [
                "open",
                "high",
                "low",
                "close"
            ]:
                if col not in df.columns:
                    return pd.DataFrame()

                df[col] = pd.to_numeric(
                    df[col],
                    errors="coerce"
                )

            df = df.dropna(
                subset=[
                    "open",
                    "high",
                    "low",
                    "close",
                    "time"
                ]
            )

            df = df.sort_values("time")

            return df.tail(count).reset_index(drop=True)

        except Exception as e:

            print(
                f"Historical candles error "
                f"{symbol}: {e}"
            )

            return pd.DataFrame()

    def close(self):

        try:
            self.api.disconnect_websocket()
        except Exception:
            pass
