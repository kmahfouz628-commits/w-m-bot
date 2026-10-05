import os
import time
import sqlite3
import traceback
from datetime import datetime

import requests
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
EXPIRY_MINUTES = 3

DB_FILE = "signals.db"


# =========================================================
# ALL 47 OTC PAIRS
# =========================================================

OTC_SYMBOLS = [
    "AEDCNY_otc",
    "AUDCAD_otc",
    "AUDCHF_otc",
    "AUDJPY_otc",
    "AUDUSD_otc",
    "BHDCNY_otc",
    "CADCHF_otc",
    "CADJPY_otc",
    "CHFJPY_otc",
    "CHFNOK_otc",
    "EURCHF_otc",
    "EURHUF_otc",
    "EURJPY_otc",
    "EURRUB_otc",
    "EURTRY_otc",
    "EURUSD_otc",
    "KESUSD_otc",
    "LBPUSD_otc",
    "MADUSD_otc",
    "NGNUSD_otc",
    "OMRCNY_otc",
    "QARCNY_otc",
    "SARCNY_otc",
    "TNDUSD_otc",
    "UAHUSD_otc",
    "USDARS_otc",
    "USDBDT_otc",
    "USDBRL_otc",
    "USDCAD_otc",
    "USDCHF_otc",
    "USDCLP_otc",
    "USDCNH_otc",
    "USDCOP_otc",
    "USDDZD_otc",
    "USDEGP_otc",
    "USDIDR_otc",
    "USDINR_otc",
    "USDJPY_otc",
    "USDMXN_otc",
    "USDMYR_otc",
    "USDPKR_otc",
    "USDRUB_otc",
    "USDSGD_otc",
    "USDTHB_otc",
    "USDVND_otc",
    "YERUSD_otc",
    "ZARUSD_otc",
]


# =========================================================
# CURRENCY FLAGS
# =========================================================

CURRENCY_REGION = {
    "AED": "AE",
    "AUD": "AU",
    "BHD": "BH",
    "CAD": "CA",
    "CHF": "CH",
    "CNY": "CN",
    "CNH": "CN",
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
    "QAR": "QA",
    "SAR": "SA",
    "TND": "TN",
    "UAH": "UA",
    "ARS": "AR",
    "BDT": "BD",
    "BRL": "BR",
    "CLP": "CL",
    "COP": "CO",
    "DZD": "DZ",
    "EGP": "EG",
    "IDR": "ID",
    "INR": "IN",
    "MXN": "MX",
    "MYR": "MY",
    "PKR": "PK",
    "SGD": "SG",
    "THB": "TH",
    "VND": "VN",
    "YER": "YE",
    "ZAR": "ZA",
}


def region_flag(region):
    if not region or len(region) != 2:
        return "🌐"

    return "".join(
        chr(127397 + ord(letter))
        for letter in region.upper()
    )


def flag_for_symbol(symbol):
    clean = symbol.replace("_otc", "").upper()

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
        + "/"
        + region_flag(quote_region)
    )


def display_symbol(symbol):
    clean = symbol.replace("_otc", "").upper()

    if len(clean) < 6:
        return clean + " OTC"

    return (
        flag_for_symbol(symbol)
        + " "
        + clean[:3]
        + "/"
        + clean[3:6]
        + " OTC"
    )


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
