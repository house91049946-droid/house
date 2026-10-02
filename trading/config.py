"""ETF 動能輪動策略設定。改這裡，不要改策略程式。"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class StrategyConfig:
    # 候選籃子：美股、小型股、已開發、新興、長債、黃金
    universe: tuple[str, ...] = ("SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "GLD")
    # 動能為負時退守的資產（短期國庫券 ETF）
    defensive: str = "BIL"
    # 動能計算視窗（月），多視窗平均可以降低單一視窗的運氣成分
    lookbacks_months: tuple[int, ...] = (3, 6, 12)
    # 每月持有幾檔
    top_n: int = 2
    # 絕對動能門檻：候選資產的動能必須高於這個值才持有，否則該額度退守 defensive
    # 設成 defensive 的動能表示「要贏過現金才持有」（雙動能的作法）
    use_defensive_as_threshold: bool = True
    # 每月第幾個交易日執行（0 = 月底最後一個交易日收盤後算、下月第一個交易日開盤買）
    # 目前只支援月底
    rebalance: str = "month_end"


@dataclass(frozen=True)
class BacktestConfig:
    start: str = "2007-01-01"
    end: str | None = None
    initial_capital: float = 3000.0  # 美金，約十萬台幣
    # 零手續費券商，但保留滑價假設（單邊 0.05%）
    slippage_bps: float = 5.0


@dataclass(frozen=True)
class LiveConfig:
    # 下單前要你在 Telegram 回覆確認；設 False 才是全自動
    require_confirmation: bool = True
    # 現金保留比例，避免零股下單因價格跳動失敗
    cash_buffer_pct: float = 0.02
    # 單檔權重和目標差距小於此值就不動，避免每月為了幾塊錢來回交易
    min_trade_usd: float = 25.0
    # 風控：任一時刻帳戶淨值低於初始資金的這個比例，停止一切買單並通知
    kill_switch_drawdown: float = 0.30


STRATEGY = StrategyConfig()
BACKTEST = BacktestConfig()
LIVE = LiveConfig()
