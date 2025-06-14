import time
import requests
import datetime
import os
import csv
import threading

# === Konfigurasi ===
coins = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
interval = 3600  # 1 jam
csv_file = "crypto_prices_full.csv"
telegram_token = "ISI_TOKEN_KAMU"
telegram_chat_id = "ISI_CHAT_ID_KAMU"
lock_file = ".collector.lock"
last_update_id = None

# === Fungsi Utilitas ===
def get_price_volume(coin):
    url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={coin}"
    data = requests.get(url).json()
    return float(data["lastPrice"]), float(data["volume"])

def calculate_ema(prices, period=20):
    if len(prices) < period:
        return prices[-1]
    ema = prices[0]
    k = 2 / (period + 1)
    for price in prices[1:]:
        ema = price * k + ema * (1 - k)
    return ema

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50
    gains, losses = [], []
    for i in range(1, period + 1):
        delta = prices[-i] - prices[-i - 1]
        (gains if delta > 0 else losses).append(abs(delta))
    avg_gain = sum(gains) / period if gains else 0.01
    avg_loss = sum(losses) / period if losses else 0.01
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    data = {"chat_id": telegram_chat_id, "text": message}
    requests.post(url, data=data)

def log_message(message):
    with open("trend_log.txt", "a") as f:
        f.write(f"{datetime.datetime.now()}\n{message}\n\n")

def append_csv(coin, timestamp, price, volume, ema, rsi, trend):
    file_exists = os.path.isfile(csv_file)
    with open(csv_file, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["coin", "timestamp", "price", "volume", "ema", "rsi", "trend"])
        writer.writerow([coin, timestamp, price, volume, ema, rsi, trend])

def load_prices(coin):
    if not os.path.exists(csv_file):
        return []
    with open(csv_file) as f:
        rows = [row for row in csv.reader(f) if row and row[0] == coin]
        return [float(row[2]) for row in rows[-30:]]

def analyze_trend(price, ema, rsi):
    if price > ema and rsi > 55:
        return "Bullish"
    elif price < ema and rsi < 45:
        return "Bearish"
    else:
        return "Sideways"

def analyze_and_send():
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output = f"📊 Dashboard Tren AI ({timestamp})\n\n"
    for coin in coins:
        try:
            price, volume = get_price_volume(coin)
            history = load_prices(coin) + [price]
            ema = calculate_ema(history)
            rsi = calculate_rsi(history)
            trend = analyze_trend(price, ema, rsi)

            append_csv(coin, timestamp, price, volume, ema, rsi, trend)
            emoji = "⬆️" if trend == "Bullish" else "⬇️" if trend == "Bearish" else "⏸"
            output += (
                f"{coin} - {emoji} {trend}\n"
                f"Price: {price} | EMA20: {ema:.2f} | RSI: {rsi:.1f} | Vol: {volume:.0f}\n\n"
            )
        except Exception as e:
            output += f"{coin} - Error: {e}\n\n"
    send_telegram_message(output)
    log_message(output)

# === Polling Pesan Telegram ===
def check_telegram_command():
    global last_update_id
    while True:
        try:
            url = f"https://api.telegram.org/bot{telegram_token}/getUpdates"
            if last_update_id:
                url += f"?offset={last_update_id + 1}"
            response = requests.get(url).json()
            for update in response.get("result", []):
                last_update_id = update["update_id"]
                message = update.get("message", {})
                chat_id = message.get("chat", {}).get("id")
                text = message.get("text", "").strip()
                if chat_id and text.lower() == "/status":
                    analyze_and_send()
        except Exception as e:
            print(f"Error polling Telegram: {e}")
        time.sleep(5)

# === Cek Lock ===
if os.path.exists(lock_file):
    print("Bot sudah berjalan.")
    exit()
with open(lock_file, "w") as f:
    f.write(str(time.time()))

try:
    # Thread Telegram command listener
    threading.Thread(target=check_telegram_command, daemon=True).start()

    # Loop utama setiap 1 jam
    while True:
        analyze_and_send()
        time.sleep(interval)
finally:
    if os.path.exists(lock_file):
        os.remove(lock_file)
