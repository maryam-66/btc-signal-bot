import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
import sys

# --- اطلاعات تلگرام ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID_ENV = os.getenv("TELEGRAM_CHAT_ID")
NEWSAPI_KEY = os.getenv("1fbbb3b298474644b2187f4a534484d4")  # کلید API اخبار

if TOKEN is None or CHAT_ID_ENV is None:
    print("\u274c خطا: توکن یا آیدی چت تنظیم نشده‌اند!")
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
           'q=bitcoin OR ethereum OR ripple OR crypto OR "federal reserve"&'
           'language=en&sortBy=publishedAt&pageSize=3&apiKey={api_key}').format(api_key=NEWSAPI_KEY)
    response = requests.get(url)
    if response.status_code == 200:
        articles = response.json()['articles']
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
        value_classification = data['data'][0]['value_classification']
        return f"📊 شاخص ترس و طمع: {value} ({value_classification})"
    else:
        return "⚠️ خطا در دریافت شاخص ترس و طمع"

# --- روند کلی بازار ---
def get_market_overview():
    url = "https://api.coingecko.com/api/v3/global"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()['data']
        market_cap = data['total_market_cap']['usd']
        btc_dominance = data['market_cap_percentage']['btc']
        eth_dominance = data['market_cap_percentage']['eth']
        return (f"🌐 مارکت کپ کل: {market_cap/1e9:.2f} میلیارد دلار\n"
                f"🔶 دامیننس BTC: {btc_dominance:.2f}%\n"
                f"🔷 دامیننس ETH: {eth_dominance:.2f}%")
    else:
        return "⚠️ خطا در دریافت اطلاعات مارکت"

# --- تنظیمات کلی تحلیل تکنیکال ---
symbols = {
    'BTC-USD': 'بیت‌کوین',
    'ETH-USD': 'اتریوم',
    'XRP-USD': 'ریپل'
}

start_date = '2024-12-01'
end_date = '2025-07-01'

final_messages = []

for symbol, name in symbols.items():
    df = yf.download(symbol, start=start_date, end=end_date, auto_adjust=False)

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ['_'.join(col).strip() for col in df.columns]

    if 'Close' not in df.columns:
        close_candidates = [col for col in df.columns if 'Close' in col]
        if close_candidates:
            df.rename(columns={close_candidates[0]: 'Close'}, inplace=True)
        else:
            print(f"⚠️ ستون 'Close' در داده‌های {symbol} یافت نشد!")
            continue

    df = df[['Close']].dropna()

    # اندیکاتورها
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

    df.dropna(subset=['RSI', 'UpperBand', 'LowerBand'], inplace=True)

    # سیگنال‌ها
    df['Buy_Signal'] = (df['RSI'] < 30) & (df['Close'] < df['LowerBand'])
    df['Sell_Signal'] = (df['RSI'] > 70) & (df['Close'] > df['UpperBand'])

    # محاسبه سود و زیان
    buy_dates = df[df['Buy_Signal']].index
    sell_dates = df[df['Sell_Signal']].index
    if len(buy_dates) == 0 or len(sell_dates) == 0:
        continue

    if sell_dates[0] < buy_dates[0]:
        sell_dates = sell_dates[1:]
    if len(buy_dates) > len(sell_dates):
        buy_dates = buy_dates[:-1]

    profits = [df.loc[sell]['Close'] - df.loc[buy]['Close'] for buy, sell in zip(buy_dates, sell_dates)]

    total_trades = len(profits)
    total_profit = sum(profits)
    avg_profit = np.mean(profits)

    last = df.iloc[-1]
    date_str = last.name.strftime('%Y-%m-%d')
    if last['Buy_Signal']:
        signal_text = f"📈 سیگنال خرید {name} ({date_str})\nقیمت: {last['Close']:.2f} USD\n📊 RSI: {last['RSI']:.2f}"
    elif last['Sell_Signal']:
        signal_text = f"📉 سیگنال فروش {name} ({date_str})\nقیمت: {last['Close']:.2f} USD\n📊 RSI: {last['RSI']:.2f}"
    else:
        signal_text = f"ℹ️ {name} - ({date_str}) هیچ سیگنالی صادر نشد."

    summary = f"✅ {name}\nمعاملات: {total_trades}\nسود کل: {total_profit:.2f} USD\nمیانگین سود هر معامله: {avg_profit:.2f} USD"
    final_messages.append(signal_text + "\n" + summary)

# --- دریافت داده‌های اضافی ---
news = get_latest_news()
fear_greed = get_fear_greed_index()
market_overview = get_market_overview()

# --- ارسال نهایی ---
final_report = '\n\n'.join(final_messages)
extra_info = f"\n\n📰 اخبار مهم:\n{news}\n\n{fear_greed}\n\n{market_overview}"

send_telegram_message(final_report + extra_info)
