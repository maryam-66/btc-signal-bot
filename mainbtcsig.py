import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
import sys
from datetime import datetime

# --- اطلاعات تلگرام ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")  # کلید API اخبار

if not TOKEN or not CHAT_ID:
    print("❌ توکن یا آیدی چت تنظیم نشده‌اند!")
    sys.exit(1)

CHAT_ID = int(CHAT_ID)

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    res = requests.post(url, data=data)
    if not res.ok:
        print("❌ ارسال پیام ناموفق:", res.text)

# --- دریافت قیمت لحظه‌ای و دامیننس ---
def get_live_prices_and_dominance():
    url = "https://api.coingecko.com/api/v3/global"
    global_res = requests.get(url)
    price_url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,ripple&vs_currencies=usd"
    price_res = requests.get(price_url)

    if global_res.ok and price_res.ok:
        market_data = global_res.json()["data"]
        prices = price_res.json()
        btc = prices["bitcoin"]["usd"]
        eth = prices["ethereum"]["usd"]
        xrp = prices["ripple"]["usd"]
        btc_dom = market_data["market_cap_percentage"]["btc"]
        eth_dom = market_data["market_cap_percentage"]["eth"]
        market_cap = market_data["total_market_cap"]["usd"]

        info = (f"💰 قیمت لحظه‌ای:\n"
                f"BTC: ${btc:,}\nETH: ${eth:,}\nXRP: ${xrp:.4f}\n\n"
                f"🌐 مارکت کپ کل: {market_cap/1e9:.2f} میلیارد دلار\n"
                f"🔶 دامیننس BTC: {btc_dom:.2f}%\n"
                f"🔷 دامیننس ETH: {eth_dom:.2f}%")
        return info
    return "⚠️ خطا در دریافت اطلاعات مارکت و قیمت‌ها"

# --- دریافت شاخص ترس و طمع ---
def get_fear_greed_index():
    url = 'https://api.alternative.me/fng/'
    res = requests.get(url)
    if res.ok:
        data = res.json()['data'][0]
        return f"📊 شاخص ترس و طمع: {data['value']} ({data['value_classification']})"
    return "⚠️ خطا در دریافت شاخص ترس و طمع"

# --- دریافت اخبار اقتصادی مهم ---
def get_latest_news():
    if not NEWSAPI_KEY:
        return "⚠️ کلید API اخبار تنظیم نشده است."
    
    keywords = "bitcoin OR ethereum OR ripple OR crypto OR 'federal reserve' OR inflation OR interest rate"
    url = (
        f"https://newsapi.org/v2/everything?"
        f"q={keywords}&language=en&sortBy=publishedAt&pageSize=3&apiKey={NEWSAPI_KEY}"
    )
    res = requests.get(url)
    if res.ok:
        articles = res.json().get("articles", [])
        if not articles:
            return "⚠️ خبری یافت نشد."
        return "\n".join([f"- {a['title']} ({a['source']['name']})" for a in articles])
    return "⚠️ خطا در دریافت اخبار"

# --- تحلیل تکنیکال و سیگنال‌دهی ---
symbols = {
    'BTC-USD': 'بیت‌کوین',
    'ETH-USD': 'اتریوم',
    'XRP-USD': 'ریپل'
}

today = datetime.utcnow().strftime('%Y-%m-%d')
final_messages = []

for symbol, name in symbols.items():
    df = yf.download(symbol, period='30d', interval='1h')  # تحلیل کوتاه‌مدت
    if df.empty or 'Close' not in df:
        continue

    df = df[['Close']].dropna()

    # اندیکاتورها
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

    last = df.iloc[-1]
    date_str = last.name.strftime('%Y-%m-%d %H:%M')
    signal = ""
    if last['RSI'] < 30 and last['Close'] < last['LowerBand']:
        signal = f"📈 سیگنال خرید {name} ({date_str})\nقیمت: ${last['Close']:.2f}\n📉 RSI: {last['RSI']:.2f}"
    elif last['RSI'] > 70 and last['Close'] > last['UpperBand']:
        signal = f"📉 سیگنال فروش {name} ({date_str})\nقیمت: ${last['Close']:.2f}\n📈 RSI: {last['RSI']:.2f}"
    else:
        signal = f"ℹ️ {name} ({date_str}) - هیچ سیگنالی صادر نشد."

    final_messages.append(signal)

# --- داده‌های تکمیلی ---
market_info = get_live_prices_and_dominance()
fear_greed = get_fear_greed_index()
news = get_latest_news()

# --- ارسال گزارش ---
report = "\n\n".join(final_messages)
final_text = f"{report}\n\n{market_info}\n\n{fear_greed}\n\n📰 اخبار اقتصادی:\n{news}"
send_telegram_message(final_text)
