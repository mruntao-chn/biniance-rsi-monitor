# scan_rsi.py
# Binance USDT 合约 RSI 监控脚本
# 作者：Qwen
# 功能：扫描所有 USDT 永续合约，记录 RSI 异常值，自动更新 CSV

import requests
import numpy as np
import pandas as pd
from talib import RSI
from datetime import datetime, timedelta
import os

# ========== 配置参数 ==========
CSV_HISTORY = "data/rsi-history.csv"        # 历史记录文件
CSV_ALERTS = "rsi-alerts.csv"               # TradingView 导入用的当前异常列表
TIMEFRAME = "15m"                           # K线周期
RSI_PERIOD = 14                             # RSI 周期
OVERBOUGHT = 70                             # 超买阈值
OVERSOLD = 30                               # 超卖阈值
DAYS_TO_KEEP = 7                            # 数据保留天数

# 确保 data 目录存在
os.makedirs("data", exist_ok=True)

def get_usdt_futures():
    """
    获取所有 Binance USDT 永续合约交易对
    返回: ['BTCUSDT', 'ETHUSDT', ...]
    """
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    try:
        response = requests.get(url, timeout=10).json()
        symbols = [
            sym["symbol"] for sym in response["symbols"]
            if sym["symbol"].endswith("USDT") 
            and sym["status"] == "TRADING"
        ]
        return sorted(symbols)
    except Exception as e:
        print(f"❌ 获取交易对失败: {e}")
        return []

def get_klines(symbol, interval=TIMEFRAME, limit=50):
    """
    获取指定交易对的K线数据
    返回: 收盘价列表 [close1, close2, ...]
    """
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        response = requests.get(url, params=params, timeout=10).json()
        return [float(k[4]) for k in response]  # 只取收盘价
    except:
        return []

def load_history():
    """
    加载历史记录
    """
    if not os.path.exists(CSV_HISTORY):
        print("🆕 创建新历史记录文件")
        return pd.DataFrame(columns=["Symbol", "RSI", "Signal", "Timestamp"])
    
    try:
        df = pd.read_csv(CSV_HISTORY)
        if "Timestamp" in df.columns:
            df["Timestamp"] = pd.to_datetime(df["Timestamp"])
        print(f"📁 已加载 {len(df)} 条历史记录")
        return df
    except Exception as e:
        print(f"⚠️  读取历史记录失败: {e}")
        return pd.DataFrame(columns=["Symbol", "RSI", "Signal", "Timestamp"])

def save_history(df):
    """
    保存历史记录
    """
    try:
        df.to_csv(CSV_HISTORY, index=False)
        print(f"💾 历史记录已保存: {len(df)} 条")
    except Exception as e:
        print(f"❌ 保存失败: {e}")

def filter_last_n_days(df, days=DAYS_TO_KEEP):
    """
    只保留最近 N 天的数据
    """
    if df.empty:
        return df
    cutoff = datetime.now() - timedelta(days=days)
    return df[df["Timestamp"] >= cutoff].copy()

def main():
    print("🔍 开始扫描 Binance USDT 合约 RSI...")

    # 1. 加载历史记录
    history_df = load_history()

    # 2. 获取所有交易对
    symbols = get_usdt_futures()
    if not symbols:
        print("❌ 未获取到任何交易对，退出")
        return
    print(f"📊 共 {len(symbols)} 个交易对")

    # 3. 当前时间（带时区）
    now = pd.Timestamp.now(tz='Asia/Shanghai')
    new_records = []

    # 4. 遍历每个交易对
    for symbol in symbols:
        try:
            closes = get_klines(symbol, TIMEFRAME, 50)
            if len(closes) < RSI_PERIOD:
                continue

            # 计算 RSI
            rsi_values = RSI(np.array(closes), timeperiod=RSI_PERIOD)
            current_rsi = rsi_values[-1]

            # 判断是否异常
            if current_rsi > OVERBOUGHT or current_rsi < OVERSOLD:
                signal = "超买" if current_rsi > OVERBOUGHT else "超卖"
                new_records.append({
                    "Symbol": symbol,
                    "RSI": round(current_rsi, 2),
                    "Signal": signal,
                    "Timestamp": now.strftime("%Y-%m-%d %H:%M")
                })

        except Exception as e:
            # 防止一个交易对出错影响整体
            continue

    print(f"✅ 扫描完成，发现 {len(new_records)} 个异常信号")

    # 5. 更新历史记录
    if new_records:
        new_df = pd.DataFrame(new_records)
        updated_history = pd.concat([history_df, new_df], ignore_index=True)
        print(f"🔄 合并后总记录数: {len(updated_history)}")
    else:
        updated_history = history_df.copy()

    # 6. 去重：每个 Symbol 保留最新一条
    if not updated_history.empty:
        updated_history = updated_history.sort_values("Timestamp", ascending=False)
        updated_history = updated_history.drop_duplicates(subset=["Symbol"], keep="first")

    # 7. 只保留最近7天
    updated_history = filter_last_n_days(updated_history)

    # 8. 保存历史记录
    save_history(updated_history)

    # 9. 生成当前警报列表（TradingView 导入用）
    alerts_df = updated_history[
        (updated_history["RSI"] > OVERBOUGHT) | 
        (updated_history["RSI"] < OVERSOLD)
    ].sort_values("Signal", ascending=False)

    # 只导出 Symbol 列，TradingView List 只需要交易对
    alerts_df[["Symbol"]].to_csv(CSV_ALERTS, index=False)
    print(f"📤 已生成 TradingView 导入文件: {len(alerts_df)} 个标的")
    print(f"🌐 文件路径: {CSV_ALERTS}")

    # 10. 显示最近5条
    if not alerts_df.empty:
        print("\n📈 最近异常信号:")
        print(alerts_df.head().to_string(index=False))

if __name__ == "__main__":
    main()
