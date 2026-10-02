"""月底換股的回測。用法：python -m trading.backtest"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import BACKTEST, STRATEGY, BacktestConfig, StrategyConfig
from .strategy import month_end_dates, target_weights


def run_backtest(
    prices: pd.DataFrame,
    scfg: StrategyConfig = STRATEGY,
    bcfg: BacktestConfig = BACKTEST,
) -> tuple[pd.Series, pd.DataFrame]:
    """回傳 (每日淨值序列, 每月目標權重表)。

    模型：月底收盤算訊號，用隔日收盤價換倉（保守，略差於開盤成交）。
    """
    rets = prices.pct_change().fillna(0.0)
    rebal_days = month_end_dates(prices.index)
    weights_log: dict[pd.Timestamp, pd.Series] = {}

    equity = pd.Series(np.nan, index=prices.index)
    cur_w = pd.Series(0.0, index=prices.columns)
    cur_w[scfg.defensive] = 1.0
    nav = bcfg.initial_capital
    pending: pd.Series | None = None
    slip = bcfg.slippage_bps / 1e4

    for i, day in enumerate(prices.index):
        if i > 0:
            nav *= 1.0 + float((cur_w * rets.loc[day]).sum())
        if pending is not None:
            turnover = float((pending - cur_w).abs().sum()) / 2.0
            nav *= 1.0 - turnover * 2 * slip
            cur_w = pending
            pending = None
        equity[day] = nav
        if day in rebal_days:
            tw = target_weights(prices, day, scfg)
            weights_log[day] = tw
            pending = tw.reindex(prices.columns).fillna(0.0)

    return equity.dropna(), pd.DataFrame(weights_log).T


def metrics(equity: pd.Series, benchmark: pd.Series | None = None) -> dict[str, float]:
    r = equity.pct_change().dropna()
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1
    dd = equity / equity.cummax() - 1
    vol = r.std() * np.sqrt(252)
    out = {
        "CAGR": cagr,
        "MaxDrawdown": dd.min(),
        "Vol": vol,
        "Sharpe": (r.mean() * 252) / vol if vol > 0 else float("nan"),
        "WorstMonth": equity.resample("ME").last().pct_change().min(),
        "Years": years,
    }
    if benchmark is not None:
        b = benchmark.reindex(equity.index).ffill()
        out["Benchmark_CAGR"] = (b.iloc[-1] / b.iloc[0]) ** (1 / years) - 1
        out["Benchmark_MaxDD"] = (b / b.cummax() - 1).min()
    return out


def main() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from .data import load_prices

    tickers = list(STRATEGY.universe) + [STRATEGY.defensive]
    prices = load_prices(tickers, BACKTEST.start, BACKTEST.end)
    equity, weights = run_backtest(prices)
    spy = prices["SPY"] / prices["SPY"].loc[equity.index[0]] * BACKTEST.initial_capital
    m = metrics(equity, spy)

    print("\n=== 回測結果 ===")
    for k, v in m.items():
        print(f"{k:>16}: {v:8.2%}" if k != "Years" else f"{k:>16}: {v:8.1f}")
    print("\n最近 6 次目標權重：")
    print(weights.tail(6).round(2).to_string())

    fig, ax = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    ax[0].plot(equity, label="Momentum rotation")
    ax[0].plot(spy, label="SPY buy & hold", alpha=0.7)
    ax[0].set_yscale("log")
    ax[0].legend()
    ax[0].set_title("Equity (log scale)")
    ax[1].plot(equity / equity.cummax() - 1, label="Strategy drawdown")
    ax[1].plot(spy / spy.cummax() - 1, label="SPY drawdown", alpha=0.7)
    ax[1].legend()
    fig.tight_layout()
    fig.savefig("trading/backtest.png", dpi=120)
    print("\n圖存到 trading/backtest.png")


if __name__ == "__main__":
    main()
