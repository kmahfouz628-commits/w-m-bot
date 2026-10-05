import os
import time
import sqlite3
import traceback
from datetime import datetime

from dotenv import load_dotenv

from po_source import PocketOptionFeed
from strategy import signal


load_dotenv()


# =========================
# SETTINGS
# =========================

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


# =========================
# OTC PAIRS
# =========================

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


# =========================
# REAL PAIRS
# =========================

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


# =========================
# DATABASE
# =========================

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
        (today + "%",),
    ).fetchone()

    conn.close()

    return int(row[0])


# =========================
# TELEGRAM
# =========================

def telegram_send(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram settings are missing.")
        print(message)
        return False

    try:
        import requests

        url = (
            "https://api.telegram.org
