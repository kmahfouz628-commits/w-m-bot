import os
import time
import sqlite3
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
from telegram import send

import store
from strategy import signal
from po_source import PocketOptionFeed


load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT = os.getenv("TELEGRAM_CHAT_ID")
SSID = os.getenv("PO_SSID")

MAX_SIGNALS = int(os.getenv("MAX_SIGNALS_PER_DAY", "4"))

# لا نضغط على Pocket Option كل 5 ثواني.
# البوت يوزع فحص الأزواج تدريجيًا.
POLL = int(os.getenv("POLL_SECONDS", "3"))

NO_SIGNAL_INTERVAL = 300

# عدد الأزواج التي نفحصها في الدورة الواحدة
BATCH_SIZE = 4

# انتظار بسيط بين طلبات البيانات
REQUEST_DELAY = 1.0

# إعادة فحص السعر/البيانات لنفس الزوج بعد هذه المدة
SYMBOL_COOLDOWN = 8

# مدة حفظ نسبة العائد في الذاكرة
PAYOUT_CACHE_SECONDS = 300


# =========================================================
# OTC PAIRS
# =========================================================

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


# =========================================================
# REAL PAIRS
# =========================================================

REAL_PAIRS = [
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


# =========================================================
# FLAGS
# =========================================================

FLAGS = {
    "AEDCNY_otc": "🇦🇪/🇨🇳",
    "AUDCAD_otc": "🇦🇺/🇨🇦",
    "AUDCHF_otc": "🇦🇺/🇨🇭",
    "AUDUSD_otc": "🇦🇺/🇺🇸",
    "CADJPY_otc": "🇨🇦/🇯🇵",
    "CHFJPY_otc": "🇨🇭/🇯🇵",
    "CHFNOK_otc": "🇨🇭/🇳🇴",
    "EURCHF_otc": "🇪🇺/🇨🇭",
    "EURHUF_otc": "🇪🇺/🇭🇺",
    "EURJPY_otc": "🇪🇺/🇯🇵",
    "EURRUB_otc": "🇪🇺/🇷🇺",
    "EURTRY_otc": "🇪🇺/🇹🇷",
    "EURUSD_otc": "🇪🇺/🇺🇸",
    "KESUSD_otc": "🇰🇪/🇺🇸",
    "MADUSD_otc": "🇲🇦/🇺🇸",
    "NGNUSD_otc": "🇳🇬/🇺🇸",
    "OMRCNY_otc": "🇴🇲/🇨🇳",
    "SARCNY_otc": "🇸🇦/🇨🇳",
    "UAHUSD_otc": "🇺🇦/🇺🇸",
    "USDARS_otc": "🇺🇸/🇦🇷",
    "USDBDT_otc": "🇺🇸/🇧🇩",
    "USDBRL_otc": "🇺🇸/🇧🇷",
    "USDCLP_otc": "🇺🇸/🇨🇱",
    "USDMXN_otc": "🇺🇸/🇲🇽",
    "USDPKR_otc": "🇺🇸/🇵🇰",
    "USDTHB_otc": "🇺🇸/🇹🇭",

    "CHFJPY": "🇨🇭/🇯🇵",
    "EURCHF": "🇪🇺/🇨🇭",
    "AUDCHF": "🇦🇺/🇨🇭",
    "EURUSD": "🇪🇺/🇺🇸",
    "CADJPY": "🇨🇦/🇯🇵",
    "AUDUSD": "🇦🇺/🇺🇸",
    "EURJPY": "🇪🇺/🇯🇵",
    "USDCAD": "🇺🇸/🇨🇦",
    "USDJPY": "🇺🇸/🇯🇵",
    "CADCHF": "🇨🇦/🇨🇭",
    "AUDCAD": "🇦🇺/🇨🇦",
    "AUDJPY": "🇦🇺/🇯🇵",
    "USDCHF": "🇺🇸/🇨🇭",
    "EURAUD": "🇪🇺/🇦🇺",
    "EURCAD": "🇪🇺/🇨🇦",
}


def get_symbols():
    return list(OTC_PAYOUTS.keys()), list(REAL_PAIRS)


# =========================================================
# PAYOUT CACHE
# =========================================================

payout_cache = {}


def get_payout_cached(feed, symbol):

    now = time.time()

    cached = payout_cache.get(symbol)

    if cached:
        payout, timestamp = cached

        if now - timestamp < PAYOUT_CACHE_SECONDS:
            return payout

    try:
        payout = feed.get_payout(symbol)

        if payout is not None:

            payout = float(payout)

            if payout <= 1:
                payout *= 100

            payout_cache[symbol] = (
                payout,
                now
            )

            return payout

    except Exception as e:
        print(
            f"Payout unavailable {symbol}: {e}"
        )

    # OTC فقط له fallback معروف
    if symbol.endswith("_otc"):

        payout = OTC_PAYOUTS.get(symbol)

        if payout is not None:

            payout_cache[symbol] = (
                payout,
                now
            )

            return payout

    return None


def payout_allowed(feed, symbol):

    payout = get_payout_cached(
        feed,
        symbol
    )

    if payout is None:
        return False, None

    if symbol.endswith("_otc"):
        return payout >= 85, payout

    return payout >= 80, payout


# =========================================================
# SAFE CONNECTION
# =========================================================

connection_state = True
connection_failures = 0


def reconnect(feed):

    global connection_state
    global connection_failures

    print("🔄 محاولة إعادة الاتصال بـ Pocket Option...")

    try:

        ok = feed.connect()

        if ok:

            connection_state = True
            connection_failures = 0

            print(
                "🟢 تمت إعادة الاتصال بنجاح"
            )

            return True

    except Exception as e:

        print(
            f"Reconnect error: {e}"
        )

    connection_state = False

    print(
        "🔴 فشل إعادة الاتصال"
   
