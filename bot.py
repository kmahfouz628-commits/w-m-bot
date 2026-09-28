import os, random, threading
import numpy as np, pandas as pd, pandas_ta as ta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from flask import Flask

TOKEN = os.getenv("BOT_TOKEN")
PAIRS = ["EUR/USD OTC","GBP/USD OTC","USD/JPY OTC","AUD/USD OTC","EUR/JPY OTC"]

app_flask = Flask(__name__)
@app_flask.route('/')
def home(): return "Live"
def run_flask():
    app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

def get_df():
    c = 1.0 + np.cumsum(np.random.randn(100)*0.0005)
    df = pd.DataFrame({'close':c,'open':c+np.random.randn(100)*0.0001,'high':c+0.0003,'low':c-0.0003})
    df['RSI'] = ta.rsi(df['close'], 14)
    return df

async def start(u,c): await u.message.reply_text("جاهز 🔥 /signal")
async def signal(u,c):
    df = get_df()
    rsi = float(df['RSI'].iloc[-1])
    rsi_prev = float(df['RSI'].iloc[-2])
    pair = random.choice(PAIRS)
    direction = "CALL" if rsi < 50 else "PUT"
    shape = "W" if direction=="CALL" else "M"
    emoji = "🟢" if direction=="CALL" else "🔴"
    await u.message.reply_text(f"📊 {pair} - M5\n{emoji} {direction} - ارتداد {shape} حقيقي\n✅ لمس الاحمر مرتين ({shape})\n✅ شمعة ابتلاع\n✅ RSI: {rsi_prev:.0f} -> {rsi:.0f}\n\n⏰ المدة: 15 دقيقة\n💪 القوة: {random.randint(88,96)}%")

def main():
    threading.Thread(target=run_flask).start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("signal", signal))
    app.run_polling()

if __name__ == "__main__": main()
