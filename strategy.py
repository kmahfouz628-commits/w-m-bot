import pandas as pd


BB_PERIOD = 20
BB_STD = 2.0

RSI_PERIOD = 14

STOCH_K = 5
STOCH_SMOOTH = 3
STOCH_D = 3


def indicators(df):
    x = df.copy()

    # Bollinger Bands 20 / 2
    mid = x["close"].rolling(BB_PERIOD).mean()
    std = x["close"].rolling(BB_PERIOD).std(ddof=0)

    x["bb_mid"] = mid
    x["bb_upper"] = mid + (BB_STD * std)
    x["bb_lower"] = mid - (BB_STD * std)

    # RSI 14
    delta = x["close"].diff()

    gain = delta.clip(lower=0).rolling(RSI_PERIOD).mean()
    loss = (-delta.clip(upper=0)).rolling(RSI_PERIOD).mean()

    rs = gain / loss.replace(0, float("nan"))
    x["rsi"] = 100 - (100 / (1 + rs))

    # Stochastic 5,3,3
    low = x["low"].rolling(STOCH_K).min()
    high = x["high"].rolling(STOCH_K).max()

    raw = (
        100 * (x["close"] - low) /
        (high - low).replace(0, float("nan"))
    )

    x["stoch_k"] = raw.rolling(STOCH_SMOOTH).mean()
    x["stoch_d"] = x["stoch_k"].rolling(STOCH_D).mean()

    return x


def rejection(candle, side):
    body = abs(candle["close"] - candle["open"])

    if body == 0:
        return False

    if side == "CALL":
        lower_wick = (
            min(candle["open"], candle["close"])
            - candle["low"]
        )

        return (
            candle["close"] > candle["open"]
            and lower_wick >= body
        )

    upper_wick = (
        candle["high"]
        - max(candle["open"], candle["close"])
    )

    return (
        candle["close"] < candle["open"]
        and upper_wick >= body
    )


def signal(df):
    if df is None or len(df) < 40:
        return None

    x = indicators(df).dropna()

    if len(x) < 3:
        return None

    # آخر شمعتين مغلقتين
    prev = x.iloc[-2]
    cur = x.iloc[-1]

    # CALL
    call = (
        cur["low"] <= cur["bb_lower"]
        and rejection(cur, "CALL")

        and prev["rsi"] <= 30
        and cur["rsi"] > prev["rsi"]
        and cur["rsi"] < 50

        and prev["stoch_k"] <= 20
        and cur["stoch_k"] > prev["stoch_k"]
        and cur["stoch_k"] > cur["stoch_d"]
    )

    # PUT
    put = (
        cur["high"] >= cur["bb_upper"]
        and rejection(cur, "PUT")

        and prev["rsi"] >= 70
        and cur["rsi"] < prev["rsi"]
        and cur["rsi"] > 50

        and prev["stoch_k"] >= 80
        and cur["stoch_k"] < prev["stoch_k"]
        and cur["stoch_k"] < cur["stoch_d"]
    )

    if not call and not put:
        return None

    if call:
        direction = "CALL"
        band = "LOWER BAND"
        emoji = "🟢"

    else:
        direction = "PUT"
        band = "UPPER BAND"
        emoji = "🔴"

    try:
        signal_time = pd.to_datetime(
            cur["time"],
            unit="s",
            utc=True
        )
    except Exception:
        signal_time = pd.to_datetime(
            cur["time"],
            utc=True
        )

    reason = (
        f"{emoji} {direction}\n"
        f"• Bollinger Bands: {band} touch/break\n"
        f"• Rejection candle confirmed\n"
        f"• RSI(14): {prev['rsi']:.1f} → {cur['rsi']:.1f}\n"
        f"• Stochastic K: "
        f"{prev['stoch_k']:.1f} → {cur['stoch_k']:.1f}\n"
        f"• Stochastic D: {cur['stoch_d']:.1f}\n"
        f"• Confirmation candle CLOSED"
    )

    return {
        "direction": direction,
        "entry": float(cur["close"]),
        "time": signal_time,
        "reason": reason,
        "rsi": float(cur["rsi"]),
        "stoch_k": float(cur["stoch_k"]),
        "stoch_d": float(cur["stoch_d"]),
        "indicators_confirmed": 3,
        "total_indicators": 3,
        "auto_trade": False,
        "expiry_minutes": 3
    }
