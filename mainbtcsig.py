import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
import sys

# --- تنظیمات تلگرام ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID_ENV = os.getenv("TELEGRAM_CHAT_ID")

if TOKEN is None or CHAT_ID_ENV is None:
    print("❌ خطا: توکن یا آیدی چت تنظیم نشده‌اند!")
    sys.exit(1)

CHAT_ID = int(CHAT_ID_ENV)

def send_telegram_message(message):
    url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
    data = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
    response = requests.post(url, data=data)
    if not response.ok:
        print("خطا در ارسال پیام به تلگرام:", response.text)

# --- تابع تحلیل بیت‌کوین با RSI و Bollinger Bands ---
def analyze_btc():
    df = yf.download("BTC-USD", period="30d", interval="1h", auto_adjust=True)
    df = df.dropna(subset=['Close'])
    
    # محاسبه اندیکاتورها
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['STD20'] = df['Close'].rolling(window=20).std()
    df['UpperBand'] = df['MA20'] + 2 * df['STD20']
    df['LowerBand'] = df['MA20'] - 2 * df['STD20']

    delta = df['Close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    df.dropna(inplace=True)

    last = df.iloc[-1]

    # دقت کن از .item() استفاده کنیم تا مقدار اسکالر بدست بیاد و شرط درست کار کنه
    rsi_val = last['RSI'].item()
    close_val = last['Close'].item()
    lower_band_val = last['LowerBand'].item()
    upper_band_val = last['UpperBand'].item()

    signal = "هیچ سیگنالی"
    if (rsi_val < 30) and (close_val < lower_band_val):
        signal = "سیگنال خرید"
    elif (rsi_val > 70) and (close_val > upper_band_val):
        signal = "سیگنال فروش"

    return signal, close_val, rsi_val

# --- دریافت قیمت لحظه‌ای از CoinGecko ---
def get_prices_coingecko():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,ripple&vs_currencies=usd"
    response = requests.get(url)
    data = response.json()
    btc_price = data['bitcoin']['usd']
    eth_price = data['ethereum']['usd']
    xrp_price = data['ripple']['usd']
    return btc_price, eth_price, xrp_price

# --- دریافت دامیننس از CoinGecko ---
def get_dominance_coingecko():
    url = "https://api.coingecko.com/api/v3/global"
    response = requests.get(url)
    data = response.json()
    dominance = data['data']['market_cap_percentage']
    btc_dom = dominance.get('btc', None)
    eth_dom = dominance.get('eth', None)
    usdt_dom = dominance.get('usdt', None)
    return btc_dom, eth_dom, usdt_dom

# --- دریافت شاخص ترس و طمع ---
def get_fear_and_greed_index():
    url = "https://api.alternative.me/fng/"
    response = requests.get(url)
    data = response.json()
    value = data['data'][0]['value']
    value_classification = data['data'][0]['value_classification']
    return value, value_classification

if __name__ == "__main__":
    signal_btc, last_price, last_rsi = analyze_btc()
    btc_price, eth_price, xrp_price = get_prices_coingecko()
    btc_dom, eth_dom, usdt_dom = get_dominance_coingecko()
    fear_value, fear_status = get_fear_and_greed_index()

    message = f"""
📊 <b>تحلیل لحظه‌ای بیت‌کوین (BTC)</b>:
سیگنال: <b>{signal_btc}</b>
قیمت لحظه‌ای: {last_price:.2f} USD
RSI: {last_rsi:.2f}

💰 <b>قیمت‌های لحظه‌ای</b>:
BTC: {btc_price} USD
ETH: {eth_price} USD
XRP: {xrp_price} USD

📈 <b>دامیننس بازار</b>:
BTC Dominance: {btc_dom:.2f}%
ETH Dominance: {eth_dom:.2f}%
USDT Dominance: {usdt_dom:.2f}%

😨 <b>شاخص ترس و طمع</b>:
مقدار: {fear_value}
وضعیت: {fear_status}
    """

    print(message)
    send_telegram_message(message)
