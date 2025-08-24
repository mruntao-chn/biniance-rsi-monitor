# scan_rsi.py
# 升级版：输出两个独立列表 - 超买 和 超卖
# 作者：Qwen

import requests
import numpy as np
import pandas as pd
from talib import RSI
from datetime import datetime, timedelta
import os

# ========== 配置参数 ==========
CSV_HISTORY = "data/rsi-history.csv"
CSV_OVERBOUGHT = "rsi-overbought.csv"   # ✅ 新增：超买列表
CSV_OVERSOLD = "rsi-oversold.csv"       # ✅ 新增：超卖列表
TIMEFRAME = "15m"
RSI_PERIOD = 14
OVERBOUGHT = 70
OVERSOLD = 30
DAYS_TO_KEEP = 7

os.makedirs("data", exist_ok=True)

def get_usdt_futures():
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    try:
        response = requests.get(url, timeout=10).json()
        symbols = [
            sym["symbol"] for sym in response["symbols"]
            if sym["symbol"].endswith("USDT") and sym["status"] == "TRADING"
        ]
        return sorted(symbols)
    except Exception as e:
        print(f"❌ 获取交易对失败: {e}")
        return []

def get_klines(symbol, interval=TIMEFRAME, limit=50):
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        response = requests.get(url, params=params, timeout=10).json()
        return [float(k[4]) for k in response]
    except:
        return []

def load_history():
    if not os.path.exists(CSV_HISTORY):
        return pd.DataFrame(columns=["Symbol", "RSI", "Signal", "Timestamp"])
    try:
        df = pd.read_csv(CSV_HISTORY)
        if "Timestamp" in df.columns:
            df["Timestamp"] = pd.to_datetime(df["Timestamp"])
        return df
    except:
        return pd.DataFrame(columns=["Symbol", "RSI", "Signal", "Timestamp"])

def save_history(df):
    df.to_csv(CSV_HISTORY, index=False)

def filter_last_n_days(df, days=DAYS_TO_KEEP):
    if df.empty:
        return df
    cutoff = datetime.now() - timedelta(days=days)
    return df[df["Timestamp"] >= cutoff].copy()

def main():
    print("🔍 开始扫描 Binance USDT 合约 RSI...")

    history_df = load_history()
    symbols = get_usdt_futures()
    if not symbols:
        print("❌ 未获取到任何交易对")
        return

    print(f"📊 共 {len(symbols)} 个交易对")

    now = pd.Timestamp.now(tz='Asia/Shanghai')
    new_records = []

    for symbol in symbols:
        try:
            closes = get_klines(symbol, TIMEFRAME, 50)
            if len(closes) < RSI_PERIOD:
                continue

            rsi_values = RSI(np.array(closes), timeperiod=RSI_PERIOD)
            current_rsi = rsi_values[-1]

            if current_rsi > OVERBOUGHT or current_rsi < OVERSOLD:
                signal = "超买" if current_rsi > OVERBOUGHT else "超卖"
                new_records.append({
                    "Symbol": symbol,
                    "RSI": round(current_rsi, 2),
                    "Signal": signal,
                    "Timestamp": now.strftime("%Y-%m-%d %H:%M")
                })
        except Exception as e:
            continue

    print(f"✅ 扫描完成，发现 {len(new_records)} 个异常信号")

    # 更新历史记录
    if new_records:
        new_df = pd.DataFrame(new_records)
        updated_history = pd.concat([history_df, new_df], ignore_index=True)
    else:
        updated_history = history_df.copy()

    # 去重 + 保留最新
    if not updated_history.empty:
        updated_history = updated_history.sort_values("Timestamp", ascending=False)
        updated_history = updated_history.drop_duplicates(subset=["Symbol"], keep="first")

    # 只保留最近7天
    updated_history = filter_last_n_days(updated_history)
    save_history(updated_history)

    # ✅ 生成两个独立列表
    overbought_list = updated_history[updated_history["RSI"] > OVERBOUGHT][["Symbol"]]
    oversold_list = updated_history[updated_history["RSI"] < OVERSOLD][["Symbol"]]

    # 保存为两个 CSV 文件
    overbought_list.to_csv(CSV_OVERBOUGHT, index=False)
    oversold_list.to_csv(CSV_OVERSOLD, index=False)

    print(f"📤 超买列表已生成: {len(overbought_list)} 个标的 → {CSV_OVERBOUGHT}")
    print(f"📤 超卖列表已生成: {len(oversold_list)} 个标的 → {CSV_OVERSOLD}")

    # 显示示例
    if not overbought_list.empty:
        print("\n📈 超买示例:", overbought_list.head()["Symbol"].tolist())
    if not oversold_list.empty:
        print("📉 超卖示例:", oversold_list.head()["Symbol"].tolist())

if __name__ == "__main__":
    main()
