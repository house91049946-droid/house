"""每月換股流程。用法：
    python -m trading.rebalance --broker dry        # 先看它會做什麼
    python -m trading.rebalance --broker firstrade  # 真的執行（預設仍會等你 Telegram 回 ok）
"""
from __future__ import annotations

import argparse
import math
from dataclasses import dataclass

import pandas as pd

from .broker import Broker, Holding, make_broker
from .config import LIVE, STRATEGY, LiveConfig, StrategyConfig


@dataclass
class Trade:
    ticker: str
    side: str
    qty: float
    usd: float


def plan_trades(
    target_w: pd.Series,
    broker: Broker,
    lcfg: LiveConfig = LIVE,
) -> list[Trade]:
    """把目標權重轉成實際買賣清單。先賣後買；低於 min_trade_usd 的差額不動。"""
    nav = broker.account_value()
    investable = nav * (1.0 - lcfg.cash_buffer_pct)
    holdings = broker.holdings()
    tickers = set(target_w.index) | set(holdings)
    trades: list[Trade] = []
    for t in sorted(tickers):
        price = broker.quote(t)
        cur_val = holdings.get(t, Holding(t, 0.0, price)).value
        tgt_val = investable * float(target_w.get(t, 0.0))
        diff = tgt_val - cur_val
        if abs(diff) < lcfg.min_trade_usd:
            continue
        qty = math.floor(abs(diff) / price * 1000) / 1000  # 零股到小數三位
        if qty <= 0:
            continue
        trades.append(Trade(t, "sell" if diff < 0 else "buy", qty, qty * price))
    trades.sort(key=lambda x: 0 if x.side == "sell" else 1)
    return trades


def format_plan(target_w: pd.Series, trades: list[Trade], nav: float) -> str:
    lines = [f"*月度換股計畫*  帳戶淨值 ${nav:,.0f}", "目標權重："]
    for t, w in target_w[target_w > 0].items():
        lines.append(f"  {t}: {w:.0%}")
    lines.append("交易：" if trades else "交易：無，持倉已符合目標")
    for tr in trades:
        lines.append(f"  {tr.side.upper():4} {tr.ticker:4} {tr.qty:.3f} 股  ≈ ${tr.usd:,.0f}")
    return "\n".join(lines)


def execute(trades: list[Trade], broker: Broker) -> list[str]:
    return [broker.market_order(t.ticker, t.qty, t.side) for t in trades]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--broker", choices=["dry", "firstrade"], default="dry")
    ap.add_argument("--no-telegram", action="store_true", help="不送通知，直接印在終端")
    ap.add_argument("--yes", action="store_true", help="跳過確認（危險，確定後再用）")
    args = ap.parse_args()

    from .data import load_prices
    from .strategy import target_weights

    tickers = list(STRATEGY.universe) + [STRATEGY.defensive]
    prices = load_prices(tickers, "2015-01-01")
    asof = prices.index[-1]
    tw = target_weights(prices, asof, STRATEGY)

    if args.broker == "dry":
        broker = make_broker("dry", cash=3000.0, prices={t: float(prices[t].iloc[-1]) for t in tickers})
    else:
        broker = make_broker("firstrade")

    nav = broker.account_value()
    trades = plan_trades(tw, broker)
    text = f"資料截至 {asof.date()}\n" + format_plan(tw, trades, nav)

    if args.no_telegram:
        print(text)
        proceed = args.yes or args.broker == "dry"
    else:
        from . import notify

        notify.send(text + ("\n\n回覆 ok 執行，no 取消" if not args.yes else ""))
        proceed = args.yes or notify.wait_for_reply("ok")

    if not trades:
        return
    if not proceed:
        msg = "未收到確認，本月不交易。"
        print(msg) if args.no_telegram else notify.send(msg)
        return
    ids = execute(trades, broker)
    done = "已送出：\n" + "\n".join(f"  {t.ticker} {t.side} {t.qty:.3f} -> {i}" for t, i in zip(trades, ids))
    print(done) if args.no_telegram else notify.send(done)


if __name__ == "__main__":
    main()
