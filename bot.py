import os
import telebot
from flask import Flask
from threading import Thread
import time
from datetime import datetime
import yfinance as yf

TOKEN = os.environ.get("TOKEN")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

PAIRS = ["USD/JPY", "EUR/USD", "GBP/USD"]
users = set()

def get_rsi(closes, period=14):
    if len(closes) < period+1: return 50
    gains = 0
    losses = 0
    for i in range(1, period+1):
        change = closes[-i] - closes[-i-1]
        if change > 0: gains += change
        else: losses -= change
    if losses == 0: return 70
    rs = gains / losses if losses != 0 else 1
    return 100 - (100 / (1 + rs))

def is_bullish_engulfing(opens, closes):
    return closes[-2] < opens[-2] and closes[-1] > opens[-1] and closes[-1] > opens[-2] and opens[-1] < closes[-2]

def is_bearish_engulfing(opens, closes):
    return closes[-2] > opens[-2] and closes[-1] < opens[-1] and closes[-1] < opens[-2] and opens[-1] > closes[-2]

def is_W(lows, lower):
    return abs(lows[-3] - lows[-1]) < 0.001 and lows[-1] <= lower and lows[-3] <= lower

def is_M(highs, upper):
    return abs(highs[-3] - highs[-1]) < 0.001 and highs[-1] >= upper and highs[-3] >= upper

def get_signal(pair):
    try:
        ticker = pair.replace("/", "") + "=X"
        data = yf.download(ticker, period="2d", interval="5m", progress=False)
        if len(data) < 25: return None, 0
        closes = data['Close'].tolist()
        highs = data['High'].tolist()
        lows = data['Low'].tolist()
        opens = data['Open'].tolist()
        upper = max(highs[-20:])
        lower = min(lows[-20:])
        rsi = get_rsi(closes, 14)
        
        # استراتيجيتنا: W + ابتلاع + RSI
        if is_W(lows, lower) and is_bullish_engulfing(opens, closes) and rsi < 35:
            return "BUY", int(rsi)
        if is_M(highs, upper) and is_bearish_engulfing(opens, closes) and rsi > 65:
            return "SELL", int(rsi)
        return None, int(rsi)
    except:
        return None, 0

@bot.message_handler(commands=['start'])
def start(m):
    users.add(m.chat.id)
    bot.send_message(m.chat.id, "✅ البوت الحقيقي اشتغل - W/M + ابتلاع + RSI\n5M شمعة / 15M صفقة")

def run_bot():
    while True:
        for pair in PAIRS:
            signal, rsi = get_signal(pair)
            if signal:
                for uid in users:
                    try:
                        bot.send_message(uid, f"🔥 {pair}\n{signal} - RSI {rsi}\nمدة 15 دقيقة\nW/M + ابتلاع ✅")
                    except: pass
        time.sleep(60)

Thread(target=run_bot, daemon=True).start()

@app.route('/')
def home():
    return "Bot running with REAL W/M strategy"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
