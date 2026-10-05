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
POLL = int(os.getenv("POLL_SECONDS", "5"))

NO_SIGNAL_INTERVAL = 300


# =========================================================
# OTC PAIRS - فقط الأزواج التي أعطيتني إياها
# النسب هنا هي النسب التي ظهرت عندك في Pocket Option
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
# REAL PAIRS - فقط القائمة التي أعطيتني إياها
# لا نضع نسبًا من عندنا.
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
    """
    OTC + REAL منفصلين تمامًا.
    لا نستخدم أي زوج آخر.
    """

    otc = list(OTC_PAYOUTS.keys())
    real = list(REAL_PAIRS)

    return otc, real


def get_real_payout(feed, symbol):
    """
    نحاول قراءة نسبة REAL الحالية من Pocket Option.
    إذا لم تكن متاحة نرجع None ولا نخترع نسبة.
    """

    try:
        payout = feed.get_payout(symbol)

        if payout is None:
            return None

        payout = float(payout)

        if payout <= 1:
            payout *= 100

        return payout

    except Exception as e:
        print(f"REAL payout error {symbol}: {e}")
        return None


def get_otc_payout(feed, symbol):
    """
    نحاول أولًا قراءة النسبة الحالية.
    إذا لم تكن متاحة نستخدم النسبة التي سجلناها من شاشة المستخدم.
    """

    try:
        payout = feed.get_payout(symbol)

        if payout is not None:
            payout = float(payout)

            if payout <= 1:
                payout *= 100

            return payout

    except Exception as e:
        print(f"Live OTC payout unavailable {symbol}: {e}")

    return OTC_PAYOUTS.get(symbol)


def payout_allowed(feed, symbol):
    """
    OTC >= 85%
    REAL >= 80%
    """

    if symbol.endswith("_otc"):
        payout = get_otc_payout(feed, symbol)

        if payout is None:
            return False, None

        return payout >= 85, payout

    payout = get_real_payout(feed, symbol)

    if payout is None:
        return False, None

    return payout >= 80, payout


def check_pending(feed):

    try:

        conn = sqlite3.connect(store.DB)

        rows = conn.execute(
            "SELECT id, symbol, signal_time, direction, entry, expiry "
            "FROM signals WHERE result='PENDING'"
        ).fetchall()

        conn.close()

        now = datetime.now(timezone.utc).timestamp()

        for row_id, symbol, signal_time, direction, entry, expiry in rows:

            if now < expiry:
                continue

            df = feed.candles_m1(symbol, 100)

            if df is None or len(df) < 2:
                continue

            target_time = float(expiry) - 60

            times = df["time"].apply(
                lambda x:
                x.timestamp()
                if hasattr(x, "timestamp")
                else float(x)
            )

            if times.empty:
                continue

            closest_index = (
                (times - target_time).abs()
            ).idxmin()

            closest_time = float(
                times.loc[closest_index]
            )

            if abs(closest_time - target_time) > 2:
                continue

            result_close = float(
                df.loc[closest_index, "close"]
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

            store.finish(signal_time, result)

            print(
                f"RESULT {symbol} {direction}: "
                f"{result} | entry={entry} | "
                f"close={result_close}"
            )

    except Exception as e:

        print("Result check error:", e)


def success_text():

    w, l, d, rate = store.stats()

    if w + l == 0:

        return (
            "📊 نسبة النجاح: لا توجد نتائج مكتملة بعد"
        )

    return (
        f"📊 نسبة النجاح: {rate:.1f}%\n"
        f"✅ أرباح: {w}\n"
        f"❌ خسائر: {l}\n"
        f"➖ تعادل: {d}"
    )


def test_pocket_option(feed, test_symbol):

    try:

        if not feed.connect():

            return (
                False,
                "🔴 Pocket Option: فشل الاتصال"
            )

        df = feed.candles_m1(
            test_symbol,
            10
        )

        if df is None or len(df) == 0:

            return (
                False,
                "🟡 Pocket Option: متصل، "
                "لكن لم تصل البيانات"
            )

        return (
            True,
            "🟢 Pocket Option: متصل\n"
            "🟢 بيانات OTC: تصل بشكل طبيعي\n"
            f"💱 اختبار البيانات: {test_symbol}\n"
            f"📊 عدد الشموع المستلمة: {len(df)}"
        )

    except Exception as e:

        return (
            False,
            "🔴 فشل فحص Pocket Option\n"
            f"❌ الخطأ: {e}"
        )


def main():

    store.db()

    if not SSID:

        raise SystemExit(
            "PO_SSID is missing. Use a DEMO session only."
        )

    feed = PocketOptionFeed(SSID)

    otc_symbols, real_symbols = get_symbols()

    test_symbol = otc_symbols[0]

    connection_ok, connection_message = (
        test_pocket_option(
            feed,
            test_symbol
        )
    )

    print(connection_message)

    if not connection_ok:

        send(
            TOKEN,
            CHAT,
            connection_message
            + "\n\n"
            + "⚠️ البوت لن يبدأ البحث."
        )

        raise SystemExit(
            "Pocket Option connection/data test failed."
        )

    send(
        TOKEN,
        CHAT,
        "🤖 تم تشغيل بوت الإشارات\n"
        "🕐 M1\n"
        "⏱️ مدة الإشارة: 3 دقائق\n"
        "🔄 استراتيجية: انعكاس\n"
        "🧪 DEMO ONLY - NO AUTOMATIC TRADES\n\n"
        + connection_message
        + "\n\n"
        + f"🟢 OTC: {len(otc_symbols)} زوج مؤهل\n"
        + f"🔵 REAL: {len(real_symbols)} زوج للمراقبة"
    )

    seen = {}

    last_no_signal_message = time.time()

    while True:

        check_pending(feed)

        if store.today_count() >= MAX_SIGNALS:

            time.sleep(30)
            continue

        found_signal = False

        # =================================================
        # أولًا OTC
        # =================================================

        for symbol in otc_symbols:

            try:

                allowed, payout = payout_allowed(
                    feed,
                    symbol
                )

                if not allowed:
                    continue

                df = feed.candles_m1(
                    symbol,
                    100
                )

                if df is None or len(df) < 40:
                    continue

                closed = df.iloc[:-1].copy()

                last_time = float(
                    closed.iloc[-1]["time"]
                )

                cid = str(int(last_time))

                key = "OTC:" + symbol

                if seen.get(key) == cid:
                    continue

                seen[key] = cid

                s = signal(closed)

                if not s:
                    continue

                found_signal = True

                signal_datetime = datetime.fromtimestamp(
                    last_time,
                    timezone.utc
                )

                expiry = (
                    signal_datetime
                    + timedelta(minutes=3)
                )

                signal_time = (
                    signal_datetime.isoformat()
                )

                s.update(
                    symbol=symbol,
                    signal_time=signal_time,
                    expiry=expiry.timestamp()
                )

                store.add(s)

                flags = FLAGS.get(
                    symbol,
                    ""
                )

                if s["direction"] == "CALL":

                    signal_title = "🟢 شراء (CALL)"
                    band = "الحد السفلي"

                else:

                    signal_title = "🔴 بيع (PUT)"
                    band = "الحد العلوي"

                entry_price = s["entry"]

                message = (
                    signal_title
                    + "\n"
                    + f"💱 الزوج: {flags} "
                    + f"{symbol.replace('_otc', ' OTC')}\n"
                    + f"💰 الدخول: {entry_price:.6f}\n"
                    + f"💵 العائد: {payout:.0f}%\n"
                    + "⏱️ المدة: 3 دقائق\n\n"
                    + success_text()
                    + "\n\n"
                    + "📊 سبب الإشارة:\n"
                    + f"• Donchian 20: لمس/كسر "
                    + f"{band}\n"
                    + "• شمعة انعكاس مؤكدة\n"
                    + f"• RSI(14): {s['rsi']:.1f}\n"
                    + f"• Stochastic(5,3,3): "
                    + f"{s['stoch_k']:.1f}\n"
                    + f"• EMA50: {s['ema50']:.6f}\n"
                    + "• شمعة التأكيد أغلقت\n\n"
                    + "🧪 DEMO ONLY\n"
                    + "🚫 NO AUTOMATIC TRADES"
                )

                send(
                    TOKEN,
                    CHAT,
                    message
                )

                print(
                    f"OTC SIGNAL {symbol}: "
                    f"{s['direction']} | "
                    f"payout={payout}"
                )

                if store.today_count() >= MAX_SIGNALS:
                    break

            except Exception as e:

                print(
                    f"OTC symbol error {symbol}: {e}"
                )

        # =================================================
        # ثانيًا REAL
        # =================================================

        if store.today_count() < MAX_SIGNALS:

            for symbol in real_symbols:

                try:

                    allowed, payout = payout_allowed(
                        feed,
                        symbol
                    )

                    if not allowed:
                        continue

                    df = feed.candles_m1(
                        symbol,
                        100
                    )

                    if df is None or len(df) < 40:
                        continue

                    closed = df.iloc[:-1].copy()

                    last_time = float(
                        closed.iloc[-1]["time"]
                    )

                    cid = str(int(last_time))

                    key = "REAL:" + symbol

                    if seen.get(key) == cid:
                        continue

                    seen[key] = cid

                    s = signal(closed)

                    if not s:
                        continue

                    found_signal = True

                    signal_datetime = (
                        datetime.fromtimestamp(
                            last_time,
                            timezone.utc
                        )
                    )

                    expiry = (
                        signal_datetime
                        + timedelta(minutes=3)
                    )

                    signal_time = (
                        signal_datetime.isoformat()
                    )

                    s.update(
                        symbol=symbol,
                        signal_time=signal_time,
                        expiry=expiry.timestamp()
                    )

                    store.add(s)

                    flags = FLAGS.get(
                        symbol,
                        ""
                    )

                    if s["direction"] == "CALL":

                        signal_title = "🟢 شراء (CALL)"
                        band = "الحد السفلي"

                    else:

                        signal_title = "🔴 بيع (PUT)"
                        band = "الحد العلوي"

                    entry_price = s["entry"]

                    message = (
                        signal_title
                        + "\n"
                        + f"💱 الزوج: {flags} "
                        + f"{symbol} REAL\n"
                        + f"💰 الدخول: {entry_price:.6f}\n"
                        + f"💵 العائد: {payout:.0f}%\n"
                        + "⏱️ المدة: 3 دقائق\n\n"
                        + success_text()
                        + "\n\n"
                        + "📊 سبب الإشارة:\n"
                        + f"• Donchian 20: لمس/كسر "
                        + f"{band}\n"
                        + "• شمعة انعكاس مؤكدة\n"
                        + f"• RSI(14): {s['rsi']:.1f}\n"
                        + f"• Stochastic(5,3,3): "
                        + f"{s['stoch_k']:.1f}\n"
                        + f"• EMA50: {s['ema50']:.6f}\n"
                        + "• شمعة التأكيد أغلقت\n\n"
                        + "🧪 DEMO ONLY\n"
                        + "🚫 NO AUTOMATIC TRADES"
                    )

                    send(
                        TOKEN,
                        CHAT,
                        message
                    )

                    print(
                        f"REAL SIGNAL {symbol}: "
                        f"{s['direction']} | "
                        f"payout={payout}"
                    )

                    if store.today_count() >= MAX_SIGNALS:
                        break

                except Exception as e:

                    print(
                        f"REAL symbol error {symbol}: {e}"
                    )

        now = time.time()

        if (
            not found_signal
            and now - last_no_signal_message
            >= NO_SIGNAL_INTERVAL
        ):

            send(
                TOKEN,
                CHAT,
                "🟡 لا توجد فرصة مطابقة حاليًا\n"
                "🔄 ما زلت أبحث..."
            )

            print(
                "NO SIGNAL: لا توجد فرصة مطابقة."
            )

            last_no_signal_message = now

        time.sleep(POLL)


if __name__ == "__main__":
    main()
