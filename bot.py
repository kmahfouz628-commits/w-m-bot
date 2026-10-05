import os
import time
import sqlite3
import traceback
from datetime import datetime

import requests
from dotenv import load_dotenv

from po_source import PocketOptionFeed
from strategy import signal


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()

PO_SSID = os.getenv("PO_SSID", "").strip()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()


# =========================================================
# SETTINGS
# =========================================================

MAX_SIGNALS_PER_DAY = 4
POLL_SECONDS = 5
REQUEST_DELAY = 1.0

MIN_OTC_PAYOUT = 85.0
EXPIRY_MINUTES = 3

DB_FILE = "signals.db"


# =========================================================
# 47 OTC PAIRS + FIXED FLAGS
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
# RUNTIME MEMORY
# Prevent repeated signals from the same candle
# =========================================================

last_signal_candle = {}


# =========================================================
# DATABASE
# =========================================================

def init_db():
    conn = sqlite3.connect(DB_FILE)

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            symbol TEXT,
            market TEXT,
            direction TEXT,
            entry REAL,
            expiry INTEGER,
            payout REAL,
            result TEXT DEFAULT 'PENDING'
        )
        """
    )

    conn.commit()
    conn.close()


def save_signal(
    symbol,
    market,
    direction,
    entry,
    expiry,
    payout
):
    conn = sqlite3.connect(DB_FILE)

    conn.execute(
        """
        INSERT INTO signals
        (
            created_at,
            symbol,
            market,
            direction,
            entry,
            expiry,
            payout,
            result
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING')
        """,
        (
            datetime.now().isoformat(),
            symbol,
            market,
            direction,
            entry,
            expiry,
            payout,
        ),
    )

    conn.commit()
    conn.close()


def signals_today():
    today = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_FILE)

    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM signals
        WHERE created_at LIKE ?
        """,
        (today + "%",)
    ).fetchone()

    conn.close()

    return int(row[0] or 0)


# =========================================================
# TELEGRAM
# =========================================================

def send_telegram(message):
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN is missing")
        return False

    if not CHAT_ID:
        print("ERROR: CHAT_ID is missing")
        return False

    url = (
        "https://api.telegram.org/bot"
        + BOT_TOKEN
        + "/sendMessage"
    )

    payload = {
        "chat_id": CHAT_ID,
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

        return False

    except Exception as e:
        print("Telegram connection error:", e)
        return False


# =========================================================
# POCKET OPTION
# =========================================================

def connect_feed():
    if not PO_SSID:
        print("ERROR: PO_SSID is missing")
        return None

    try:
        print("Connecting to Pocket Option...")

        feed = PocketOptionFeed(PO_SSID)

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
# CANDLES
# =========================================================

def get_candles(feed, symbol):
    try:
        df = feed.candles_m1(symbol, 100)

        if df is None:
            return None

        if len(df) < 60:
            print(
                f"{symbol}: not enough candles "
                f"({len(df)})"
            )
            return None

        return df

    except Exception as e:
        print(
            f"Candles error {symbol}: {e}"
        )
        return None


# =========================================================
# PAYOUT
# IMPORTANT:
# We NEVER remove a pair because of payout.
# Payout is checked dynamically.
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
        print(
            f"Payout error {symbol}: {e}"
        )
        return None


# =========================================================
# MESSAGE
# =========================================================

def build_signal_message(
    display_name,
    result,
    payout,
    entry
):
    direction = result.get("direction", "")

    if direction == "CALL":
        header = "🟢 CALL"
    else:
        header = "🔴 PUT"

    rsi = result.get("rsi")
    ema50 = result.get("ema50")
    stoch_k = result.get("stoch_k")
    stoch_d = result.get("stoch_d")

    reason = result.get(
        "reason",
        "إشارة انعكاس مؤكدة"
    )

    message = (
        f"{header}\n"
        f"━━━━━━━━━━━━━━\n"
        f"📊 {display_name}\n"
        f"💰 Payout: {payout:.0f}%\n"
        f"⏱ الإطار: M1\n"
        f"⌛ الانتهاء: {EXPIRY_MINUTES} دقائق\n"
        f"💵 سعر الدخول: {entry}\n"
        f"━━━━━━━━━━━━━━\n"
        f"🧠 السبب:\n"
        f"{reason}\n"
        f"━━━━━━━━━━━━━━\n"
        f"📈 RSI 14: {rsi}\n"
        f"📉 EMA 50: {ema50}\n"
        f"📊 Stoch K: {stoch_k}\n"
        f"📊 Stoch D: {stoch_d}\n"
        f"━━━━━━━━━━━━━━\n"
        f"🟡 OTC\n"
        f"🎯 DEMO ONLY\n"
        f"🚫 NO AUTOMATIC TRADES"
    )

    return message


# =========================================================
# PROCESS ONE PAIR
# =========================================================

def process_pair(feed, symbol, display_name):
    payout = get_current_payout(feed, symbol)

    if payout is None:
        print(
            f"{display_name}: payout unavailable"
        )
        return False

    print(
        f"{display_name}: payout = {payout:.0f}%"
    )

    # IMPORTANT:
    # Pair stays in monitoring even when payout < 85%.
    if payout < MIN_OTC_PAYOUT:
        print(
            f"{display_name}: waiting "
            f"(payout below {MIN_OTC_PAYOUT:.0f}%)"
        )
        return False

    df = get_candles(feed, symbol)

    if df is None:
        return False

    try:
        candle_time = df.iloc[-1]["time"]
    except Exception:
        candle_time = None

    # Prevent repeated signal from same candle
    if (
        candle_time is not None
        and last_signal_candle.get(symbol) == candle_time
    ):
        return False

    try:
        result = signal(df)
    except Exception as e:
        print(
            f"Strategy error {symbol}: {e}"
        )
        traceback.print_exc()
        return False

    if not result:
        return False

    direction = result.get("direction")

    if direction not in ("CALL", "PUT"):
        print(
            f"{symbol}: invalid signal"
        )
        return False

    try:
        entry = float(df.iloc[-1]["close"])
    except Exception:
        entry = 0.0

    message = build_signal_message(
        display_name,
        result,
        payout,
        entry
    )

    print(
        f"*** SIGNAL {direction} "
        f"{display_name} ***"
    )

    if not send_telegram(message):
        print(
            f"{display_name}: "
            f"Telegram send failed"
        )
        return False

    save_signal(
        symbol=symbol,
        market="OTC",
        direction=direction,
        entry=entry,
        expiry=EXPIRY_MINUTES,
        payout=payout
    )

    if candle_time is not None:
        last_signal_candle[symbol] = candle_time

    print(
        f"Signal sent successfully: "
        f"{display_name} {direction}"
    )

    return True


# =========================================================
# START MESSAGE
# =========================================================

def send_start_message():
    message = (
        "🤖 OTC SIGNAL BOT STARTED\n"
        "━━━━━━━━━━━━━━\n"
        "📊 47 OTC PAIRS\n"
        "⏱ M1\n"
        "⌛ 3 MIN EXPIRY\n"
        "💰 MIN PAYOUT: 85%\n"
        "🎯 MAX SIGNALS: 4/DAY\n"
        "━━━━━━━━━━━━━━\n"
        "🧠 REVERSAL STRATEGY\n"
        "📈 Donchian 20\n"
        "📉 RSI 14\n"
        "📊 EMA 50\n"
        "📊 Stochastic 5,3,3\n"
        "━━━━━━━━━━━━━━\n"
        "🎯 DEMO ONLY\n"
        "🚫 NO AUTOMATIC TRADES"
    )

    send_telegram(message)


# =========================================================
# MAIN LOOP
# =========================================================

def main():
    print("======================================")
    print("OTC SIGNAL BOT STARTING")
    print("DEMO ONLY - NO AUTOMATIC TRADES")
    print("======================================")

    if not PO_SSID:
        print("ERROR: PO_SSID is missing")
        return

    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN is missing")
        return

    if not CHAT_ID:
        print("ERROR: CHAT_ID is missing")
        return

    init_db()

    print(
        f"Loaded {len(OTC_PAIRS)} OTC pairs"
    )

    feed = None

    while True:
        try:
            # -------------------------------------------------
            # CONNECTION
            # -------------------------------------------------

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

            # -------------------------------------------------
            # DAILY LIMIT
            # -------------------------------------------------

            current_count = signals_today()

            print(
                f"Today's signals: "
                f"{current_count}/{MAX_SIGNALS_PER_DAY}"
            )

            if current_count >= MAX_SIGNALS_PER_DAY:
                print(
                    "Daily signal limit reached. "
                    "Waiting for next day..."
                )

                time.sleep(60)

                continue

            # -------------------------------------------------
            # SCAN ALL 47 PAIRS
            # -------------------------------------------------

            for symbol, display_name in OTC_PAIRS:

                if signals_today() >= MAX_SIGNALS_PER_DAY:
                    break

                if not feed_connected(feed):
                    print(
                        "Connection lost during scan."
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

                time.sleep(REQUEST_DELAY)

            # -------------------------------------------------
            # WAIT BEFORE NEXT SCAN
            # -------------------------------------------------

            print(
                f"Scan completed. "
                f"Waiting {POLL_SECONDS} seconds..."
            )

            time.sleep(POLL_SECONDS)

        except KeyboardInterrupt:
            print("Bot stopped manually.")

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
