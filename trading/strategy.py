"""ETF 動能輪動的訊號計算。純函數，不碰網路、不碰券商，方便測試。"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import StrategyConfig


def month_end_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """每個月最後一個交易日。"""
    s = pd.Series(index, index=index)
    return pd.DatetimeIndex(s.groupby([index.year, index.month]).last().values)


def momentum_scores(prices: pd.DataFrame, asof: pd.Timestamp, cfg: StrategyConfig) -> pd.Series:
    """以 asof 當天收盤為基準，算每檔的多視窗平均報酬。"""
    hist = prices.loc[:asof]
    if hist.empty:
        raise ValueError("asof 早於資料起點")
    last = hist.iloc[-1]
    scores = pd.Series(0.0, index=prices.columns)
    for m in cfg.lookbacks_months:
        # 用「約 21 個交易日 * m」回看，比用日曆月穩定
        n = 21 * m
        if len(hist) <= n:
            return pd.Series(float("nan"), index=prices.columns)
        past = hist.iloc[-1 - n]
        scores += last / past - 1.0
    # 某資產在回看期內還不存在 → NaN，之後視為不可投資
    return scores / len(cfg.lookbacks_months)


def target_weights(prices: pd.DataFrame, asof: pd.Timestamp, cfg: StrategyConfig) -> pd.Series:
    """回傳目標權重（總和 1）。欄位包含 universe 和 defensive。"""
    scores = momentum_scores(prices, asof, cfg)
    all_assets = list(cfg.universe) + [cfg.defensive]
    w = pd.Series(0.0, index=all_assets)
    if np.isnan(scores[cfg.defensive]) or scores[list(cfg.universe)].isna().all():
        w[cfg.defensive] = 1.0
        return w

    threshold = scores[cfg.defensive] if cfg.use_defensive_as_threshold else 0.0
    ranked = scores[list(cfg.universe)].dropna().sort_values(ascending=False)
    picks = ranked.head(cfg.top_n)
    slot = 1.0 / cfg.top_n
    for t, sc in picks.items():
        if sc > threshold:
            w[t] += slot
        else:
            w[cfg.defensive] += slot
    return w
