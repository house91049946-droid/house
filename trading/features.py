"""第 2 層：元標籤（meta-labeling）的特徵與標籤。

不預測價格。預測的是「這個月動能訊號會不會贏過 BIL」。
所有特徵只用 asof 當天以前的資料，避免偷看未來。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import StrategyConfig
from .strategy import momentum_scores, month_end_dates, target_weights

FEATURE_NAMES = [
    "spy_vol20",       # SPY 近 20 日年化波動
    "spy_vol60",       # SPY 近 60 日年化波動
    "vol_ratio",       # 短期波動 / 長期波動，>1 代表波動正在升高
    "spy_dd252",       # SPY 距 52 週高點的回撤
    "spy_ma200_gap",   # SPY 收盤相對 200 日均線的距離
    "mom_spread",      # 最強資產動能 - BIL 動能
    "mom_breadth",     # 籃子裡動能贏過 BIL 的比例
    "mom_dispersion",  # 籃子動能的標準差，高代表趨勢分化明顯
    "tlt_mom",         # 長債動能，利率環境代理
    "gld_mom",         # 黃金動能，避險情緒代理
    "avg_corr60",      # 籃子近 60 日平均兩兩相關，高代表齊漲齊跌
    "prev_month_ret",  # 上個月策略本身的報酬
]


def _ann_vol(s: pd.Series, n: int) -> float:
    return float(s.pct_change().tail(n).std() * np.sqrt(252))


def features_at(prices: pd.DataFrame, asof: pd.Timestamp, cfg: StrategyConfig, prev_ret: float) -> pd.Series | None:
    hist = prices.loc[:asof]
    if len(hist) < 260:
        return None
    scores = momentum_scores(prices, asof, cfg)
    if np.isnan(scores["SPY"]) or np.isnan(scores[cfg.defensive]):
        return None
    spy = hist["SPY"]
    uni = list(cfg.universe)
    bil = scores[cfg.defensive]
    rets60 = hist[uni].pct_change().tail(60)
    corr = rets60.corr().values
    avg_corr = float(np.nanmean(corr[np.triu_indices_from(corr, k=1)]))
    v20, v60 = _ann_vol(spy, 20), _ann_vol(spy, 60)
    return pd.Series(
        {
            "spy_vol20": v20,
            "spy_vol60": v60,
            "vol_ratio": v20 / v60 if v60 > 0 else 1.0,
            "spy_dd252": float(spy.iloc[-1] / spy.tail(252).max() - 1),
            "spy_ma200_gap": float(spy.iloc[-1] / spy.tail(200).mean() - 1),
            "mom_spread": float(scores[uni].max() - bil),
            "mom_breadth": float((scores[uni].dropna() > bil).mean()),
            "mom_dispersion": float(scores[uni].std()),
            "tlt_mom": float(scores.get("TLT", 0.0)),
            "gld_mom": float(scores.get("GLD", 0.0)),
            "avg_corr60": avg_corr,
            "prev_month_ret": prev_ret,
        }
    )


def build_dataset(prices: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    """每個月底一列：特徵 + 標籤 + 當月策略超額報酬。

    label = 1 代表「月底決定的目標組合，下個月報酬 > BIL」。
    最後一列沒有未來資料，label 為 NaN，留給實盤推論用。
    """
    rebal = month_end_dates(prices.index)
    rows: list[dict] = []
    prev_ret = 0.0
    for i, day in enumerate(rebal):
        f = features_at(prices, day, cfg, prev_ret)
        if f is None:
            continue
        tw = target_weights(prices, day, cfg)
        if i + 1 < len(rebal):
            nxt = rebal[i + 1]
            period = prices.loc[day:nxt]
            asset_ret = period.iloc[-1] / period.iloc[0] - 1
            port_ret = float((tw.reindex(asset_ret.index).fillna(0.0) * asset_ret).sum())
            excess = port_ret - float(asset_ret[cfg.defensive])
            label = float(excess > 0)
        else:
            port_ret, excess, label = np.nan, np.nan, np.nan
        row = f.to_dict()
        row.update({"date": day, "port_ret": port_ret, "excess": excess, "label": label})
        rows.append(row)
        prev_ret = port_ret if not np.isnan(port_ret) else 0.0
    return pd.DataFrame(rows).set_index("date")
