import os
import telebot
from flask import Flask
from threading import Thread

TOKEN = os.environ.get("TOKEN")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Live!"

PAIRS = {
"USD/JPY": "💴 USD/JPY","EUR/USD": "💶 EUR/USD","GBP/USD": "💷 GBP/USD",
"USD/CAD": "💵 USD/CAD","AUD/CAD": "💵 AUD/CAD","AUD/USD": "💵 AUD/USD",
"EUR/JPY": "💶 EUR/JPY","EUR/GBP": "💶 EUR/GBP","AUD/NZD": "💵 AUD/NZD",
"CHF/JPY": "💶 CHF/JPY","GBP/JPY": "💷 GBP/JPY","GBP/AUD": "💷 GBP/AUD"
}
TF = "5M"

@bot.message_handler(commands=['start','signal'])
def signal(m):
    txt="اختر زوج العملات 👇\n\n"
    markup=telebot.types.InlineKeyboardMarkup(row_width=2)
    for k,v in PAIRS.items():
        markup.add(telebot.types.InlineKeyboardButton(v, callback_data=k))
    bot.send_message(m.chat.id, txt, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: True)
def cb(c):
    pair=c.data
    bot.send_message(c.message.chat.id, f"✅ تم اختيار {pair}\n\n⏳ جاري التحليل لـ {TF} ...\n\n📈 الإشارة: BUY ⬆️\n🎯 دخول بعد شمعة واحدة")

def run_bot():
    bot.infinity_polling()

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))

if __name__ == "__main__":
    Thread(target=run_flask).start()
    run_bot()
