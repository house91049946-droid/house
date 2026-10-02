# ETF 動能輪動自動交易（Firstrade）

每月月底收盤後，計算一籃子 ETF 的 3/6/12 個月平均動能，持有最強的 3 檔；
若動能贏不過短債 ETF（BIL）就退守 BIL。一個月交易一次，不受 PDT 當沖限制。

## 安裝

```bash
pip install -r trading/requirements.txt
```

## 回測（先做這步）

```bash
python -m trading.backtest           # 用 yfinance 抓真實 ETF 資料
python -m trading.backtest --proxy   # 抓不到 Yahoo 時，用期貨 / Lean 代理資料（見 data_proxy.py）
```

已跑過的結果和判讀在 `RESULTS.md`。

印出 CAGR、最大回撤、Sharpe、最差月份，並和 SPY 買進持有比較，圖存到 `trading/backtest.png`。
看完回撤覺得能接受再往下走。

## 第 2 層：ML 元標籤（meta-labeling）

不預測價格，預測「這個月的動能訊號會不會贏過 BIL」。
特徵在 `features.py`（波動、回撤、動能廣度、利率與黃金動能、相關性等 12 個），
模型在 `ml.py`，預設邏輯回歸，每年年初用之前所有資料重訓一次，純 walk-forward。
信心低於 0.40 全退守 BIL，0.40 到 0.55 之間按比例減碼。

```bash
python -m trading.backtest_ml [--proxy]              # 邏輯回歸
python -m trading.backtest_ml [--proxy] --model gbm
```

輸出樣本外區間的 baseline 與 ml_overlay 對照。**Sharpe 和 MaxDrawdown 要同時優於 baseline 才算贏**，
沒贏就不要接到實盤，門檻和特徵可在 `ml.py` 的 `MLConfig` 調整。

## 模擬換股（不碰真錢）

```bash
python -m trading.rebalance --broker dry --no-telegram
```

## 實盤

1. 複製 `.env.example` 成 `.env`，填 Firstrade 帳密與 Telegram bot。
2. 確認 Firstrade App 已開啟零股交易。
3. 每月最後一個交易日美股收盤後（台灣時間早上 5 點後）跑：

```bash
python -m trading.rebalance --broker firstrade
```

它會把計畫送到 Telegram，你回 `ok` 才下單，回 `no` 取消。6 小時沒回覆視為取消。

## 排程

cron 範例（每月 1 日台灣時間 06:00，美股前一日已收盤）：

```
0 6 1 * * cd /path/to/house && /usr/bin/python3 -m trading.rebalance --broker firstrade >> trading/logs.txt 2>&1
```

## 風險提醒

- `firstrade` 套件是非官方的，Firstrade 改版會壞；壞了就照 Telegram 收到的計畫手動下單。
- 第一次實盤請只放一部分資金，跑一到兩個月確認流程無誤再加碼。
- 策略在震盪盤會連續小虧，這是動能策略的本質，不是 bug。

## 測試

```bash
python -m pytest trading/tests -q   # 13 個測試
```
