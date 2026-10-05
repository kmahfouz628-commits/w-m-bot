import os
import time
import traceback
from datetime import datetime, timezone, timedelta

import requests
from dotenv import load_dotenv

import store
from strategy import signal
from po_source import PocketOptionFeed


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT = os.getenv("TELEGRAM_CHAT_ID", "").strip()
SSID = os.getenv("PO_SSID", "").strip()


# =========================================================
# SETTINGS
# =========================================================

MAX_SIGNALS_PER_DAY = 20
POLL_SECONDS = 5
REQUEST_DELAY = 1.0

MIN_OTC_PAYOUT = 80.0
EXPIRY_MINUTES = 3


# =========================================================
# 47 OTC PAIRS
# =========================================================

OTC_PAIRS = [
    ("AEDCNY_otc", "🇦🇪/🇨🇳 AED/CNY OTC"),
    ("AUDCAD_otc", "🇦🇺/🇨🇦 AUD/CAD OTC"),
    ("AUDCHF_otc", "🇦🇺/🇨🇭 AUD/CHF OTC"),
    ("AUDJPY_otc", "🇦🇺/🇯🇵 AUD/JPY OTC"),
    ("AUDUSD_otc", "🇦🇺/🇺🇸 AUD/USD OTC"),
    ("BHDCNY_otc", "🇧🇭/🇨🇳 BHD/CNY OTC"),
    ("CADCHF_otc", "🇨🇦/🇨🇭 CAD/CHF OTC"),
    ("CADJPY_otc", "🇨🇦/🇯🇵 CAD/JPY OTC"),
    ("CHFJPY_otc", "🇨🇭/🇯🇵 CHF/JPY OTC"),
    ("CHFNOK_otc", "🇨🇭/🇳🇴 CHF/NOK OTC"),
    ("EURCHF_otc", "🇪🇺/🇨🇭 EUR/CHF OTC"),
    ("EURHUF_otc", "🇪🇺/🇭🇺 EUR/HUF OTC"),
    ("EURJPY_otc", "🇪🇺/🇯🇵 EUR/JPY OTC"),
    ("EURRUB_otc", "🇪🇺/🇷🇺 EUR/RUB OTC"),
    ("EURTRY_otc", "🇪🇺/🇹🇷 EUR/TRY OTC"),
    ("EURUSD_otc", "🇪🇺/🇺🇸 EUR/USD OTC"),
    ("KESUSD_otc", "🇰🇪/🇺🇸 KES/USD OTC"),
    ("LBPUSD_otc", "🇱🇧/🇺🇸 LBP/USD OTC"),
    ("MADUSD_otc", "🇲🇦/🇺🇸 MAD/USD OTC"),
    ("NGNUSD_otc", "🇳🇬/🇺🇸 NGN/USD OTC"),
    ("OMRCNY_otc", "🇴🇲/🇨🇳 OMR/CNY OTC"),
    ("QARCNY_otc", "🇶🇦/🇨🇳 QAR/CNY OTC"),
    ("SARCNY_otc", "🇸🇦/🇨🇳 SAR/CNY OTC"),
    ("TNDUSD_otc", "🇹🇳/🇺🇸 TND/USD OTC"),
    ("UAHUSD_otc", "🇺🇦/🇺🇸 UAH/USD OTC"),
    ("USDARS_otc", "🇺🇸/🇦🇷 USD/ARS OTC"),
    ("USDBDT_otc", "🇺🇸/🇧🇩 USD/BDT OTC"),
    ("USDBRL_otc", "🇺🇸/🇧🇷 USD/BRL OTC"),
    ("USDCAD_otc", "🇺🇸/🇨🇦 USD/CAD OTC"),
    ("USDCHF_otc", "🇺🇸/🇨🇭 USD/CHF OTC"),
    ("USDCLP_otc", "🇺🇸/🇨🇱 USD/CLP OTC"),
    ("USDCNH_otc", "🇺🇸/🇨🇳 USD/CNH OTC"),
    ("USDCOP_otc", "🇺🇸/🇨🇴 USD/COP OTC"),
    ("USDDZD_otc", "🇺🇸/🇩🇿 USD/DZD OTC"),
    ("USDEGP_otc", "🇺🇸/🇪🇬 USD/EGP OTC"),
    ("USDIDR_otc", "🇺🇸/🇮🇩 USD/IDR OTC"),
    ("USDINR_otc", "🇺🇸/🇮🇳 USD/INR OTC"),
    ("USDJPY_otc", "🇺🇸/🇯🇵 USD/JPY OTC"),
    ("USDMXN_otc", "🇺🇸/🇲🇽 USD/MXN OTC"),
    ("USDMYR_otc", "🇺🇸/🇲🇾 USD/MYR OTC"),
    ("USDPKR_otc", "🇺🇸/🇵🇰 USD/PKR OTC"),
    ("USDRUB_otc", "🇺🇸/🇷🇺 USD/RUB OTC"),
    ("USDSGD_otc", "🇺🇸/🇸🇬 USD/SGD OTC"),
    ("USDTHB_otc", "🇺🇸/🇹🇭 USD/THB OTC"),
    ("USDVND_otc", "🇺🇸/🇻🇳 USD/VND OTC"),
    ("YERUSD_otc", "🇾🇪/🇺🇸 YER/USD OTC"),
    ("ZARUSD_otc", "🇿🇦/🇺🇸 ZAR/USD OTC"),
]


# =========================================================
# MEMORY
# =========================================================

seen_candles = {}


# =========================================================
# TELEGRAM
# =========================================================

def send_telegram(message):

    if not TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is missing")
        return False

    if not CHAT:
        print("ERROR: TELEGRAM_CHAT_ID is missing")
        return False

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT,
        "text": message,
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(
            url,
            data=payload,
            timeout=20
        )

        if response.ok:
            return True

        print(
            "Telegram error:",
            response.status_code,
            response.text
        )

    except Exception as e:
        print("Telegram connection error:", e)

    return False


# =========================================================
# CONNECTION
# =========================================================

def connect_feed():

    if not SSID:
        print("ERROR: PO_SSID is missing")
        return None

    try:
        print("Connecting to Pocket Option...")

        feed = PocketOptionFeed(SSID)

        if feed.connect():
            print("Pocket Option connected successfully")
            return feed

        print("Pocket Option connection failed")

    except Exception as e:
        print("Pocket Option connection error:", e)
        traceback.print_exc()

    return None


def feed_connected(feed):

    try:
        return (
            feed is not None
            and feed.api.check_connect()
            and feed.api.is_time_synced()
        )
    except Exception:
        return False


# =========================================================
# PAYOUT
# =========================================================

def get_current_payout(feed, symbol):

    try:
        payout = feed.get_payout(symbol)

        if payout is None:
            return None

        payout = float(payout)

        if payout <= 1:
            payout *= 100

        return payout

    except Exception as e:
        print(f"Payout error {symbol}: {e}")
        return None


# =========================================================
# CANDLES
# =========================================================

def get_candles(feed, symbol):

    try:
        df = feed.candles_m1(symbol, 100)

        if df is None or len(df) < 60:
            return None

        return df

    except Exception as e:
        print(f"Candles error {symbol}: {e}")
        return None


# =========================================================
# RESULT CHECK
# =========================================================

def check_pending(feed):

    try:

        conn = store.db()

        rows = conn.execute(
            """
            SELECT id, symbol, signal_time,
                   direction, entry, expiry
            FROM signals
            WHERE result='PENDING'
            """
        ).fetchall()

        conn.close()

        now = datetime.now(timezone.utc).timestamp()

        for (
            row_id,
            symbol,
            signal_time,
            direction,
            entry,
            expiry
        ) in rows:

            if now < expiry:
                continue

            df = feed.candles_m1(symbol, 100)

            if df is None or len(df) < 2:
                continue

            target_time = expiry - 60

            candles = df[
                df["time"].apply(
                    lambda x:
                    x.timestamp()
                    if hasattr(x, "timestamp")
                    else float(x)
                ) == target_time
            ]

            if candles.empty:
                continue

            result_close = float(
                candles.iloc[-1]["close"]
            )

            if result_close > entry:
                result = (
                    "WIN"
                    if direction == "CALL"
                    else "LOSS"
                )

            elif result_close < entry:
                result = (
                    "WIN"
                    if direction == "PUT"
                    else "LOSS"
                )

            else:
                result = "DRAW"

            store.finish(
                signal_time,
                result
            )

            print(
                f"RESULT {symbol} {direction}: "
                f"{result} | "
                f"entry={entry} | "
                f"close={result_close}"
            )

    except Exception as e:
        print("Result check error:", e)


# =========================================================
# SUCCESS RATE
# =========================================================

def success_text():

    w, l, d, rate = store.stats()

    if w + l == 0:
        return (
            "📊 SUCCESS RATE: "
            "لا توجد نتائج مكتملة بعد"
        )

    return (
        f"📊 SUCCESS RATE: {rate:.1f}%\n"
        f"🟢 WINS: {w}\n"
        f"🔴 LOSSES: {l}\n"
        f"🟡 DRAWS: {d}"
    )


# =========================================================
# SIGNAL MESSAGE
# =========================================================

def build_message(
    display_name,
    s,
    entry,
    payout
):

    if s["direction"] == "CALL":
        title = "🟢 GREEN CALL - BUY"
        level = "LOWER DONCHIAN"
    else:
        title = "🔴 RED PUT - SELL"
        level = "UPPER DONCHIAN"

    rsi = s.get("rsi")
    stoch_k = s.get("stoch_k")
    stoch_d = s.get("stoch_d")
    reason = s.get(
        "reason",
        "انعكاس مؤكد"
    )

    message = (
        f"{title}\n"
        f"━━━━━━━━━━━━━━\n"
        f"📊 PAIR: {display_name}\n"
        f"📍 {level}\n"
        f"💰 PAYOUT: {payout:.0f}%\n"
        f"⏱ TIMEFRAME: M1\n"
        f"⌛ EXPIRY: 3 MINUTES\n"
        f"💵 ENTRY: {entry}\n"
        f"━━━━━━━━━━━━━━\n"
        f"🧠 REASON:\n"
        f"{reason}\n"
        f"━━━━━━━━━━━━━━\n"
        f"📈 RSI 14: {rsi}\n"
        f"📊 Stoch K: {stoch_k}\n"
        f"📊 Stoch D: {stoch_d}\n"
        f"━━━━━━━━━━━━━━\n"
        f"{success_text()}\n"
        f"━━━━━━━━━━━━━━\n"
        f"🎯 DEMO ONLY\n"
        f"🚫 NO AUTOMATIC TRADES"
    )

    return message


# =========================================================
# PROCESS PAIR
# =========================================================

def process_pair(
    feed,
    symbol,
    display_name
):

    payout = get_current_payout(
        feed,
        symbol
    )

    if payout is None:

        print(
            f"{display_name}: "
            "payout unavailable"
        )

        return False

    print(
        f"{display_name}: "
        f"payout={payout:.0f}%"
    )

    # -----------------------------------------------------
    # PAYOUT FILTER
    # IMPORTANT:
    # Pair is NOT removed if payout is low.
    # It remains monitored and can return later.
    # -----------------------------------------------------

    if payout < MIN_OTC_PAYOUT:

        print(
            f"{display_name}: "
            f"waiting for payout >= "
            f"{MIN_OTC_PAYOUT:.0f}%"
        )

        return False

    df = get_candles(
        feed,
        symbol
    )

    if df is None:
        return False

    # -----------------------------------------------------
    # LAST CLOSED CANDLE
    # -----------------------------------------------------

    try:

        closed = df.iloc[:-1].copy()

        if len(closed) < 60:
            return False

        candle = closed.iloc[-1]

        candle_id = str(
            candle["time"]
        )

    except Exception as e:

        print(
            f"Candle preparation error "
            f"{symbol}: {e}"
        )

        return False

    # Prevent duplicate signal
    if seen_candles.get(symbol) == candle_id:
        return False

    # -----------------------------------------------------
    # STRATEGY
    # strategy.py remains unchanged
    # -----------------------------------------------------

    try:

        result = signal(closed)

    except Exception as e:

        print(
            f"Strategy error {symbol}: {e}"
        )

        traceback.print_exc()

        return False

    if not result:
        return False

    direction = result.get(
        "direction"
    )

    if direction not in (
        "CALL",
        "PUT"
    ):

        return False

    # -----------------------------------------------------
    # ENTRY
    # -----------------------------------------------------

    try:

        entry = float(
            candle["close"]
        )

    except Exception:

        return False

    # -----------------------------------------------------
    # EXPIRY
    # -----------------------------------------------------

    try:

        candle_time = candle["time"]

        if hasattr(
            candle_time,
            "timestamp"
        ):

            candle_timestamp = (
                candle_time.timestamp()
            )

        else:

            candle_timestamp = float(
                candle_time
            )

        expiry = (
            candle_timestamp
            + EXPIRY_MINUTES * 60
        )

    except Exception as e:

        print(
            f"Expiry error {symbol}: {e}"
        )

        return False

    # -----------------------------------------------------
    # SAVE SIGNAL
    # -----------------------------------------------------

    signal_data = dict(result)

    signal_data.update(
        {
            "symbol": symbol,
            "signal_time": candle_id,
            "entry": entry,
            "expiry": expiry,
        }
    )

    try:

        store.add(signal_data)

    except Exception as e:

        print(
            f"Database save error "
            f"{symbol}: {e}"
        )

        traceback.print_exc()

        return False

    # -----------------------------------------------------
    # TELEGRAM
    # -----------------------------------------------------

    message = build_message(
        display_name,
        signal_data,
        entry,
        payout
    )

    if not send_telegram(message):

        print(
            f"{display_name}: "
            "Telegram send failed"
        )

        return False

    seen_candles[
        symbol
    ] = candle_id

    print(
        f"*** SIGNAL {direction} "
        f"{display_name} "
        f"payout={payout:.0f}% ***"
    )

    return True


# =========================================================
# START MESSAGE
# =========================================================

def send_start_message():

    message = (
        "🤖 OTC SIGNAL BOT STARTED\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📊 47 OTC PAIRS\n"
        "⏱ M1\n"
        "⌛ 3 MIN EXPIRY\n"
        "💰 MIN PAYOUT: 80%\n"
        "🎯 MAX SIGNALS: 20/DAY\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🧠 REVERSAL STRATEGY\n"
        "📈 Donchian 20\n"
        "📉 RSI 14\n"
        "🕯️ Rejection Candle\n"
        "📊 Stochastic 5,3,3\n"
        "📉 EMA 50\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🎯 DEMO ONLY\n"
        "🚫 NO AUTOMATIC TRADES"
    )

    send_telegram(message)


# =========================================================
# MAIN
# =========================================================

def main():

    print("======================================")
    print("OTC SIGNAL BOT STARTING")
    print("DEMO ONLY - NO AUTOMATIC TRADES")
    print("======================================")

    if not SSID:
        print("ERROR: PO_SSID is missing")
        return

    if not TOKEN:
        print(
            "ERROR: "
            "TELEGRAM_BOT_TOKEN is missing"
        )
        return

    if not CHAT:
        print(
            "ERROR: "
            "TELEGRAM_CHAT_ID is missing"
        )
        return

    # Make sure database exists
    store.db().close()

    print(
        f"Loaded {len(OTC_PAIRS)} OTC pairs"
    )

    feed = None

    # -----------------------------------------------------
    # MAIN LOOP
    # -----------------------------------------------------

    while True:

        try:

            # =============================================
            # CONNECTION
            # =============================================

            if not feed_connected(feed):

                print(
                    "Pocket Option is not connected."
                )

                if feed is not None:

                    try:
                        feed.close()
                    except Exception:
                        pass

                feed = connect_feed()

                if feed is None:

                    print(
                        "Connection failed. "
                        "Retrying in 15 seconds..."
                    )

                    time.sleep(15)

                    continue

                print(
                    "Connection restored."
                )

                send_start_message()

            # =============================================
            # CHECK PENDING RESULTS
            # =============================================

            check_pending(feed)

            # =============================================
            # DAILY LIMIT
            # =============================================

            current_count = store.today_count()

            print(
                f"Today's signals: "
                f"{current_count}/"
                f"{MAX_SIGNALS_PER_DAY}"
            )

            if (
                current_count
                >= MAX_SIGNALS_PER_DAY
            ):

                print(
                    "Daily signal limit reached."
                )

                time.sleep(60)

                continue

            # =============================================
            # SCAN ALL 47 OTC PAIRS
            # =============================================

            for (
                symbol,
                display_name
            ) in OTC_PAIRS:

                if (
                    store.today_count()
                    >= MAX_SIGNALS_PER_DAY
                ):
                    break

                if not feed_connected(feed):

                    print(
                        "Connection lost "
                        "during scan."
                    )

                    break

                try:

                    process_pair(
                        feed,
                        symbol,
                        display_name
                    )

                except Exception as e:

                    print(
                        f"Unexpected error "
                        f"{symbol}: {e}"
                    )

                    traceback.print_exc()

                time.sleep(
                    REQUEST_DELAY
                )

            # =============================================
            # WAIT
            # =============================================

            print(
                f"Scan completed. "
                f"Waiting "
                f"{POLL_SECONDS} seconds..."
            )

            time.sleep(
                POLL_SECONDS
            )

        except KeyboardInterrupt:

            print(
                "Bot stopped manually."
            )

            if feed is not None:

                try:
                    feed.close()
                except Exception:
                    pass

            break

        except Exception as e:

            print(
                "MAIN LOOP ERROR:",
                e
            )

            traceback.print_exc()

            try:

                if feed is not None:
                    feed.close()

            except Exception:
                pass

            feed = None

            print(
                "Restarting connection "
                "in 15 seconds..."
            )

            time.sleep(15)


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()
