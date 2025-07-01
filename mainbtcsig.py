import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
import sys
from datetime import datetime

# --- اطلاعات تلگرام ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID_ENV = os.getenv("TELEGRAM_CHAT_ID")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")

if TOKEN is None or CHAT_ID_ENV is None:
    print("❌ توکن یا آیدی چت تنظیم نشده‌اند!")
    sys.exit(1)

CHAT_ID = int(CHAT_ID_ENV)

def send_telegram_message(message):
    url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
    data = {'chat_id': CHAT_ID, 'text': message}
    response = requests.post(url, data=data)
    if not response.ok:
        print("⚠️ ارسال پیام تلگرام ناموفق بود:", response.text)

# --- دریافت اخبار مهم ---
def get_latest_news():
    if not NEWSAPI_KEY:
        return "⚠️ کلید API اخبار تنظیم نشده است."
    url = (
        'https://newsapi.org/v2/everything?'
        'q=bitcoin OR ethereum OR ripple OR "federal reserve" OR inflation OR interest rates&'
        'language=en&sortBy=publishedAt&pageSize=3&apiKey=' + NEWSAPI_KEY
    )
    response = requests.get(url)
    if response.status_code == 200:
        articles = response.json().get('articles', [])
        if not articles:
            return "⚠️ خبری یافت نشد."
        news_texts = [f"- {a['title']} ({a['source']['name']})" for a in articles]
        return "\n".join(news_texts)
    return "⚠️ خطا در دریافت اخبار"

# --- شاخص ترس و طمع ---
def get_fear_greed_index():
    url = 'https://api.alternative.me/fng/'
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        value = data['data'][0]['value']
        classification = data['data'][0]['value_classification']
        return f"📊 شاخص ترس و طمع: {value} ({classification})"
    except:
        return "⚠️ خطا در دریافت شاخص ترس و طمع"

# --- اطلاعات لحظه‌ای بازار ---
def get_market_data():
    url = "https://api.coingecko.com/api/v3/global"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()['data']
        market_cap = data['total_market_cap']['usd'] / 1e9
        btc_dominance = data['market_cap_percentage']['btc']
        eth_dominance = data['market_cap_percentage']['eth']
        return f"🌐 مارکت کپ کل: {market_cap:.2f} میلیارد دلار\n🔶 دامیننس BTC: {btc_dominance:.2f}%\n🔷 دامیننس ETH: {eth_dominance:.2f}%"
    except:
        return "⚠️ خطا در دریافت اطلاعات مارکت"

# --- قیمت لحظه‌ای رمزارزها ---
def get_live_prices(symbols):
    prices = {}
    for symbol, name in symbols.items():
        url = f'https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower().split("-")[0]}&vs_currencies=usd'
        try:
            response = requests.get(url, timeout=5)
            data = response.json()
            price = data[symbol.lower().split("-")[0]]['usd']
            prices[name] = f"{price:.2f} USD"
        except:
            prices[name] = "❌ دریافت نشد"
    return prices

# --- تحلیل تکنیکال و سیگنال ---
symbols = {
    'BTC-USD': 'بیت‌کوین',
    'ETH-USD': 'اتریوم',
    'XRP-USD': 'ریپل'
}

final_messages = []

for symbol, name in symbols.items():
    df = yf.download(symbol, period='30d', interval='1h', auto_adjust=False)

    if 'Close' not in df.columns:
        print(f"⚠️ داده‌های {name} ناقص است.")
        continue

    df['7_MA'] = df['Close'].rolling(7).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['STD20'] = df['Close'].rolling(20).std()
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

    df['Buy_Signal'] = (df['RSI'] < 30) & (df['Close'] < df['LowerBand'])
    df['Sell_Signal'] = (df['RSI'] > 70) & (df['Close'] > df['UpperBand'])

    last_row = df.iloc[-1]
    date_str = last_row.name.strftime('%Y-%m-%d %H:%M')

    if last_row['Buy_Signal']:
        signal = f"📈 سیگنال خرید {name} ({date_str})\nقیمت: {last_row['Close']:.2f} USD\n📊 RSI: {last_row['RSI']:.2f}"
    elif last_row['Sell_Signal']:
        signal = f"📉 سیگنال فروش {name} ({date_str})\nقیمت: {last_row['Close']:.2f} USD\n📊 RSI: {last_row['RSI']:.2f}"
    else:
        signal = f"ℹ️ {name} - ({date_str}) هیچ سیگنالی صادر نشد."

    final_messages.append(signal)

# --- اطلاعات جانبی ---
live_prices = get_live_prices(symbols)
prices_text = "\n".join([f"💰 {k}: {v}" for k, v in live_prices.items()])

news = get_latest_news()
fear_greed = get_fear_greed_index()
market_data = get_market_data()

# --- ارسال نهایی ---
message = "\n\n".join(final_messages)
extra_info = f"\n\n{prices_text}\n\n📰 اخبار مهم:\n{news}\n\n{fear_greed}\n\n{market_data}"

send_telegram_message(message + extra_info)
