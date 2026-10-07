import os
import time
import traceback
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

import store
from strategy import signal
from po_source import PocketOptionFeed


load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT = os.getenv("TELEGRAM_CHAT_ID", "").strip()
SSID = os.getenv("PO_SSID", "").strip()

MAX_SIGNALS_PER_DAY = 20
POLL_SECONDS = 5
REQUEST_DELAY = 1.0
MIN_OTC_PAYOUT = 80.0
EXPIRY_MINUTES = 3

LOCK_FILE = "/tmp/otc_signal_bot.lock"

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
    ("ZARUSD_otc", "🇿🇦/🇿🇦 ZAR/USD OTC"),
]

seen_candles = {}


def acquire_lock():
    try:
        if os.path.exists(LOCK_FILE):
            try:
                with open(LOCK_FILE, "r", encoding="utf-8") as f:
                    old_pid = f.read().strip()
            except Exception:
                old_pid = "غير معروف"

            print("⚠️ نسخة أخرى من البوت تعمل بالفعل.")
            print(f"PID الموجود: {old_pid}")
            return False

        with open(LOCK_FILE, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))

        print("تم تفعيل حماية التشغيل الفردي.")
        return True

    except Exception as e:
        print("Lock error:", e)
        return False


def release_lock():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception as e:
        print("Lock release error:", e)


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


def get_candles(feed, symbol):
    try:
        df = feed.candles_m1(symbol, 100)

        if df is None or len(df) < 60:
            return None

        return df

    except Exception as e:
        print(f"Candles error {symbol}: {e}")
        return None


def candle_timestamp(value):
    try:
        if hasattr(value, "timestamp"):
            return float(value.timestamp())

        return float(value)

    except Exception:
        return None


def get_display_name(symbol):
    for pair_symbol, display_name in OTC_PAIRS:
        if pair_symbol == symbol:
            return display_name

    return symbol.replace("_otc", " OTC")


def check_pending(feed):
    try:
        conn = store.db()

        rows = conn.execute(
            """
            SELECT id,
                   symbol,
                   signal_time,
                   direction,
                   entry,
                   expiry
            FROM signals
            WHERE result='PENDING'
            """
        ).fetchall()

        conn.close()

        now = datetime.now(timezone.utc).timestamp()

        for row in rows:
            (
                row_id,
                symbol,
                signal_time,
                direction,
                entry,
                expiry
            ) = row

            if now < float(expiry):
                continue

            try:
                df = feed.candles_m1(symbol, 100)
            except Exception as e:
                print(f"Result candles error {symbol}: {e}")
                continue

            if df is None or len(df) < 3:
                continue

            target_time = float(expiry) - 60

            best_candle = None
            best_difference = None

            for _, candle in df.iterrows():
                ts = candle_timestamp(candle["time"])

                if ts is None:
                    continue

                difference = abs(ts - target_time)

                if difference <= 5:
                    if (
                        best_difference is None
                        or difference < best_difference
                    ):
                        best_difference = difference
                        best_candle = candle

            if best_candle is None:
                candidates = []

                for _, candle in df.iterrows():
                    ts = candle_timestamp(candle["time"])

                    if ts is None:
                        continue

                    if ts <= target_time:
                        candidates.append((ts, candle))

                if candidates:
                    candidates.sort(key=lambda x: x[0])
                    best_candle = candidates[-1][1]

            if best_candle is None:
                print(f"Waiting for expiry candle {symbol}")
                continue

            try:
                result_close = float(best_candle["close"])
                entry_price = float(entry)
            except Exception as e:
                print(f"Price conversion error {symbol}: {e}")
                continue

            if result_close > entry_price:
                result = "WIN" if direction == "CALL" else "LOSS"

            elif result_close < entry_price:
                result = "WIN" if direction == "PUT" else "LOSS"

            else:
                result = "DRAW"

            try:
                store.finish(signal_time, result)
            except Exception as e:
                print(f"Database result error {symbol}: {e}")
                continue

            w, l, d, rate = store.stats()

            display_name = get_display_name(symbol)

            if result == "WIN":
                result_title = "✅ نجحت — WIN"
                result_text = "الإشارة حققت النتيجة الصحيحة بعد انتهاء 3 دقائق."

            elif result == "LOSS":
                result_title = "❌ خسرت — LOSS"
                result_text = "الإشارة لم تحقق النتيجة المتوقعة بعد انتهاء 3 دقائق."

            else:
                result_title = "🟡 تعادل — DRAW"
                result_text = "سعر الدخول وسعر النهاية كانا متساويين."

            direction_ar = "🟢 شراء" if direction == "CALL" else "🔴 بيع"

            result_message = (
                f"{result_title}\n"
                f"━━━━━━━━━━━━━━\n"
                f"📊 الزوج: {display_name}\n"
                f"📌 الاتجاه: {direction_ar}\n"
                f"💵 سعر الدخول: {entry_price}\n"
                f"🏁 سعر انتهاء الصفقة: {result_close}\n"
                f"⏱️ مدة الإشارة: 3 دقائق\n"
                f"━━━━━━━━━━━━━━\n"
                f"📝 النتيجة:\n"
                f"{result_text}\n"
                f"━━━━━━━━━━━━━━\n"
                f"📊 الإحصائيات حتى الآن\n"
                f"🟢 ناجحة: {w}\n"
                f"🔴 خاسرة: {l}\n"
                f"🟡 تعادل: {d}\n"
                f"📈 نسبة النجاح: {rate:.1f}%\n"
                f"━━━━━━━━━━━━━━\n"
                f"🎯 تجريبي فقط\n"
                f"🚫 لا توجد صفقات تلقائية"
            )

            send_telegram(result_message)

            print(
                f"RESULT {symbol} {direction}: "
                f"{result} | entry={entry_price} | close={result_close}"
            )

    except Exception as e:
        print("Result check error:", e)
        traceback.print_exc()


def success_text():
    w, l, d, rate = store.stats()

    if w + l == 0:
        return "📊 نسبة النجاح: لا توجد نتائج مكتملة بعد"

    return (
        f"📊 نسبة النجاح: {rate:.1f}%\n"
        f"🟢 ناجحة: {w}\n"
        f"🔴 خاسرة: {l}\n"
        f"🟡 تعادل: {d}"
    )


def build_message(display_name, s, entry, payout):
    if s["direction"] == "CALL":
        title = "🟢 إشارة شراء — CALL"
        level = "📍 الحد السفلي لدونشيان"
        direction_text = "شراء"
    else:
        title = "🔴 إشارة بيع — PUT"
        level = "📍 الحد العلوي لدونشيان"
        direction_text = "بيع"

    rsi = s.get("rsi", "غير متوفر")
    stoch_k = s.get("stoch_k", "غير متوفر")
    stoch_d = s.get("stoch_d", "غير متوفر")

    reason = s.get(
        "reason",
        "انعكاس مؤكد حسب شروط الاستراتيجية"
    )

    return (
        f"{title}\n"
        f"━━━━━━━━━━━━━━\n"
        f"📊 الزوج: {display_name}\n"
        f"📌 الاتجاه: {direction_text}\n"
        f"{level}\n"
        f"💰 نسبة العائد: {payout:.0f}%\n"
        f"⏱️ الإطار: M1\n"
        f"⌛ مدة الإشارة: 3 دقائق\n"
        f"💵 سعر الدخول: {entry}\n"
        f"━━━━━━━━━━━━━━\n"
        f"🧠 سبب الإشارة:\n"
        f"{reason}\n"
        f"━━━━━━━━━━━━━━\n"
        f"📈 RSI 14: {rsi}\n"
        f"📊 Stochastic K: {stoch_k}\n"
        f"📊 Stochastic D: {stoch_d}\n"
        f"━━━━━━━━━━━━━━\n"
        f"{success_text()}\n"
        f"━━━━━━━━━━━━━━\n"
        f"🎯 تجريبي فقط\n"
        f"🚫 لا توجد صفقات تلقائية"
    )


def process_pair(feed, symbol, display_name):
    payout = get_current_payout(feed, symbol)

    if payout is None:
        print(f"{display_name}: العائد غير متوفر")
        return False

    print(
        f"{display_name}: "
        f"نسبة الدفع = {payout:.0f}%"
    )

    if payout < MIN_OTC_PAYOUT:
        print(
            f"{display_name}: "
            f"في انتظار الدفع ≥ {MIN_OTC_PAYOUT:.0f}%"
        )
        return False

    df = get_candles(feed, symbol)

    if df is None:
        return False

    try:
        closed = df.iloc[:-1].copy()

        if len(closed) < 60:
            return False

        candle = closed.iloc[-1]

        candle_id = str(candle["time"])

    except Exception as e:
        print(
            f"Candle preparation error {symbol}: {e}"
        )
        return False

    if seen_candles.get(symbol) == candle_id:
        return False

    try:
        result = signal(closed)
    except Exception as e:
        print(f"Strategy error {symbol}: {e}")
        traceback.print_exc()
        return False

    if not result:
        return False

    direction = result.get("direction")

    if direction not in ("CALL", "PUT"):
        return False

    try:
        entry = float(candle["close"])
    except Exception:
        return False

    try:
        candle_time = candle["time"]
        candle_ts = candle_timestamp(candle_time)

        if candle_ts is None:
            return False

        expiry = candle_ts + EXPIRY_MINUTES * 60

    except Exception as e:
        print(f"Expiry error {symbol}: {e}")
        return False

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
        print(f"Database save error {symbol}: {e}")
        traceback.print_exc()
        return False

    message = build_message(
        display_name,
        signal_data,
        entry,
        payout
    )

    if not send_telegram(message):
        print(
            f"{display_name}: "
            "فشل إرسال رسالة Telegram"
        )
        return False

    seen_candles[symbol] = candle_id

    print(
        f"*** SIGNAL {direction} "
        f"{display_name} "
        f"payout={payout:.0f}% ***"
    )

    return True


def send_start_message():
    message = (
        "🤖 تم تشغيل بوت إشارات OTC\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📊 عدد الأزواج: 47 زوج OTC\n"
        "⏱️ الإطار الزمني: M1\n"
        "⌛ مدة الإشارة: 3 دقائق\n"
        "💰 أقل عائد: 80%\n"
        "🎯 الحد الأقصى: 20 إشارة يوميًا\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🧠 استراتيجية الانعكاس\n"
        "📈 Donchian 20\n"
        "📉 RSI 14\n"
        "🕯️ شمعة رفض\n"
        "📊 Stochastic 5,3,3\n"
        "📉 EMA 50\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📌 البوت يرسل إشارات فقط\n"
        "🎯 تجريبي فقط\n"
        "🚫 لا توجد صفقات تلقائية"
    )

    send_telegram(message)


def main():
    print("======================================")
    print("بدء تشغيل بوت إشارات OTC")
    print("تجريبي فقط - لا توجد صفقات تلقائية")
    print("======================================")

    if not SSID:
        print("ERROR: PO_SSID is missing")
        return

    if not TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is missing")
        return

    if not CHAT:
        print("ERROR: TELEGRAM_CHAT_ID is missing")
        return

    if not acquire_lock():
        print(
            "تم إيقاف هذه النسخة "
            "لأن هناك نسخة أخرى تعمل."
        )
        return

    try:
        store.db().close()

        print(
            f"تم تحميل {len(OTC_PAIRS)} زوج OTC"
        )

        feed = None

        while True:
            try:
                if not feed_connected(feed):

                    print(
                        "Pocket Option غير متصل."
                    )

                    if feed is not None:
                        try:
                            feed.close()
                        except Exception:
                            pass

                    feed = connect_feed()

                    if feed is None:
                        print(
                            "فشل الاتصال. "
                            "إعادة المحاولة بعد 15 ثانية..."
                        )

                        time.sleep(15)
                        continue

                    print("تم استعادة الاتصال.")
                    send_start_message()

                check_pending(feed)

                current_count = store.today_count()

                print(
                    f"إشارات اليوم: "
                    f"{current_count}/"
                    f"{MAX_SIGNALS_PER_DAY}"
                )

                if current_count >= MAX_SIGNALS_PER_DAY:

                    print(
                        "تم الوصول إلى الحد "
                        "اليومي للإشارات."
                    )

                    time.sleep(60)
                    continue

                for symbol, display_name in OTC_PAIRS:

                    if (
                        store.today_count()
                        >= MAX_SIGNALS_PER_DAY
                    ):
                        break

                    if not feed_connected(feed):
                        print(
                            "انقطع الاتصال أثناء الفحص."
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
                            f"خطأ غير متوقع "
                            f"{symbol}: {e}"
                        )
                        traceback.print_exc()

                    time.sleep(REQUEST_DELAY)

                print(
                    f"اكتمل الفحص. "
                    f"الانتظار {POLL_SECONDS} ثوانٍ..."
                )

                time.sleep(POLL_SECONDS)

            except KeyboardInterrupt:

                print(
                    "تم إيقاف البوت يدويًا."
                )

                break

            except Exception as e:

                print(
                    "خطأ في الحلقة الرئيسية:",
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
                    "إعادة الاتصال بعد 15 ثانية..."
                )

                time.sleep(15)

    finally:

        release_lock()

        print(
            "تم تحرير قفل التشغيل."
        )


if __name__ == "__main__":
    main()
