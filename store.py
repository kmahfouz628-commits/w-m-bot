import sqlite3
from datetime import datetime, timezone
DB='signals.db'

def db():
    c=sqlite3.connect(DB); c.execute('''CREATE TABLE IF NOT EXISTS signals(id INTEGER PRIMARY KEY, symbol TEXT, signal_time TEXT, direction TEXT, entry REAL, expiry REAL, result TEXT, rsi REAL, stoch_k REAL, stoch_d REAL, reason TEXT)'''); c.commit(); return c

def add(s):
    c=db(); c.execute('INSERT INTO signals(symbol,signal_time,direction,entry,expiry,result,rsi,stoch_k,stoch_d,reason) VALUES(?,?,?,?,?,?,?,?,?,?)',(s['symbol'],s['signal_time'],s['direction'],s['entry'],s['expiry'],'PENDING',s['rsi'],s['stoch_k'],s['stoch_d'],s['reason'])); c.commit(); c.close()

def finish(signal_time,result):
    c=db(); c.execute('UPDATE signals SET result=? WHERE signal_time=? AND result="PENDING"',(result,signal_time)); c.commit(); c.close()

def stats():
    c=db(); rows=c.execute('SELECT result,COUNT(*) FROM signals WHERE result IN ("WIN","LOSS","DRAW") GROUP BY result').fetchall(); c.close(); d=dict(rows); w=d.get('WIN',0); l=d.get('LOSS',0); dr=d.get('DRAW',0); rate=(w/(w+l)*100) if w+l else 0; return w,l,dr,rate

def today_count():
    c=db(); n=c.execute('SELECT COUNT(*) FROM signals WHERE date(signal_time)=date("now")').fetchone()[0]; c.close(); return n
  
