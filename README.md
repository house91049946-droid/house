---
title: 食物熱量估算器
emoji: 🍔
colorFrom: yellow
colorTo: red
sdk: gradio
sdk_version: 6.19.0
app_file: app.py
pinned: false
---

# 🍔 食物熱量估算器 (Food Calorie Estimator)

上傳一張食物照片，使用 Google Gemini 視覺模型估算大概的熱量。
如果照片中不是食物，會回應「這不是食物」。

## 功能
- 📷 上傳圖片 → AI 判斷是否為食物
- 🔥 是食物：估算總熱量 (kcal)、份量假設與說明
- 🚫 不是食物：回應「這不是食物」

## 在 Hugging Face Space 部署
1. 建立一個 **Gradio** SDK 的 Space。
2. 上傳 `app.py`、`requirements.txt`、`README.md`。
3. 到 **Settings → Variables and secrets**，新增一個 **Secret**：
   - Name: `GOOGLE_API_KEY`
   - Value: 你的 Google Gemini API Key
4.（選用）新增變數 `GEMINI_MODEL` 來指定模型，預設為 `gemini-2.5-flash`。

## 本機開發（使用 uv，不污染本機環境）
```bash
# 安裝依賴到 .venv
uv sync

# 設定 API Key 並啟動
export GOOGLE_API_KEY="你的_API_Key"
uv run app.py
```
開啟瀏覽器到 http://127.0.0.1:7860

## 取得 Google Gemini API Key
到 [Google AI Studio](https://aistudio.google.com/apikey) 建立 API Key。
