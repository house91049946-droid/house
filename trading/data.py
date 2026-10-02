"""日線資料下載與快取。來源 yfinance，快取成 CSV 放在 trading/data/。"""
from __future__ import annotations

import os
from datetime import date

import pandas as pd

CACHE_DIR = os.path.join(os.path.dirname(__file__), "data")


def _cache_path(ticker: str) -> str:
    return os.path.join(CACHE_DIR, f"{ticker}.csv")


def load_prices(
    tickers: list[str] | tuple[str, ...],
    start: str,
    end: str | None = None,
    refresh: bool = False,
) -> pd.DataFrame:
    """回傳 adjusted close 的寬表：index 為日期，欄位為 ticker。

    快取規則：若 CSV 存在且最後一筆日期是今天或昨天就直接用，否則重新下載。
    """
    import yfinance as yf

    os.makedirs(CACHE_DIR, exist_ok=True)
    frames: dict[str, pd.Series] = {}
    for t in tickers:
        p = _cache_path(t)
        if not refresh and os.path.exists(p):
            s = pd.read_csv(p, index_col=0, parse_dates=True).iloc[:, 0]
            if (date.today() - s.index[-1].date()).days <= 3:
                frames[t] = s
                continue
        df = yf.download(t, start=start, end=end, auto_adjust=True, progress=False)
        if df.empty:
            raise RuntimeError(f"{t} 下載失敗，請檢查網路或 ticker")
        s = df["Close"]
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0]
        s.name = t
        s.to_csv(p)
        frames[t] = s
    out = pd.DataFrame(frames).sort_index()
    out = out.loc[start:end] if end else out.loc[start:]
    return out.dropna(how="all")
