"""用合成價格驗證訊號、回測、下單規劃的邏輯。不需要網路。"""
import numpy as np
import pandas as pd
import pytest

from trading.backtest import metrics, run_backtest
from trading.broker import DryRunBroker, Holding
from trading.config import BacktestConfig, LiveConfig, StrategyConfig
from trading.rebalance import plan_trades
from trading.strategy import month_end_dates, momentum_scores, target_weights

CFG = StrategyConfig(universe=("A", "B", "C"), defensive="CASH", lookbacks_months=(3, 6), top_n=1)


def synth(trends: dict[str, float], days: int = 600, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=days)
    data = {}
    for t, drift in trends.items():
        r = rng.normal(drift / 252, 0.002, days)
        data[t] = 100 * np.cumprod(1 + r)
    return pd.DataFrame(data, index=idx)


def test_month_end_dates_picks_last_trading_day():
    idx = pd.bdate_range("2024-01-01", "2024-03-31")
    me = month_end_dates(idx)
    assert list(me.strftime("%Y-%m-%d")) == ["2024-01-31", "2024-02-29", "2024-03-29"]


def test_picks_strongest_asset_when_it_beats_cash():
    p = synth({"A": 0.30, "B": 0.05, "C": -0.10, "CASH": 0.01})
    w = target_weights(p, p.index[-1], CFG)
    assert w["A"] == pytest.approx(1.0)
    assert w.sum() == pytest.approx(1.0)


def test_goes_defensive_when_everything_is_weak():
    p = synth({"A": -0.20, "B": -0.10, "C": -0.30, "CASH": 0.02})
    w = target_weights(p, p.index[-1], CFG)
    assert w["CASH"] == pytest.approx(1.0)


def test_defensive_when_history_too_short():
    p = synth({"A": 0.3, "B": 0.1, "C": 0.0, "CASH": 0.0}, days=50)
    w = target_weights(p, p.index[-1], CFG)
    assert w["CASH"] == pytest.approx(1.0)
    assert momentum_scores(p, p.index[-1], CFG).isna().all()


def test_backtest_runs_and_metrics_sane():
    p = synth({"A": 0.15, "B": 0.05, "C": -0.05, "CASH": 0.01}, days=800)
    eq, w = run_backtest(p, CFG, BacktestConfig(initial_capital=1000.0))
    assert eq.iloc[0] == pytest.approx(1000.0)
    assert (w.sum(axis=1) - 1).abs().max() < 1e-9
    m = metrics(eq)
    assert -1 < m["MaxDrawdown"] <= 0
    assert m["CAGR"] > -0.5


def test_plan_trades_sells_before_buys_and_skips_dust():
    broker = DryRunBroker(
        cash=100.0,
        holdings={"B": Holding("B", 10, 100.0), "A": Holding("A", 0.1, 50.0)},
        prices={"A": 50.0, "B": 100.0, "CASH": 10.0},
    )
    tw = pd.Series({"A": 1.0, "B": 0.0, "CASH": 0.0})
    trades = plan_trades(tw, broker, LiveConfig(cash_buffer_pct=0.0, min_trade_usd=25.0))
    assert [t.side for t in trades] == ["sell", "buy"]
    assert trades[0].ticker == "B" and trades[0].qty == pytest.approx(10.0)
    assert trades[1].ticker == "A"
    # 淨值 1105，目標全壓 A，現有 A 價值 5，差 1100 → 22 股
    assert trades[1].qty == pytest.approx(22.0)
