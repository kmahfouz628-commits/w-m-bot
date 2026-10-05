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


PAIR_FLAGS = {
    "AEDCNY_otc": "🇦🇪🇨🇳",
    "AUDCAD_otc": "🇦🇺🇨🇦",
    "AUDCHF_otc": "🇦🇺🇨🇭",
    "AUDUSD_otc": "🇦🇺🇺🇸",
    "CADJPY_otc": "🇨🇦🇯🇵",
    "CHFJPY_otc": "🇨🇭🇯🇵",
    "CHFNOK_otc": "🇨🇭🇳🇴",
    "EURCHF_otc": "🇪🇺🇨🇭",
    "EURHUF_otc": "🇪🇺🇭🇺",
    "EURJPY_otc": "🇪🇺🇯🇵",
    "EURRUB_otc": "🇪🇺🇷🇺",
    "EURTRY_otc": "🇪🇺🇹🇷",
    "EURUSD_otc": "🇪🇺🇺🇸",
    "KESUSD_otc": "🇰🇪🇺🇸",
    "MADUSD_otc": "🇲🇦🇺🇸",
    "NGNUSD_otc": "🇳🇬🇺🇸",
    "OMRCNY_otc": "🇴🇲🇨🇳",
    "SARCNY_otc": "🇸🇦🇨🇳",
    "UAHUSD_otc": "🇺🇦🇺🇸",
    "USDARS_otc": "🇺🇸🇦🇷",
    "USDBDT_otc": "🇺🇸🇧🇩",
    "US
