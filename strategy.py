import pandas as pd
import numpy as np


# ==============================
# SETTINGS
# ==============================

DONCHIAN_PERIOD = 20
RSI_PERIOD = 14
EMA_PERIOD = 50

STOCH_K_PERIOD = 5
STOCH_SMOOTH = 3
STOCH_D_PERIOD = 3

MIN_WICK_BODY_RATIO = 1.5
MIN_BODY_RANGE_RATIO = 0.10


# ==============================
# DATA PREPARATION
# ==============================

def prepare_data(df):
    if df is None or len(df) < 60:
        return None

    data = df.copy()

    # Normalize column names
    data.columns = [str(c).lower().strip() for c in data.columns]

    required = ["open", "high", "low", "close"]

    for col in required:
        if col not in data.columns:
            return None

    for col in required:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    data = data.dropna(subset=required).reset_index(drop=True)

    if len(data) < 60:
        return None

    return data


# ==============================
# RSI 14
# ==============================

def calculate_rsi(close, period=RSI_PERIOD):
    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    rsi = 100 - (100 / (1 + rs))

    return rsi


# ==============================
# STOCHASTIC 5,3,3
# ==============================

def calculate_stochastic(data):
    lowest_low = data["low"].rolling(STOCH_K_PERIOD).min()
    highest_high = data["high"].rolling(STOCH_K_PERIOD).max()

    denominator = (highest_high - lowest_low).replace(0, np.nan)

    raw_k = (
        100
        * (data["close"] - lowest_low)
        / denominator
    )

    k = raw_k.rolling(STOCH_SMOOTH).mean()
    d = k.rolling(STOCH_D_PERIOD).mean()

    return k, d


# ==============================
# MAIN SIGNAL
# ==============================

def signal(df):

    data = prepare_data(df)

    if data is None:
        return None

    # --------------------------------
    # Indicators
    # --------------------------------

    data["rsi"] = calculate_rsi(data["close"])

    data["ema50"] = (
        data["close"]
        .ewm(span=EMA_PERIOD, adjust=False)
        .mean()
    )

    data["stoch_k"], data["stoch_d"] = calculate_stochastic(data)

    # --------------------------------
    # Donchian 20
    #
    # IMPORTANT:
    # Channel is based on the PREVIOUS
    # 20 candles, not the current candle.
    # --------------------------------

    data["donchian_upper"] = (
        data["high"]
        .shift(1)
        .rolling(DONCHIAN_PERIOD)
        .max()
    )

    data["donchian_lower"] = (
        data["low"]
        .shift(1)
        .rolling(DONCHIAN_PERIOD)
        .min()
    )

    # --------------------------------
    # Last CLOSED candle
    # --------------------------------

    current = data.iloc[-1]
    previous = data.iloc[-2]

    # Make sure indicators exist
    indicator_values = [
        current["rsi"],
        previous["rsi"],
        current["ema50"],
        current["donchian_upper"],
        current["donchian_lower"],
    ]

    if any(pd.isna(x) for x in indicator_values):
        return None

    # --------------------------------
    # Candle information
    # --------------------------------

    open_price = current["open"]
    high = current["high"]
    low = current["low"]
    close = current["close"]

    candle_range = high - low

    if candle_range <= 0:
        return None

    body = abs(close - open_price)

    upper_wick = high - max(open_price, close)
    lower_wick = min(open_price, close) - low

    # Avoid tiny / almost-doji candles
    if body <= 0:
        return None

    if (body / candle_range) < MIN_BODY_RANGE_RATIO:
        return None

    # --------------------------------
    # Donchian boundaries
    # --------------------------------

    upper = current["donchian_upper"]
    lower = current["donchian_lower"]

    # --------------------------------
    # RSI CROSS
    # --------------------------------

    # PUT:
    # Previous RSI above 70
    # Current RSI crosses below 70

    rsi_put_cross = (
        previous["rsi"] > 70
        and current["rsi"] < 70
    )

    # CALL:
    # Previous RSI below 30
    # Current RSI crosses above 30

    rsi_call_cross = (
        previous["rsi"] < 30
        and current["rsi"] > 30
    )

    # --------------------------------
    # PUT CONDITIONS
    # --------------------------------

    put_donchian_touch = high >= upper

    put_rejection = (
        close < open_price
        and upper_wick >= MIN_WICK_BODY_RATIO * body
        and upper_wick > lower_wick
        and close < upper
    )

    put_signal = (
        put_donchian_touch
        and put_rejection
        and rsi_put_cross
    )

    # --------------------------------
    # CALL CONDITIONS
    # --------------------------------

    call_donchian_touch = low <= lower

    call_rejection = (
        close > open_price
        and lower_wick >= MIN_WICK_BODY_RATIO * body
        and lower_wick > upper_wick
        and close > lower
    )

    call_signal = (
        call_donchian_touch
        and call_rejection
        and rsi_call_cross
    )

    # --------------------------------
    # EMA 50 CONTEXT
    # NOT an entry condition
    # --------------------------------

    if close > current["ema50"]:
        ema_context = "السعر فوق EMA 50"
    elif close < current["ema50"]:
        ema_context = "السعر تحت EMA 50"
    else:
        ema_context = "السعر عند EMA 50"

    # --------------------------------
    # STOCHASTIC CONTEXT
    # NOT an entry condition
    # --------------------------------

    stoch_k = current["stoch_k"]
    stoch_d = current["stoch_d"]

    if pd.isna(stoch_k) or pd.isna(stoch_d):
        stoch_context = "غير متاح"
    elif stoch_k > 80 and stoch_k < stoch_d:
        stoch_context = "يدعم PUT"
    elif stoch_k < 20 and stoch_k > stoch_d:
        stoch_context = "يدعم CALL"
    else:
        stoch_context = "غير حاسم"

    # --------------------------------
    # RETURN PUT
    # --------------------------------

    if put_signal:

        reason = (
            "انعكاس PUT | "
            "السعر لمس/كسر الحد العلوي لـ Donchian 20 | "
            "شمعة رفض هابطة بذيل علوي قوي | "
            "RSI 14 اخترق 70 للأسفل | "
            f"{ema_context} | "
            f"Stochastic: {stoch_context}"
        )

        return {
            "direction": "PUT",
            "signal": "PUT",
            "expiry": 3,
            "timeframe": "M1",
            "reason": reason,
            "rsi": round(float(current["rsi"]), 2),
            "ema50": round(float(current["ema50"]), 6),
            "stoch_k": (
                None if pd.isna(stoch_k)
                else round(float(stoch_k), 2)
            ),
            "stoch_d": (
                None if pd.isna(stoch_d)
                else round(float(stoch_d), 2)
            ),
            "donchian_upper": round(float(upper), 6),
            "donchian_lower": round(float(lower), 6),
        }

    # --------------------------------
    # RETURN CALL
    # --------------------------------

    if call_signal:

        reason = (
            "انعكاس CALL | "
            "السعر لمس/كسر الحد السفلي لـ Donchian 20 | "
            "شمعة رفض صاعدة بذيل سفلي قوي | "
            "RSI 14 اخترق 30 للأعلى | "
            f"{ema_context} | "
            f"Stochastic: {stoch_context}"
        )

        return {
            "direction": "CALL",
            "signal": "CALL",
            "expiry": 3,
            "timeframe": "M1",
            "reason": reason,
            "rsi": round(float(current["rsi"]), 2),
            "ema50": round(float(current["ema50"]), 6),
            "stoch_k": (
                None if pd.isna(stoch_k)
                else round(float(stoch_k), 2)
            ),
            "stoch_d": (
                None if pd.isna(stoch_d)
                else round(float(stoch_d), 2)
            ),
            "donchian_upper": round(float(upper), 6),
            "donchian_lower": round(float(lower), 6),
        }

    # --------------------------------
    # NO SIGNAL
    # --------------------------------

    return None
