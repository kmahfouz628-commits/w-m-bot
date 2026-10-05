import os
import time
import sqlite3
import traceback
from datetime import datetime

from dotenv import load_dotenv
from po_source import PocketOptionFeed
from strategy import signal

load_dotenv()

PO_SSID = os.getenv("PO_SSID", "").strip()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()

MAX_SIGNALS_PER_DAY = 4
POLL_SECONDS = 3
BATCH_SIZE = 4
REQUEST_DELAY = 1.0

MIN_OTC_PAYOUT = 85.0
MIN_REAL_PAYOUT = 80.0

DB_FILE = "signals.db"

OTC_PAYOUTS = {
    "AEDCNY_otc": 92,
    "AUDCAD_otc": 92,
    "AUDCHF_otc": 85,
    "AUDUSD_otc": 92,
    "CADJPY_otc": 92,
    "CHFJPY_otc": 92,
    "CHFNOK_otc": 91,
    "EURCHF_otc": 92,
    "EURHUF_otc": 92,
    "EURJPY_otc": 92,
    "EURRUB_otc": 92,
    "EURTRY_otc": 91,
    "EURUSD_otc": 92,
    "KESUSD_otc": 92,
    "MADUSD_otc": 92,
    "NGNUSD_otc": 92,
    "OMRCNY_otc": 92,
    "SARCNY_otc": 92,
    "UAHUSD_otc": 86,
    "USDARS_otc": 92,
    "USDBDT_otc": 92,
    "USDBRL_otc": 92,
    "USDCLP_otc": 91,
    "USDMXN_otc": 92,
    "USDPKR_otc": 92,
    "USDTHB_otc": 92,
}

REAL_SYMBOLS = [
    "CHFJPY",
    "EURCHF",
    "AUDCHF",
    "EURUSD",
    "CADJPY",
    "AUDUSD",
    "EURJPY",
    "USDCAD",
    "USDJPY",
    "CADCHF",
    "AUDCAD",
    "AUDJPY",
    "USDCHF",
    "EURAUD",
    "EURCAD",
]

CURRENCY_REGION = {
    "AED": "AE",
    "AUD": "AU",
    "CAD": "CA",
    "CHF": "CH",
    "CNY": "CN",
    "NOK": "NO",
    "EUR": "EU",
    "HUF": "HU",
    "JPY": "JP",
    "RUB": "RU",
    "TRY": "TR",
    "KES": "KE",
    "USD": "US",
    "MAD": "MA",
    "NGN": "NG",
    "OMR": "OM",
    "SAR": "SA",
    "UAH": "UA",
    "ARS": "AR",
    "BDT": "BD",
    "BRL": "BR",
    "CLP": "CL",
    "MXN": "MX",
    "PKR": "PK",
    "THB": "TH",
}


def region_flag(region):
    if len(region) != 2:
        return "🌐"

    return "".join(
        chr(127397 + ord(letter))
        for letter in region.upper()
    )


def flag_for_symbol(symbol):
    clean = symbol.replace("_otc", "")

    if len(clean) < 6:
        return "🌐"

    base = clean[:3]
    quote = clean[3:6]

    base_region = CURRENCY_REGION.get(base)
    quote_region = CURRENCY_REGION.get(quote)

    if not base_region or not quote_region:
        return "🌐"

    return (
        region_flag(base_region)
        + region_flag(quote_region)
    )


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


def save_signal(symbol, market, direction, entry, expiry, payout):
    conn = sqlite3.connect(DB_FILE)

    conn.execute(
        """
        INSERT INTO signals
        (created_at, symbol, market, direction, entry, expiry, payout, result)
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
        "SELECT COUNT(*) FROM signals WHERE created_at LIKE ?",
        (today + "%",),
    ).fetchone()

    conn.close()

    return int(row[0])


def telegram_send(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram settings are missing.")
        print(message)
        return False

    try:
        import requests

        url = (
            "https://api.telegram.org/bot"
            + BOT_TOKEN
            + "/sendMessage"
        )

        response = requests.post(
            url,
            data={
                "chat_id": CHAT_ID,
                "text": message,
            },
            timeout=15,
        )

        return response.ok

    except Exception as e:
        print("Telegram error:", e)
        return False


payout_cache = {}


def get_payout(feed, symbol, market):
    now = time.time()

    cached = payout_cache.get(symbol)

    if cached:
        payout_value, saved_time = cached

        if now - saved_time < 300:
            return payout_value

    if market == "OTC":
        payout = OTC_PAYOUTS.get(symbol)

        if payout is not None:
            payout_cache[symbol] = (payout, now)
            return float(payout)

    try:
        payout = feed.get_payout(symbol)

        if payout is not None:
            payout = float(payout)

            if payout <= 1:
                payout *= 100

            payout_cache[symbol] = (payout, now)

            return payout

    except Exception as e:
        print("Payout error:", symbol, e)

    return None


def connect_feed():
    if not PO_SSID:
        print("PO_SSID is missing.")
        return None

    try:
        feed = PocketOptionFeed(PO_SSID)

        print("Connecting to Pocket Option...")

        if feed.connect():
            print("Pocket Option connected.")
            return feed

        print("Pocket Option connection failed.")

    except Exception as e:
        print("Connection error:", e)

    return None


def safe_candles(feed, symbol, count=100):
    try:
        df = feed.candles_m1(symbol, count)

        if df is None:
            return None

        if len(df) < 30:
            return None

        return df

    except Exception as e:
        print("Candles error:", symbol, e)
        return None


def build_message(symbol, market, sig, payout):
    direction = sig.get("direction", "")

    if direction == "CALL":
        icon = "🟢"
    else:
        icon = "🔴"

    flag = flag_for_symbol(symbol)

    rsi = sig.get("rsi", 0)
    ema = sig.get("ema50", 0)
    stoch_k = sig.get("stoch_k", 0)
    stoch_d = sig.get("stoch_d", 0)
    upper = sig.get("donchian_upper", 0)
    lower = sig.get("donchian_lower", 0)

    reason = sig.get(
        "reason",
        "Donchian rejection + RSI confirmation",
    )

    message = (
        icon + " " + direction + "\n\n"
        + flag + " " + symbol + "\n"
        + "📊 السوق: " + market + "\n"
        + "💰 العائد: " + str(round(payout)) + "%\n"
        + "⏱️ الإطار: M1\n"
        + "⌛ الانتهاء: 3 دقائق\n\n"
        + "📌 السبب:\n"
        + str(reason) + "\n\n"
        + "📈 RSI 14: " + str(round(rsi, 2)) + "\n"
        + "📊 Stochastic K/D: "
        + str(round(stoch_k, 2))
        + " / "
        + str(round(stoch_d, 2))
        + "\n"
        + "📉 EMA 50: " + str(round(ema, 6)) + "\n"
        + "📏 Donchian 20:\n"
        + "Upper: " + str(round(upper, 6)) + "\n"
        + "Lower: " + str(round(lower, 6)) + "\n\n"
        + "🧪 DEMO ONLY - NO AUTOMATIC TRADES"
    )

    return message


def process_symbol(feed, symbol, market):
    payout = get_payout(feed, symbol, market)

    if payout is None:
        print(symbol, ": payout unavailable")
        return False

    if market == "OTC":
        if payout < MIN_OTC_PAYOUT:
            print(
                symbol,
                ": payout",
                payout,
                "below OTC minimum",
            )
            return False
    else:
        if payout < MIN_REAL_PAYOUT:
            print(
                symbol,
                ": payout",
                payout,
                "below REAL minimum",
            )
            return False

    print(
        "Checking",
        symbol,
        "|",
        market,
        "| payout",
        round(payout),
    )

    df = safe_candles(feed, symbol, 100)

    if df is None:
        print(symbol, ": no candle data")
        return False

    try:
        sig = signal(df)

    except Exception as e:
        print("Strategy error:", symbol, e)
        return False

    if not sig:
        return False

    direction = sig.get("direction")

    if direction not in ("CALL", "PUT"):
        return False

    entry = sig.get("entry", 0)
    expiry = sig.get("expiry", 3)

    save_signal(
        symbol,
        market,
        direction,
        entry,
        expiry,
        payout,
    )

    message = build_message(
        symbol,
        market,
        sig,
        payout,
    )

    telegram_send(message)

    print(
        "NEW SIGNAL:",
        symbol,
        direction,
    )

    return True


def main():
    print("================================")
    print("OTC SIGNAL BOT STARTED")
    print("M1 - 3 MIN EXPIRY")
    print("Strategy: Reversal")
    print("DEMO ONLY - NO AUTOMATIC TRADES")
    print("================================")

    init_db()

    print("OTC pairs:", len(OTC_PAYOUTS))
    print("REAL pairs:", len(REAL_SYMBOLS))

    feed = connect_feed()

    if feed is None:
        telegram_send(
            "🔴 فشل الاتصال بـ Pocket Option\n"
            "البوت متوقف مؤقتًا."
        )
        return

    telegram_send(
        "🤖 تم تشغيل بوت الإشارات\n"
        "🕐 M1\n"
        "⏱️ مدة الإشارة: 3 دقائق\n"
        "🔄 استراتيجية: انعكاس\n"
        "🧪 DEMO ONLY - NO AUTOMATIC TRADES\n\n"
        "🟢 Pocket Option: متصل\n"
        + "🟢 OTC: "
        + str(len(OTC_PAYOUTS))
        + " زوج مؤهل\n"
        + "🔵 REAL: "
        + str(len(REAL_SYMBOLS))
        + " زوج للمراقبة"
    )

    all_symbols = []

    for symbol in OTC_PAYOUTS:
        all_symbols.append((symbol, "OTC"))

    for symbol in REAL_SYMBOLS:
        all_symbols.append((symbol, "REAL"))

    position = 0
    last_status = 0

    while True:
        try:
            if signals_today() >= MAX_SIGNALS_PER_DAY:
                print("Daily signal limit reached.")
                time.sleep(60)
                continue

            if not feed.api.check_connect():
                print("Pocket Option disconnected.")

                try:
                    feed.close()
                except Exception:
                    pass

                time.sleep(5)

                feed = connect_feed()

                if feed is None:
                    time.sleep(30)
                    continue

                continue

            checked = 0
            found_signal = False

            while (
                checked < BATCH_SIZE
                and position < len(all_symbols)
            ):
                symbol, market = all_symbols[position]

                position += 1
                checked += 1

                if process_symbol(
                    feed,
                    symbol,
                    market,
                ):
                    found_signal = True

                    if signals_today() >= MAX_SIGNALS_PER_DAY:
                        break

                time.sleep(REQUEST_DELAY)

            if position >= len(all_symbols):
                position = 0

            now = time.time()

            if (
                not found_signal
                and now - last_status > 300
            ):
                print(
                    "No matching opportunity currently."
                )

                telegram_send(
                    "🟡 لا توجد فرصة مطابقة حاليًا\n"
                    "🔄 ما زلت أبحث..."
                )

                last_status = now

            time.sleep(POLL_SECONDS)

        except KeyboardInterrupt:
            print("Bot stopped.")
            break

        except Exception as e:
            print("MAIN LOOP ERROR:", e)
            traceback.print_exc()
            time.sleep(10)

    try:
        feed.close()
    except Exception:
        pass


if __name__ == "__main__":
    main()
