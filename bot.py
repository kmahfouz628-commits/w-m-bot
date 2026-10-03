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

SYMBOLS = [
    x.strip()
    for x in os.getenv(
        "OTC_SYMBOLS",
        "EURUSD_otc,GBPUSD_otc"
    ).split(",")
    if x.strip()
]

MAX = int(os.getenv("MAX_SIGNALS_PER_DAY", "4"))
POLL = int(os.getenv("POLL_SECONDS", "5"))


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
        return "📊 نسبة النجاح: لا توجد نتائج مكتملة بعد"

    return (
        f"📊 نسبة النجاح: {rate:.1f}%\n"
        f"✅ أرباح: {w}\n"
        f"❌ خسائر: {l}\n"
        f"➖ تعادل: {d}"
    )


def main():

    store.db()

    if not SSID:
        raise SystemExit(
            "PO_SSID is missing. Use a DEMO session only."
        )

    feed = PocketOptionFeed(SSID)

    if not feed.connect():
        raise SystemExit(
            "Pocket Option connection failed."
        )

    seen = {}

    send(
        TOKEN,
        CHAT,
        "🤖 تم تشغيل بوت إشارات OTC\n"
        "🕐 فريم: دقيقة واحدة (M1)\n"
        "⏱️ مدة الإشارة: 3 دقائق\n"
        "🧪 تجريبي فقط — بدون تنفيذ تلقائي"
    )

    while True:

        check_pending(feed)

        if store.today_count() >= MAX:
            time.sleep(30)
            continue

        for symbol in SYMBOLS:

            try:
                df = feed.candles_m1(symbol, 100)

                if df is None or len(df) < 40:
                    continue

                closed = df.iloc[:-1].copy()

                last_time = float(
                    closed.iloc[-1]["time"]
                )

                cid = str(int(last_time))

                if seen.get(symbol) == cid:
                    continue

                seen[symbol] = cid

                s = signal(closed)

                if not s:
                    continue

                signal_datetime = datetime.fromtimestamp(
                    last_time,
                    timezone.utc
                )

                expiry = (
                    signal_datetime
                    + timedelta(minutes=3)
                )

                signal_time = signal_datetime.isoformat()

                s.update(
                    symbol=symbol,
                    signal_time=signal_time,
                    expiry=expiry.timestamp()
                )

                store.add(s)

                if s["direction"] == "CALL":

                    signal_title = "🟢 شراء (CALL)"
                    band = "الحد السفلي"

                else:

                    signal_title = "🔴 بيع (PUT)"
                    band = "الحد العلوي"

                entry_price = s["entry"]

                message = (
                    signal_title + "\n"
                    + f"💱 الزوج: {symbol.replace('_otc', ' OTC')}\n"
                    + f"💰 سعر الدخول: {entry_price:.6f}\n"
                    + "⏱️ مدة الإشارة: 3 دقائق\n\n"
                    + success_text() + "\n\n"
                    + "📊 سبب الإشارة:\n"
                    + f"• بولينجر باند: لمس/كسر {band}\n"
                    + "• شمعة رفض مؤكدة\n"
                    + f"• RSI(14): {s['rsi']:.1f}\n"
                    + f"• ستوكاستك (5,3,3): "
                    + f"{s['stoch_k']:.1f}\n"
                    + "• شمعة التأكيد أغلقت\n\n"
                    + "🧪 تجريبي فقط — بدون تنفيذ تلقائي"
                )

                send(
                    TOKEN,
                    CHAT,
                    message
                )

                print(
                    f"SIGNAL {symbol}: "
                    f"{s['direction']} | "
                    f"entry={entry_price}"
                )

            except Exception as e:

                print(
                    f"Symbol error {symbol}: {e}"
                )

        time.sleep(POLL)


if __name__ == "__main__":
    main()
