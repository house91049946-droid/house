"""第 2 層：特徵、標籤、walk-forward 的邏輯測試，合成資料。"""
import numpy as np
import pandas as pd
import pytest

from trading.backtest import run_backtest
from trading.config import BacktestConfig, StrategyConfig
from trading.features import FEATURE_NAMES, build_dataset, features_at
from trading.ml import MLConfig, apply_overlay, exposure_from_confidence, walk_forward_confidence

CFG = StrategyConfig(universe=("SPY", "TLT", "GLD"), defensive="BIL", lookbacks_months=(3, 6), top_n=1)


def synth(days: int = 2200, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2012-01-02", periods=days)
    out = {}
    for t, d, v in [("SPY", .10, .16), ("TLT", .03, .12), ("GLD", .05, .14), ("BIL", .01, .002)]:
        out[t] = 100 * np.cumprod(1 + rng.normal(d / 252, v / np.sqrt(252), days))
    return pd.DataFrame(out, index=idx)


def test_features_use_only_past_data():
    p = synth()
    asof = p.index[400]
    f1 = features_at(p, asof, CFG, 0.0)
    p2 = p.copy()
    p2.iloc[401:] *= 5.0  # 竄改未來
    f2 = features_at(p2, asof, CFG, 0.0)
    pd.testing.assert_series_equal(f1, f2)


def test_features_none_when_history_short():
    assert features_at(synth(days=100), synth(days=100).index[-1], CFG, 0.0) is None


def test_dataset_shape_and_labels():
    ds = build_dataset(synth(), CFG)
    assert set(FEATURE_NAMES) <= set(ds.columns)
    assert ds["label"].iloc[-1] != ds["label"].iloc[-1]  # 最後一列 NaN
    assert ds["label"].iloc[:-1].isin([0.0, 1.0]).all()
    assert not ds[FEATURE_NAMES].isna().any().any()


def test_walk_forward_never_predicts_before_min_train():
    ds = build_dataset(synth(), CFG)
    cfg = MLConfig(min_train_months=24)
    conf = walk_forward_confidence(ds, cfg)
    first = conf.first_valid_index()
    assert ds.index.get_loc(first) >= 24
    assert conf.dropna().between(0, 1).all()


def test_exposure_mapping():
    cfg = MLConfig(conf_low=0.4, conf_high=0.6)
    assert exposure_from_confidence(float("nan"), cfg) == 1.0
    assert exposure_from_confidence(0.3, cfg) == 0.0
    assert exposure_from_confidence(0.5, cfg) == pytest.approx(0.5)
    assert exposure_from_confidence(0.9, cfg) == 1.0


def test_overlay_keeps_weights_summing_to_one_and_backtest_accepts_override():
    p = synth()
    eq, w = run_backtest(p, CFG, BacktestConfig(initial_capital=1000.0))
    conf = pd.Series(0.45, index=w.index)
    ov = apply_overlay(w, conf, "BIL", MLConfig(conf_low=0.4, conf_high=0.5))
    assert (ov.sum(axis=1) - 1).abs().max() < 1e-9
    assert (ov["BIL"] >= 0.5 - 1e-9).all()
    eq2, _ = run_backtest(p, CFG, BacktestConfig(initial_capital=1000.0), weights_override=ov)
    assert len(eq2) == len(eq)
