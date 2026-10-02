"""替代資料源：用公開的期貨與 Lean 範例資料拼出 ETF 代理價格。

為什麼需要：雲端環境抓不到 Yahoo，但抓得到 GitHub raw。
來源：
  - robcarver17/pysystemtrade 的回溯調整期貨日線（1982 起，到 2024-03）
  - QuantConnect/Lean 範例日線 + factor file（IWM 2000 起、EEM 2003 起，到 2021-03）
限制：
  - 期貨報酬是「超額報酬」（已扣掉現金利率），所以 BIL 用零報酬的平線代替
  - Lean 的 ETF 是總報酬，兩者混用有小幅不一致，驗證策略邏輯夠用，數字不要拿去當精確預期
  - 資料到 2024-03 為止
用法：python -m trading.data_proxy  會下載、快取並印出範圍
"""
from __future__ import annotations

import io
import os
import zipfile

import numpy as np
import pandas as pd
import requests

PST = "https://raw.githubusercontent.com/robcarver17/pysystemtrade/master/data/futures"
LEAN = "https://raw.githubusercontent.com/QuantConnect/Lean/master/Data/equity/usa"
CACHE = os.path.join(os.path.dirname(__file__), "data", "proxy")

# ETF -> 期貨代碼
FUTURES = {"SPY": "SP500", "QQQ": "NASDAQ", "TLT": "US20", "GLD": "GOLD", "EFA": "MSCIEAFA", "IWM": "RUSSELL", "EEM": "MSCIASIA"}
# ETF -> Lean 代碼與有效起點（Lean 的 eem 在 2003-12 之前是別家公司的舊代號）
LEAN_ETF = {"IWM": ("iwm", "2000-06-01"), "EEM": ("eem", "2003-12-30")}


def _get(url: str) -> bytes:
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, url.split("/futures/")[-1].replace("/", "_") if "/futures/" in url else url.split("/usa/")[-1].replace("/", "_"))
    if os.path.exists(p):
        return open(p, "rb").read()
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    open(p, "wb").write(r.content)
    return r.content


def futures_returns(code: str) -> pd.Series:
    """每日百分比超額報酬 = 回溯調整價差 / 前一日未調整合約價。"""
    adj = pd.read_csv(io.BytesIO(_get(f"{PST}/adjusted_prices_csv/{code}.csv")), parse_dates=["DATETIME"])
    mp = pd.read_csv(io.BytesIO(_get(f"{PST}/multiple_prices_csv/{code}.csv")), parse_dates=["DATETIME"])
    adj = adj.set_index("DATETIME")["price"].resample("D").last().dropna()
    raw = mp.set_index("DATETIME")["PRICE"].resample("D").last().dropna()
    df = pd.concat({"adj": adj, "raw": raw}, axis=1).dropna()
    ret = df["adj"].diff() / df["raw"].shift(1)
    ret = ret[(ret.abs() < 0.25)]  # 去掉資料錯誤造成的離群值
    return ret.dropna()


def lean_adjusted_close(sym: str, start: str) -> pd.Series:
    z = zipfile.ZipFile(io.BytesIO(_get(f"{LEAN}/daily/{sym}.zip")))
    raw = pd.read_csv(z.open(z.namelist()[0]), header=None, names=["dt", "o", "h", "l", "c", "v"])
    raw["dt"] = pd.to_datetime(raw["dt"].str[:8], format="%Y%m%d")
    close = raw.set_index("dt")["c"] / 1e4
    ff = pd.read_csv(io.BytesIO(_get(f"{LEAN}/factor_files/{sym}.csv")), header=None, usecols=[0, 1, 2], names=["dt", "pf", "sf"])
    ff["dt"] = pd.to_datetime(ff["dt"].astype(str), format="%Y%m%d")
    ff = ff.sort_values("dt")
    # 每個交易日套用「第一個 >= 該日」的 factor 列
    idx = np.searchsorted(ff["dt"].values, close.index.values, side="left")
    idx = np.clip(idx, 0, len(ff) - 1)
    adj = close * ff["pf"].values[idx] * ff["sf"].values[idx]
    return adj.loc[start:]


def build_proxy_prices(start: str = "1999-01-01") -> pd.DataFrame:
    """回傳與 yfinance 版相同格式的價格寬表（欄位 = ETF 名）。"""
    rets: dict[str, pd.Series] = {}
    for etf, code in FUTURES.items():
        rets[etf] = futures_returns(code)
    # IWM / EEM：Lean 的 ETF 歷史在前，期貨接在後面
    for etf, (sym, s0) in LEAN_ETF.items():
        lean_ret = lean_adjusted_close(sym, s0).pct_change().dropna()
        fut = rets[etf]
        fut = fut.loc[lean_ret.index[-1] + pd.Timedelta(days=1):]
        rets[etf] = pd.concat([lean_ret, fut])
    df = pd.DataFrame(rets).sort_index()
    df = df.loc[start:]
    # 只留美股交易日：以 SPY 有資料的日子為準
    df = df[df["SPY"].notna()]
    df["BIL"] = 0.0
    # 第一個有效值之前保持 NaN（代表該資產尚未存在），之後缺值視為 0 報酬
    first = df.apply(lambda s: s.first_valid_index())
    for c in df.columns:
        df.loc[first[c]:, c] = df.loc[first[c]:, c].fillna(0.0)
    prices = (1.0 + df).cumprod() * 100.0
    return prices


if __name__ == "__main__":
    p = build_proxy_prices()
    print(p.apply(lambda s: f"{s.first_valid_index().date()} .. {s.last_valid_index().date()}"))
    print(p.tail(3).round(2))
