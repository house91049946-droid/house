# FB Marketplace 不動產自動發文(RPA)

用 Playwright 自動把不動產物件發到 Facebook Marketplace。

## ⚠️ 風險與限制
- Marketplace 沒有官方 API,自動化發文**違反 Facebook 使用條款**,帳號有被限制/封鎖的風險。
- 請用**自己的帳號**、**保守的發文頻率**、量不要大。
- FB 前端常改版,`poster.py` 裡的 selector 需要不定期對照實際畫面微調。
- 不動產分類在不同地區規則不同,首次請確認你所在地 Marketplace 有「房地產出售」分類。

## 安裝
```bash
uv pip install playwright pandas
playwright install chromium
```

## 使用步驟
1. **登入並儲存 session(只需一次)**
   ```bash
   python FB/login.py
   ```
   在彈出的瀏覽器手動登入(含兩步驟驗證),回終端機按 Enter。

2. **準備物件資料**
   - 複製 `data/listings_sample.csv` → `data/listings.csv`,填入你的物件。
   - 照片放進 `data/photos/`,在 CSV 的 `photos` 欄填檔名,多張用 `;` 分隔。

3. **先空跑測試(不送出)**
   ```bash
   python FB/poster.py --dry-run
   ```
   它會開啟表單、填好欄位但不送出,並在 `screenshots/` 留截圖。
   對照截圖,調整 `poster.py` 裡分類/地點/送出按鈕的 selector。

4. **正式發文**
   ```bash
   python FB/poster.py
   ```

## 檔案
| 檔案 | 用途 |
|------|------|
| `config.py` | 路徑、發文節奏、瀏覽器設定 |
| `login.py` | 首次登入並儲存 session |
| `poster.py` | 讀 CSV 逐筆發文(核心) |
| `data/listings_sample.csv` | 物件資料範本 |

> `auth/`(登入憑證)、`screenshots/`、真實 `listings.csv` 與照片都已在 `.gitignore`,不會被提交。
