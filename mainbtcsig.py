import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import requests
import os

# اطلاعات تلگرام
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = int(os.getenv('TELEGRAM_CHAT_ID'))


def send_telegram_message(message):
    url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
    data = {'chat_id': CHAT_ID, 'text': message}
    requests.post(url, data=data)


# 1. دانلود داده بیت‌کوین (با auto_adjust=False برای جلوگیری از ساختار پیچیده)
btc = yf.download('BTC-USD', start='2024-12-01', end='2025-07-01', auto_adjust=False)

# اگر MultiIndex داشت، آن را فلت کن
if isinstance(btc.columns, pd.MultiIndex):
    btc.columns = ['_'.join(col).strip() if isinstance(col, tuple) else col for col in btc.columns]

# بررسی اینکه ستون Close وجود دارد یا نه
if 'Close' not in btc.columns:
    close_candidates = [col for col in btc.columns if 'Close' in col]
    if close_candidates:
        close_col = close_candidates[0]
        btc.rename(columns={close_col: 'Close'}, inplace=True)
    else:
        raise ValueError("ستون 'Close' در داده‌های دریافتی یافت نشد!")

# فقط ستون Close
btc = btc[['Close']]
btc.dropna(inplace=True)

# 2. محاسبه اندیکاتورها
btc['7_MA'] = btc['Close'].rolling(window=7).mean()
btc['MA20'] = btc['Close'].rolling(window=20).mean()
btc['STD20'] = btc['Close'].rolling(window=20).std()
btc['UpperBand'] = btc['MA20'] + 2 * btc['STD20']
btc['LowerBand'] = btc['MA20'] - 2 * btc['STD20']

# RSI
delta = btc['Close'].diff()
gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)
avg_gain = gain.rolling(window=14).mean()
avg_loss = loss.rolling(window=14).mean()
rs = avg_gain / avg_loss
btc['RSI'] = 100 - (100 / (1 + rs))

# حذف ردیف‌های ناقص
btc.dropna(subset=['RSI', 'UpperBand', 'LowerBand'], inplace=True)

# 3. سیگنال‌ها
btc['Buy_Signal'] = (btc['RSI'] < 30) & (btc['Close'] < btc['LowerBand'])
btc['Sell_Signal'] = (btc['RSI'] > 70) & (btc['Close'] > btc['UpperBand'])

# 4. نمودار
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

# قیمت و میانگین‌ها
ax1.plot(btc.index, btc['Close'], label='BTC Price', marker='o', markersize=4, linewidth=1.2)
ax1.plot(btc.index, btc['7_MA'], label='7-day MA', linestyle='--', color='orange')
ax1.plot(btc.index, btc['UpperBand'], label='Bollinger Upper', linestyle='--', color='green')
ax1.plot(btc.index, btc['LowerBand'], label='Bollinger Lower', linestyle='--', color='red')

# سیگنال‌ها
ax1.plot(btc[btc['Buy_Signal']].index, btc[btc['Buy_Signal']]['Close'], '^', color='green', label='Buy Signal', markersize=10)
ax1.plot(btc[btc['Sell_Signal']].index, btc[btc['Sell_Signal']]['Close'], 'v', color='red', label='Sell Signal', markersize=10)

ax1.set_title('BTC Technical Analysis', fontsize=14)
ax1.set_ylabel('Price (USD)')
ax1.grid(True)
ax1.legend()

# RSI chart
ax2.plot(btc.index, btc['RSI'], label='RSI', color='purple')
ax2.axhline(70, color='red', linestyle='--', linewidth=1)
ax2.axhline(30, color='green', linestyle='--', linewidth=1)
ax2.set_title('RSI Indicator', fontsize=14)
ax2.set_ylabel('RSI')
ax2.set_ylim(0, 100)
ax2.grid(True)
ax2.legend()

plt.xlabel('Date')
plt.tight_layout()
plt.show()

# 1. گرفتن فقط تاریخ‌های سیگنال خرید و فروش
buy_dates = btc[btc['Buy_Signal']].index
sell_dates = btc[btc['Sell_Signal']].index

# 2. مطمئن می‌شیم اولین سیگنال خرید هست، آخرین سیگنال فروش
if sell_dates[0] < buy_dates[0]:
    sell_dates = sell_dates[1:]
if len(buy_dates) > len(sell_dates):
    buy_dates = buy_dates[:-1]

# 3. محاسبه سود و زیان
profits = []
for buy_date, sell_date in zip(buy_dates, sell_dates):
    buy_price = btc.loc[buy_date]['Close']
    sell_price = btc.loc[sell_date]['Close']
    profit = sell_price - buy_price
    profits.append(profit)

# 4. نمایش نتیجه
total_trades = len(profits)
total_profit = sum(profits)
avg_profit = np.mean(profits)

print(f'✅ Total Trades: {total_trades}')
print(f'💰 Total Profit: {total_profit:.2f} USD')
print(f'📈 Average Profit per Trade: {avg_profit:.2f} USD')

# 5. ارسال پیام تلگرام اگر سیگنال جدید وجود داشت
last = btc.iloc[-1]

if last['Buy_Signal']:
    send_telegram_message(f"📈 سیگنال خرید بیت‌کوین ({last.name.date()})\nقیمت: {last['Close']:.2f} USD\n📉 RSI: {last['RSI']:.2f}")
elif last['Sell_Signal']:
    send_telegram_message(f"📉 سیگنال فروش بیت‌کوین ({last.name.date()})\nقیمت: {last['Close']:.2f} USD\n📈 RSI: {last['RSI']:.2f}")
else:
    send_telegram_message(f"ℹ️ در تاریخ {last.name.date()} هیچ سیگنالی صادر نشد.")

