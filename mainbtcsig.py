# تحلیل و سیگنال‌دهی حرفه‌ای برای BTC، ETH، XRP با ارسال پیام به تلگرام
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import requests
import os
import sys

# --- اطلاعات تلگرام ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID_ENV = os.getenv("TELEGRAM_CHAT_ID")

if TOKEN is None or CHAT_ID_ENV is None:
    print("\u274c خطا: توکن یا آیدی چت تنظیم نشده‌اند!")
    sys.exit(1)

CHAT_ID = int(CHAT_ID_ENV)

def send_telegram_message(message):
    url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
    data = {'chat_id': CHAT_ID, 'text': message}
    requests.post(url, data=data)

# --- تنظیمات کلی ---
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
            raise ValueError(f"ستون 'Close' در داده‌های {symbol} یافت نشد!")

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
    if last['Buy_Signal']:
        signal_text = f"\ud83d\udcc8 سیگنال خرید {name} ({last.name.date()})\nقیمت: {last['Close']:.2f} USD\n\ud83d\udcc9 RSI: {last['RSI']:.2f}"
    elif last['Sell_Signal']:
        signal_text = f"\ud83d\udcc9 سیگنال فروش {name} ({last.name.date()})\nقیمت: {last['Close']:.2f} USD\n\ud83d\udcc8 RSI: {last['RSI']:.2f}"
    else:
        signal_text = f"ℹ️ {name} - ({last.name.date()}) هیچ سیگنالی صادر نشد."

    summary = f"✅ {name}\nمعاملات: {total_trades}\nسود کل: {total_profit:.2f} USD\nمیانگین سود هر معامله: {avg_profit:.2f} USD"
    final_messages.append(signal_text + "\n" + summary)

# --- ارسال نهایی ---
final_report = '\n\n'.join(final_messages)
send_telegram_message(final_report)
