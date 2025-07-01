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

if not TOKEN or not CHAT_ID_ENV:
    print("❌ خطا: توکن یا آیدی چت تلگرام تنظیم نشده‌اند.")
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
    url = (f'https://newsapi.org/v2/everything?'
           'q=crypto OR bitcoin OR ethereum OR ripple OR "federal reserve"&'
           'language=en&sortBy=publishedAt&pageSize=3&apiKey={api_key}').format(api_key=NEWSAPI_KEY)
    response = requests.get(url)
    if response.status_code == 200:
        articles = response.json().get('articles', [])
        if not articles:
            return "⚠️ خبری یافت نشد."
        news_texts = [f"- {a['title']} ({a['source']['name']})" for a in articles]
        return "\n".join(news_texts)
    else:
        return "⚠️ خطا در دریافت اخبار"

# --- شاخص ترس و طمع ---
def get_fear_greed_index():
    url = 'https://api.alternative.me/fng/'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        value = data['data'][0]['value']
        classification = data['data'][0]['value_classification']
        return f"📊 شاخص ترس و طمع: {value} ({classification})"
    else:
        return "⚠️ خطا در دریافت شاخص ترس و طمع"

# --- روند کلی بازار + قیمت لحظه‌ای ---
def get_market_overview_and_prices():
    try:
        res = requests.get("https://api.coingecko.com/api/v3/global")
        prices = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,ripple&vs_currencies=usd")
        if res.status_code == 200 and prices.status_code == 200:
            global_data = res.json()['data']
            price_data = prices.json()
            market_cap = global_data['total_market_cap']['usd'] / 1e9
            btc_dominance = global_data['market_cap_percentage']['btc']
            eth_dominance = global_data['market_cap_percentage']['eth']
            btc_price = price_data['bitcoin']['usd']
            eth_price = price_data['ethereum']['usd']
            xrp_price = price_data['ripple']['usd']
            return (f"💰 قیمت لحظه‌ای:\n"
                    f"- بیت‌کوین: ${btc_price:,.2f}\n"
                    f"- اتریوم: ${eth_price:,.2f}\n"
                    f"- ریپل: ${xrp_price:,.2f}\n\n"
                    f"🌐 مارکت کپ کل: {market_cap:.2f} میلیارد دلار\n"
                    f"🔶 دامیننس BTC: {btc_dominance:.2f}%\n"
                    f"🔷 دامیننس ETH: {eth_dominance:.2f}%")
        else:
            return "⚠️ خطا در دریافت قیمت یا وضعیت بازار"
    except Exception as e:
        return f"⚠️ خطا: {str(e)}"

# --- تحلیل تکنیکال و سیگنال‌دهی ---
symbols = {
    'BTC-USD': 'بیت‌کوین',
    'ETH-USD': 'اتریوم',
    'XRP-USD': 'ریپل'
}

final_messages = []

for symbol, name in symbols.items():
    df = yf.download(symbol, period='30d', interval='1h')  # تحلیل کوتاه‌مدت

    if df.empty or 'Close' not in df.columns:
        continue

    df = df[['Close']].copy()
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

    if df.empty or 'RSI' not in df.columns:
        continue

    # سیگنال‌ها
    df['Buy_Signal'] = (df['RSI'] < 30) & (df['Close'] < df['LowerBand'])
    df['Sell_Signal'] = (df['RSI'] > 70) & (df['Close'] > df['UpperBand'])

    last = df.iloc[-1]

    close = float(last['Close'])
    rsi = float(last['RSI'])
    lower = float(last['LowerBand'])
    upper = float(last['UpperBand'])

    date_str = last.name.strftime('%Y-%m-%d %H:%M')

    signal = ""
    if rsi < 30 and close < lower:
        signal = f"📈 سیگنال خرید {name} ({date_str})\nقیمت: ${close:.2f}\n📉 RSI: {rsi:.2f}"
    elif rsi > 70 and close > upper:
        signal = f"📉 سیگنال فروش {name} ({date_str})\nقیمت: ${close:.2f}\n📈 RSI: {rsi:.2f}"
    else:
        signal = f"ℹ️ {name} ({date_str}) - هیچ سیگنالی صادر نشد."

    final_messages.append(signal)

# --- بخش‌های نهایی ---
news = get_latest_news()
fear_greed = get_fear_greed_index()
market_data = get_market_overview_and_prices()

final_report = '\n\n'.join(final_messages)
extra_info = f"\n\n📰 اخبار مهم:\n{news}\n\n{fear_greed}\n\n{market_data}"

# ارسال به تلگرام
send_telegram_message(final_report + extra_info)
