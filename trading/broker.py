"""券商抽象層。DryRunBroker 只印不下單；FirstradeBroker 包非官方 firstrade 套件。

注意：firstrade 套件是社群模擬網頁登入，Firstrade 改版就可能壞，
而且技術上不符其使用條款。第一版請保持 require_confirmation=True。
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Holding:
    ticker: str
    quantity: float
    price: float

    @property
    def value(self) -> float:
        return self.quantity * self.price


class Broker:
    def account_value(self) -> float: ...
    def cash(self) -> float: ...
    def holdings(self) -> dict[str, Holding]: ...
    def quote(self, ticker: str) -> float: ...
    def market_order(self, ticker: str, qty: float, side: str) -> str: ...


class DryRunBroker(Broker):
    """用假持倉跑完整流程，不碰任何真錢。"""

    def __init__(self, cash: float, holdings: dict[str, Holding] | None = None, prices: dict[str, float] | None = None):
        self._cash = cash
        self._h = holdings or {}
        self._p = prices or {}
        self.orders: list[tuple[str, float, str]] = []

    def account_value(self) -> float:
        return self._cash + sum(h.value for h in self._h.values())

    def cash(self) -> float:
        return self._cash

    def holdings(self) -> dict[str, Holding]:
        return dict(self._h)

    def quote(self, ticker: str) -> float:
        if ticker in self._p:
            return self._p[ticker]
        if ticker in self._h:
            return self._h[ticker].price
        raise KeyError(ticker)

    def market_order(self, ticker: str, qty: float, side: str) -> str:
        self.orders.append((ticker, qty, side))
        px = self.quote(ticker)
        if side == "buy":
            self._cash -= qty * px
            h = self._h.get(ticker, Holding(ticker, 0.0, px))
            self._h[ticker] = Holding(ticker, h.quantity + qty, px)
        else:
            self._cash += qty * px
            h = self._h[ticker]
            self._h[ticker] = Holding(ticker, h.quantity - qty, px)
        return f"DRY-{len(self.orders)}"


class FirstradeBroker(Broker):
    """環境變數：FT_USERNAME、FT_PASSWORD、FT_PIN（或 FT_EMAIL/FT_PHONE 做 2FA）。"""

    def __init__(self) -> None:
        from firstrade import account, order, symbols  # noqa: WPS433

        self._order_mod = order
        self._symbols_mod = symbols
        self._ft = account.FTSession(
            username=os.environ["FT_USERNAME"],
            password=os.environ["FT_PASSWORD"],
            pin=os.getenv("FT_PIN"),
            email=os.getenv("FT_EMAIL"),
            phone=os.getenv("FT_PHONE"),
        )
        self._ft.login()
        self._data = account.FTAccountData(self._ft)
        self._acct = self._data.account_numbers[0]

    def _balances(self) -> dict:
        return self._data.get_account_balances(self._acct)

    def account_value(self) -> float:
        return float(self._balances()["total_value"])

    def cash(self) -> float:
        return float(self._balances()["cash_available"])

    def holdings(self) -> dict[str, Holding]:
        out: dict[str, Holding] = {}
        for p in self._data.get_positions(self._acct).get("items", []):
            out[p["symbol"]] = Holding(p["symbol"], float(p["quantity"]), float(p["last_price"]))
        return out

    def quote(self, ticker: str) -> float:
        q = self._symbols_mod.SymbolQuote(self._ft, self._acct, ticker)
        return float(q.last)

    def market_order(self, ticker: str, qty: float, side: str) -> str:
        o = self._order_mod.Order(self._ft)
        res = o.place_order(
            account=self._acct,
            symbol=ticker,
            price_type=self._order_mod.PriceType.MARKET,
            order_type=self._order_mod.OrderType.BUY if side == "buy" else self._order_mod.OrderType.SELL,
            quantity=qty,
            duration=self._order_mod.Duration.DAY,
            dry_run=False,
            notional=False,
        )
        return str(res.get("order_id", res))


def make_broker(name: str, **kw) -> Broker:
    if name == "dry":
        return DryRunBroker(**kw)
    if name == "firstrade":
        return FirstradeBroker()
    raise ValueError(name)
