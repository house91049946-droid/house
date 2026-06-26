# -*- coding: utf-8 -*-
"""共用設定:路徑、發文節奏、瀏覽器參數。"""
from pathlib import Path

# === 路徑 ===
BASE_DIR = Path(__file__).resolve().parent
AUTH_DIR = BASE_DIR / "auth"                  # 存登入 session(勿提交 git)
STATE_FILE = AUTH_DIR / "storage_state.json"  # Playwright 登入狀態
DATA_DIR = BASE_DIR / "data"
PHOTOS_DIR = DATA_DIR / "photos"              # 物件照片資料夾
LISTINGS_CSV = DATA_DIR / "listings.csv"      # 物件清單
SHOTS_DIR = BASE_DIR / "screenshots"          # 除錯截圖

for _d in (AUTH_DIR, DATA_DIR, PHOTOS_DIR, SHOTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# === 發文節奏(降低被偵測風險;請保守設定)===
MIN_DELAY_BETWEEN_POSTS = 90    # 每則發文最少間隔(秒)
MAX_DELAY_BETWEEN_POSTS = 180   # 最多間隔(秒)
ACTION_DELAY = (0.8, 2.5)       # 每個動作之間的隨機停頓(秒)

# === 瀏覽器 ===
HEADLESS = False                # 不動產建議用有畫面模式,方便人工過驗證
LOCALE = "zh-TW"
TIMEZONE = "Asia/Taipei"

# Marketplace 建立刊登頁(物件分類在不同地區可能不同,首次請人工確認網址)
MARKETPLACE_CREATE_URL = "https://www.facebook.com/marketplace/create/item"
