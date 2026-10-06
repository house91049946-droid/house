# 💡 Idea 資料庫

平常看到**有趣的功能、影片、文章**,把連結和自己的想法丟進來收集,之後用**標籤、類型、關鍵字**調閱。
資料存在本機 SQLite(`Idea/data/ideas.db`),核心只用 Python 標準函式庫,不需要額外安裝套件。

## 每筆資料記什麼
| 欄位 | 說明 |
|------|------|
| 標題 | 一句話說這是什麼 |
| 來源連結 | 影片 / 文章 / 產品頁網址,可空 |
| 類型 | 🧩 功能、🎬 影片、📄 文章、📌 其他(不填會從網址猜:YouTube 等 → 影片,其他網址 → 文章,沒網址 → 功能) |
| 我的想法 | 為什麼有趣、想怎麼用 |
| 標籤 | 逗號分隔,方便之後分類調閱 |
| 狀態 / 優先度 | 💡 點子 → 🚧 進行中 → ✅ 完成 / 🗑️ 放棄,優先度 1~5(預設 3,不用特別管) |

## 功能
- ➕ 收藏:貼網址 + 寫想法 + 標籤,幾秒內完成
- 🔍 調閱:依類型、狀態、標籤、關鍵字(標題 / 想法 / 網址 / 標籤)篩選
- 📤 匯出 JSON / CSV
- 兩種介面:命令列(`cli.py`)與網頁(`app.py`,Gradio)

## 命令列用法
```bash
python Idea/cli.py add "拖曳排序的看板 UI" -u https://youtu.be/xxxx -c "想用在待辦 App" -t ui,app
python Idea/cli.py add "一鍵把網頁存成 Markdown" -k feature -t tool
python Idea/cli.py list                       # 全部列出
python Idea/cli.py list --kind video          # 只看影片
python Idea/cli.py list --status doing        # 只看進行中
python Idea/cli.py list --tag app --order priority
python Idea/cli.py search 看板                # 關鍵字搜尋
python Idea/cli.py show 1                     # 看詳情(含連結)
python Idea/cli.py edit 1 -s doing -p 5       # 修改欄位(-u 改連結、-k 改類型)
python Idea/cli.py done 1                     # 快速標記完成(另有 doing / drop)
python Idea/cli.py rm 1                       # 刪除
python Idea/cli.py tags                       # 所有標籤
python Idea/cli.py stats                      # 各狀態數量
python Idea/cli.py export ideas.json          # 或 ideas.csv
```
用 `--db 路徑` 或環境變數 `IDEA_DB_PATH` 可以指定不同的資料庫檔案。

## 網頁介面
```bash
uv sync            # 專案根目錄,安裝 gradio
uv run Idea/app.py
```
開啟 http://127.0.0.1:7860
- 左側貼連結、寫想法收藏,右側列表可依類型 / 狀態 / 標籤 / 關鍵字篩選
- 點列表任一列,下方編輯區會載入該點子,可修改或刪除
- 最下方可匯出 JSON / CSV

## 在程式裡使用
```python
from Idea.db import IdeaDB

with IdeaDB() as db:
    idea = db.add("點子標題", "我的想法", tags="a,b", url="https://youtu.be/xxxx")  # kind 自動判為 video
    db.set_status(idea.id, "doing")
    for i in db.list(query="標題"):
        print(i.id, i.title, i.tags)
```

## 檔案
| 檔案 | 用途 |
|------|------|
| `db.py` | SQLite 存取核心(新增 / 查詢 / 更新 / 刪除 / 匯出) |
| `cli.py` | 命令列工具 |
| `app.py` | Gradio 網頁介面 |
| `test_db.py` | 核心邏輯測試(`python -m unittest Idea/test_db.py`) |
| `data/ideas.db` | 你的資料(已在 `.gitignore`,不會提交) |
