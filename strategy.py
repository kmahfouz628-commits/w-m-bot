import pandas as pd


def calculate_indicators(df):
    df = df.copy()

    # Bollinger Bands 20 / 2
    df["bb_mid"] = df["close"].rolling(20).mean()
    df["bb_std"] = df["close"].rolling(20).std()
    df["bb_upper"] = df["bb_mid"] + (2 * df["bb_std"])
    df["bb_lower"] = df["bb_mid"] - (2 * df["bb_std"])

    # RSI 14
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))
    df["rsi"] = 100 - (100 / (1 + rs))

    # Stochastic 5,3,3
    low_5 = df["low"].rolling(5).min()
    high_5 = df["high"].rolling(5).max()

    df["stoch_k_raw"] = (
        (df["close"] - low_5) /
        (high_5 - low_5).replace(0, float("nan"))
    ) * 100

    df["stoch_k"] = df["stoch_k_raw"].rolling(3).mean()
    df["stoch_d"] = df["stoch_k"].rolling(3).mean()

    return df


def get_signal(df):
    if df is None or len(df) < 30:
        return None

    df = calculate_indicators(df)

    # نستخدم آخر شمعة مغلقة
    prev = df.iloc[-2]
    cur = df.iloc[-1]

    # -------------------------
    # شمعة رفض هابطة PUT
    # -------------------------
    body = abs(cur["close"] - cur["open"])
    upper_wick = cur["high"] - max(cur["open"], cur["close"])
    lower_wick = min(cur["open"], cur["close"]) - cur["low"]

    bearish_rejection = (
        cur["close"] < cur["open"]
        and upper_wick > body
    )

    bullish_rejection = (
        cur["close"] > cur["open"]
        and lower_wick > body
    )

    # RSI يتحرك باتجاه المنطقة الوسطى
    rsi_put = (
        prev["rsi"] >= 70
        and cur["rsi"] < prev["rsi"]
    )

    rsi_call = (
        prev["rsi"] <= 30
        and cur["rsi"] > prev["rsi"]
    )

    # Stochastic crosses
    stoch_put = (
        prev["stoch_k"] >= prev["stoch_d"]
        and cur["stoch_k"] < cur["stoch_d"]
        and cur["stoch_k"] > 80
    )

    stoch_call = (
        prev["stoch_k"] <= prev["stoch_d"]
        and cur["stoch_k"] > cur["stoch_d"]
        and cur["stoch_k"] < 20
    )

    # PUT
    put_conditions = (
        cur["high"] >= cur["bb_upper"]
        and bearish_rejection
        and rsi_put
        and stoch_put
    )

    if put_conditions:
        return {
            "signal": "PUT",
            "reason": (
                "Upper BB rejection + bearish candle + "
                "RSI falling from overbought + "
                "Stochastic bearish cross above 80"
            )
        }

    # CALL
    call_conditions = (
        cur["low"] <= cur["bb_lower"]
        and bullish_rejection
        and rsi_call
        and stoch_call
    )

    if call_conditions:
        return {
            "signal": "CALL",
            "reason": (
                "Lower BB rejection + bullish candle + "
                "RSI rising from oversold + "
                "Stochastic bullish cross below 20"
            )
        }

    return None
