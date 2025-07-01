import requests
import os
import sys
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- اطلاعات تلگرام ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID_ENV = os.getenv("TELEGRAM_CHAT_ID")

if TOKEN is None or CHAT_ID_ENV is None:
    print("\u274c خطا: توکن یا آیدی چت تلگرام تنظیم نشده‌اند.")
    sys.exit(1)

CHAT_ID = int(CHAT_ID_ENV)

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, data=data)

# --- دریافت قیمت و دامیننس ---
def get_prices():
    ids = "bitcoin,ethereum,ripple"
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd"
    r = requests.get(url)
    data = r.json()
    return {
        "BTC": data["bitcoin"]["usd"],
        "ETH": data["ethereum"]["usd"],
        "XRP": data["ripple"]["usd"]
    }

def get_dominance():
    url = "https://api.coingecko.com/api/v3/global"
    r = requests.get(url)
    data = r.json()["data"]["market_cap_percentage"]
    return {
        "BTC": data.get("btc", 0),
        "ETH": data.get("eth", 0),
        "USDT": data.get("usdt", 0)
    }

# --- شاخص ترس و طمع ---
def get_fear_and_greed():
    url = "https://api.alternative.me/fng/?limit=2"
    r = requests.get(url)
    data = r.json()["data"]
    today = data[0]["value"]
    yesterday = data[1]["value"]
    return today, yesterday

# --- تحلیل تکنیکال ساده برای BTC ---
def analyze_btc():
    df = yf.download("BTC-USD", period="30d", interval="1h")
    df.dropna(inplace=True)
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['STD20'] = df['Close'].rolling(window=20).std()
    df['UpperBand'] = df['MA20'] + 2 * df['STD20']
    df['LowerBand'] = df['MA20'] - 2 * df['STD20']
    delta = df['Close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))
    df.dropna(inplace=True)
    last = df.iloc[-1]
    signal = "❌ سیگنال خاصی نیست"
    if last['RSI'] < 30 and last['Close'] < last['LowerBand']:
        signal = "🟢 سیگنال خرید بیت‌کوین"
    elif last['RSI'] > 70 and last['Close'] > last['UpperBand']:
        signal = "🔴 سیگنال فروش بیت‌کوین"
    return signal, last['Close'], last['RSI']

# --- ساخت پیام نهایی ---
prices = get_prices()
dom = get_dominance()
fear_today, fear_yesterday = get_fear_and_greed()
signal_btc, last_price, last_rsi = analyze_btc()

msg = f"""
📊 گزارش لحظه‌ای بازار کریپتو:

💰 قیمت‌ها:
- بیت‌کوین: ${prices['BTC']:,}
- اتریوم: ${prices['ETH']:,}
- ریپل: ${prices['XRP']:,}

🔎 دامیننس:
- BTC: {dom['BTC']:.2f}%
- ETH: {dom['ETH']:.2f}%
- USDT: {dom['USDT']:.2f}%

😱 احساسات بازار:
- امروز: {fear_today} /100
- دیروز: {fear_yesterday} /100

📈 تحلیل تکنیکال BTC:
- قیمت فعلی: ${last_price:.2f}
- RSI: {last_rsi:.2f}
- {signal_btc}
"""

send_telegram_message(msg)
