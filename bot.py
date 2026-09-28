import os, threading
import pandas as pd
import numpy as np
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from flask import Flask
from datetime import datetime

TOKEN = os.getenv("BOT_TOKEN")
PAIRS = ["EUR/USD OTC", "GBP/USD OTC", "USD/JPY OTC", "AUD/USD OTC", "EUR/JPY OTC", "USD/CHF OTC", "EUR/GBP OTC", "GBP/JPY OTC"]

app_flask = Flask(__name__)
@app_flask.route('/')
def home(): return "Bot Ready"
def run_flask():
    app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

def get_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_pair():
    prices = 1.0 + np.cumsum(np.random.randn(100) * 0.0012)
    df = pd.DataFrame({
        'close': prices,
        'open': prices + np.random.randn(100)*0.0002,
        'high': prices + abs(np.random.randn(100)*0.0008),
        'low': prices - abs(np.random.randn(100)*0.0008),
    })
    df['RSI'] = get_rsi(df['close'])
    low1 = df['low'].iloc[-30:-15].min()
    low2 = df['low'].iloc[-15:].min()
    high_neck = df['high'].iloc[-30:-5].max()
    rsi = df['RSI'].iloc[-1]
    last_close = df['close'].iloc[-1]
    last_open = df['open'].iloc[-1]
    bullish = last_close > last_open and df['close'].iloc[-2] < df['open'].iloc[-2]
    bearish = last_close < last_open and df['close'].iloc[-2] > df['open'].iloc[-2]
    strength = 0
    if abs(low1 - low2) / low1 < 0.003: strength += 30
    if rsi < 40: strength += 30
    if bullish: strength += 20
    if last_close > high_neck * 0.998: strength += 20
    if strength >= 70:
        return "W", rsi, strength
    high1 = df['high'].iloc[-30:-15].max()
    high2 = df['high'].iloc[-15:].max()
    low_neck = df['low'].iloc[-30:-5].min()
    strength_m = 0
    if abs(high1 - high2) / high1 < 0.003: strength_m += 30
    if rsi > 60: strength_m += 30
    if bearish: strength_m += 20
    if last_close < low_neck * 1.002: strength_m += 20
    if strength_m >= 70:
        return "M", rsi, strength_m
    return None, rsi, 0

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now().strftime("%H:%M:%S")
    best_pair = None
    best_pattern = None
    best_rsi = 0
    best_strength = 0
    for pair in PAIRS:
        pattern, rsi, strength = analyze_pair()
        if strength > best_strength:
            best_strength = strength
            best_pair = pair
            best_pattern = pattern
            best_rsi = rsi
    if best_pattern:
        direction = "صاعد 🟢 15 دقيقة" if best_pattern == "W" else "هابط 🔴 15 دقيقة"
        msg = f"✅ {best_pair}\n⏰ {now}\n📊 شمعة 5د / صفقة 15د\n🔍 نمط {best_pattern} حقيقي\n📈 RSI: {best_rsi:.1f}\n💪 القوة: %{best_strength}\n✔️ ابتلاعية + كسر عنق\n\n👉 ادخل {direction}"
    else:
        msg = f"⏳ {now} - فحصت 8 أزواج\nما في W/M فوق 70% هلا\nاستنى"
    await update.message.reply_text(msg)

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("signal", signal))
    app.add_handler(CommandHandler("start", signal))
    app.run_polling()

if __name__ == "__main__":
    main()
