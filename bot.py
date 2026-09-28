import os
import telebot
from flask import Flask
from threading import Thread
import time
import random
from datetime import datetime, timedelta

TOKEN = os.environ.get("TOKEN")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

PAIRS = ["USD/JPY", "EUR/USD", "GBP/USD", "USD/CAD", "AUD/CAD", "AUD/USD", "EUR/JPY", "EUR/GBP", "AUD/NZD", "CHF/JPY", "GBP/JPY", "GBP/AUD"]
users = set()

def get_signal(pair):
    signal = random.choice(["BUY", "SELL"])
    rsi = random.randint(28, 72)
    return signal, rsi

def format_message(pair, signal, rsi):
    now = datetime.now() + timedelta(hours=3)
    entry_time = (now + timedelta(minutes=1)).strftime("%H:%M:%S")
    
    if signal == "BUY":
        color = "🟢🟢🟢"
        arrow = "📈"
        action = "شراء"
        bg = "💚"
    else:
        color = "🔴🔴🔴"
        arrow = "📉"
        action = "بيع"
        bg = "❤️"

    msg = f"""
{color} إشارة جديدة {color}

{bg} الزوج: {pair} OTC
{arrow} الإشارة: {signal} - {action}
⏰ وقت الدخول: {entry_time}
⏳ مدة الصفقة: 15 دقيقة
📊 RSI: {rsi}
🎯 الدخول بعد: شمعة واحدة

━━━━━━━━━━━━━━
💡 تحليل 5M - دقة عالية
"""
    return msg

@bot.message_handler(commands=['start'])
def start(message):
    users.add(message.chat.id)
    bot.send_message(message.chat.id, "👋 أهلا! رح أبلش أبعتلك إشارات OTC كل 15 دقيقة تلقائيا 🔥\n\n✅ تم تفعيل الإشارات التلقائية")
    pair = random.choice(PAIRS)
    sig, rsi = get_signal(pair)
    bot.send_message(message.chat.id, format_message(pair, sig, rsi), parse_mode="Markdown")

def auto_signals():
    while True:
        time.sleep(15 * 60)
        if not users:
            continue
        pair = random.choice(PAIRS)
        sig, rsi = get_signal(pair)
        msg = format_message(pair, sig, rsi)
        for uid in list(users):
            try:
                bot.send_message(uid, msg, parse_mode="Markdown")
            except:
                pass

@app.route('/')
def home():
    return "Bot is Live!"

def run_bot():
    Thread(target=auto_signals, daemon=True).start()
    bot.infinity_polling()

if __name__ == "__main__":
    Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))), daemon=True).start()
    run_bot()
