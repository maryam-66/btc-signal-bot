import yfinance as yf
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
import datetime
import os
import sys

# --- تنظیمات تلگرام ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID_ENV = os.getenv("TELEGRAM_CHAT_ID")

if not TOKEN or not CHAT_ID_ENV:
    print("❌ خطا: توکن یا آیدی چت تلگرام تنظیم نشده‌اند.")
    sys.exit(1)

CHAT_ID = int(CHAT_ID_ENV)

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    resp = requests.post(url, data=data)
    if not resp.ok:
        print(f"❌ خطا در ارسال پیام تلگرام: {resp.text}")

# --- دانلود دیتا با YFinance و پردازش ---
def download_and_process(symbol):
    df = yf.download(symbol, period="30d", interval="1h", auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ['_'.join(col).strip() for col in df.columns]

    close_cols = [col for col in df.columns if col.startswith('Close')]
    if not close_cols:
        raise KeyError(f"ستون Close برای {symbol} پیدا نشد!")
    price_col = close_cols[0]

    df = df.dropna(subset=[price_col])

    # اندیکاتورها
    df['MA20'] = df[price_col].rolling(20).mean()
    df['STD20'] = df[price_col].rolling(20).std()
    df['UpperBand'] = df['MA20'] + 2 * df['STD20']
    df['LowerBand'] = df['MA20'] - 2 * df['STD20']

    delta = df[price_col].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))

    df.dropna(inplace=True)
    return df, price_col

def analyze_signal(df, price_col, name):
    last = df.iloc[-1]
    rsi = last['RSI']
    close = last[price_col]
    lower = last['LowerBand']
    upper = last['UpperBand']

    signal = None
    if (rsi < 30) and (close < lower):
        signal = f"📈 سیگنال خرید {name}"
    elif (rsi > 70) and (close > upper):
        signal = f"📉 سیگنال فروش {name}"
    else:
        signal = f"ℹ️ هیچ سیگنالی برای {name} نیست"

    return signal, close, rsi

# --- دریافت دامیننس از CoinGecko ---
def get_dominance():
    url = "https://api.coingecko.com/api/v3/global"
    resp = requests.get(url)
    data = resp.json()
    dom = data.get("data", {}).get("market_cap_percentage", {})
    btc_dom = dom.get("btc", None)
    eth_dom = dom.get("eth", None)
    usdt_dom = dom.get("usdt", None)
    return btc_dom, eth_dom, usdt_dom

# --- دریافت Fear & Greed Index ---
def get_fear_greed():
    url = "https://api.alternative.me/fng/"
    resp = requests.get(url)
    data = resp.json()
    if "data" in data and len(data["data"]) > 0:
        val = data["data"][0]["value"]
        classification = data["data"][0]["value_classification"]
        return val, classification
    return None, None

# --- دریافت خبرهای کلان از investing.com (scraping ساده) ---
def get_economic_news():
    url = "https://www.investing.com/economic-calendar/"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers)
        soup = BeautifulSoup(resp.content, "html.parser")
        news_list = []
        # بخش اخبار اصلی در جدول
        rows = soup.select("table.ecEventsTable tbody tr")
        for r in rows[:5]:  # ۵ خبر اول
            time = r.select_one("td.first.left.time")
            title = r.select_one("td.event")
            impact = r.select_one("td.sentiment")
            if time and title and impact:
                time_text = time.text.strip()
                title_text = title.text.strip()
                impact_text = impact.text.strip()
                news_list.append(f"{time_text} | {impact_text} | {title_text}")
        return news_list
    except Exception as e:
        print("⚠️ خطا در دریافت اخبار کلان:", e)
        return []

# --- ساخت پیام نهایی ---
def build_message(signals, dominances, fear_greed_val, fear_greed_class, news_list):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"📊 گزارش تحلیل رمزارزها - {now}\n\n"

    for sym, sig, price, rsi in signals:
        msg += f"{sig}\nقیمت: {price:.2f} USD\nRSI: {rsi:.2f}\n\n"

    msg += f"🔹 دامیننس‌ها:\nBTC: {dominances[0]:.2f}% | ETH: {dominances[1]:.2f}% | USDT: {dominances[2]:.2f}%\n\n"
    msg += f"😨 شاخص ترس و طمع: {fear_greed_val} ({fear_greed_class})\n\n"

    msg += "📰 اخبار کلان اقتصادی:\n"
    if news_list:
        for news in news_list:
            msg += f"- {news}\n"
    else:
        msg += "اخباری یافت نشد.\n"

    return msg

# --- برنامه اصلی ---
def main():
    symbols = {
        "BTC-USD": "بیت‌کوین",
        "ETH-USD": "اتریوم",
        "XRP-USD": "ریپل"
    }

    signals = []
    for sym, name in symbols.items():
        try:
            df, price_col = download_and_process(sym)
            sig, price, rsi = analyze_signal(df, price_col, name)
            signals.append((sym, sig, price, rsi))
        except Exception as e:
            print(f"⚠️ خطا در تحلیل {name}: {e}")

    dominances = get_dominance()
    fear_greed_val, fear_greed_class = get_fear_greed()
    news_list = get_economic_news()

    message = build_message(signals, dominances, fear_greed_val, fear_greed_class, news_list)
    send_telegram_message(message)
    print("✅ پیام به تلگرام ارسال شد.")

if __name__ == "__main__":
    main()
