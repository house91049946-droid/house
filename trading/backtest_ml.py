"""第 2 層驗證：規則基準線 vs ML 元標籤疊加，walk-forward 樣本外比較。
用法：python -m trading.backtest_ml [--model logit|gbm]
"""
from __future__ import annotations

import argparse

import pandas as pd

from .backtest import metrics, run_backtest
from .config import BACKTEST, STRATEGY
from .features import build_dataset
from .ml import MLConfig, apply_overlay, feature_importance, walk_forward_confidence


def compare(prices: pd.DataFrame, mlcfg: MLConfig) -> dict[str, dict[str, float]]:
    base_eq, base_w = run_backtest(prices, STRATEGY, BACKTEST)
    ds = build_dataset(prices, STRATEGY)
    conf = walk_forward_confidence(ds, mlcfg)
    ov_w = apply_overlay(base_w.loc[ds.index.intersection(base_w.index)], conf, STRATEGY.defensive, mlcfg)
    ov_eq, _ = run_backtest(prices, STRATEGY, BACKTEST, weights_override=ov_w)

    # 只比較 ML 真正有在做預測的樣本外區間
    oos_start = conf.dropna().index[0]
    base_oos = base_eq.loc[oos_start:]
    ov_oos = ov_eq.loc[oos_start:]
    base_oos = base_oos / base_oos.iloc[0] * BACKTEST.initial_capital
    ov_oos = ov_oos / ov_oos.iloc[0] * BACKTEST.initial_capital
    spy = prices["SPY"].loc[oos_start:]
    spy = spy / spy.iloc[0] * BACKTEST.initial_capital
    return {
        "oos_start": str(oos_start.date()),
        "baseline": metrics(base_oos, spy),
        "ml_overlay": metrics(ov_oos, spy),
        "confidence": conf.dropna(),
        "dataset": ds,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["logit", "gbm"], default="logit")
    args = ap.parse_args()
    from .data import load_prices

    tickers = list(STRATEGY.universe) + [STRATEGY.defensive]
    prices = load_prices(tickers, BACKTEST.start, BACKTEST.end)
    mlcfg = MLConfig(model=args.model)
    r = compare(prices, mlcfg)

    print(f"\n=== 樣本外比較（{r['oos_start']} 起，模型 {args.model}）===")
    keys = ["CAGR", "MaxDrawdown", "Sharpe", "WorstMonth"]
    print(f"{'':>14}" + "".join(f"{k:>14}" for k in keys))
    for name in ("baseline", "ml_overlay"):
        print(f"{name:>14}" + "".join(
            f"{r[name][k]:>14.2f}" if k == "Sharpe" else f"{r[name][k]:>14.2%}" for k in keys))
    print(f"{'SPY':>14}{r['baseline']['Benchmark_CAGR']:>14.2%}{r['baseline']['Benchmark_MaxDD']:>14.2%}")

    conf = r["confidence"]
    print(f"\n信心分布：min {conf.min():.2f}  median {conf.median():.2f}  max {conf.max():.2f}")
    print(f"退守月份數（信心 <= {mlcfg.conf_low}）：{(conf <= mlcfg.conf_low).sum()} / {len(conf)}")
    ds = r["dataset"]
    acc = ((conf > 0.5) == (ds.loc[conf.index, 'label'] > 0.5)).mean()
    print(f"方向準確率：{acc:.1%}（基準：label 平均 {ds['label'].mean():.1%}）")
    print("\n特徵重要性（全樣本，僅供參考）：")
    print(feature_importance(ds, mlcfg).round(3).to_string())
    print("\n判讀原則：ml_overlay 的 Sharpe 和 MaxDrawdown 要同時優於 baseline 才算贏。")


if __name__ == "__main__":
    main()
