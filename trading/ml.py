"""Walk-forward 訓練與信心輸出。

規則：每年年初用「之前所有年份」重訓一次，預測接下來 12 個月。
模型永遠沒看過它要預測的那段資料。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler

from .features import FEATURE_NAMES


@dataclass(frozen=True)
class MLConfig:
    model: str = "logit"          # "logit" 或 "gbm"；資料少時 logit 比較不會過擬合
    min_train_months: int = 60    # 至少 5 年資料才開始預測
    retrain_every_months: int = 12
    # 信心低於 low 全退守，介於 low 與 high 之間按比例減碼，高於 high 全倉
    conf_low: float = 0.40
    conf_high: float = 0.55


def make_model(name: str) -> Pipeline:
    if name == "logit":
        return make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=1000))
    if name == "gbm":
        return make_pipeline(
            StandardScaler(),
            GradientBoostingClassifier(n_estimators=100, max_depth=2, learning_rate=0.05, subsample=0.8, random_state=0),
        )
    raise ValueError(name)


def walk_forward_confidence(ds: pd.DataFrame, cfg: MLConfig = MLConfig()) -> pd.Series:
    """回傳每個月底的信心（0 到 1）。沒有足夠訓練資料的月份為 NaN。"""
    labeled = ds.dropna(subset=["label"])
    X_all = ds[FEATURE_NAMES]
    conf = pd.Series(np.nan, index=ds.index)
    model: Pipeline | None = None
    last_train_idx = -10**9
    for i, day in enumerate(ds.index):
        train = labeled.loc[: day - pd.Timedelta(days=1)]
        # 標籤要等下個月底才知道，所以訓練集最後一列的標籤在 day 當天其實還沒揭曉，去掉
        train = train.iloc[:-1] if len(train) else train
        if len(train) < cfg.min_train_months:
            continue
        if model is None or i - last_train_idx >= cfg.retrain_every_months:
            model = make_model(cfg.model)
            model.fit(train[FEATURE_NAMES].values, train["label"].values)
            last_train_idx = i
        conf[day] = float(model.predict_proba(X_all.loc[[day]].values)[0, 1])
    return conf


def exposure_from_confidence(conf: float, cfg: MLConfig = MLConfig()) -> float:
    """信心 → 風險資產曝險比例（0 到 1），其餘退守 BIL。"""
    if np.isnan(conf):
        return 1.0
    if conf <= cfg.conf_low:
        return 0.0
    if conf >= cfg.conf_high:
        return 1.0
    return (conf - cfg.conf_low) / (cfg.conf_high - cfg.conf_low)


def apply_overlay(weights: pd.DataFrame, conf: pd.Series, defensive: str, cfg: MLConfig = MLConfig()) -> pd.DataFrame:
    """把信心套到每月目標權重上。"""
    out = weights.copy()
    for day in out.index:
        e = exposure_from_confidence(float(conf.get(day, np.nan)), cfg)
        risky = out.loc[day].drop(defensive)
        out.loc[day, risky.index] = risky * e
        out.loc[day, defensive] = 1.0 - out.loc[day, risky.index].sum()
    return out


def feature_importance(ds: pd.DataFrame, cfg: MLConfig = MLConfig()) -> pd.Series:
    """用全部有標籤的資料訓練一次，看哪些特徵重要。只做參考，不用於交易。"""
    labeled = ds.dropna(subset=["label"])
    m = make_model(cfg.model).fit(labeled[FEATURE_NAMES].values, labeled["label"].values)
    est = m.steps[-1][1]
    imp = est.coef_[0] if hasattr(est, "coef_") else est.feature_importances_
    return pd.Series(imp, index=FEATURE_NAMES).sort_values(key=abs, ascending=False)
