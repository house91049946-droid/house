# -*- coding: utf-8 -*-
"""發文核心:讀取物件清單,逐筆到 Marketplace 建立刊登。

⚠️ 重要:Marketplace 的表單欄位、按鈕文字會隨 FB 改版而變,
   下面的 selector 需要你第一次跑時對照實際畫面微調。
   每一步都有截圖,失敗時看 screenshots/ 資料夾除錯。

用法:
    python FB/poster.py            # 讀 data/listings.csv 全部發文
    python FB/poster.py --dry-run  # 只開到表單、不送出(測試用)
"""
import argparse
import random
import time
from datetime import datetime

import pandas as pd
from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout

import config


def human_pause(rng=config.ACTION_DELAY):
    """模擬真人的隨機停頓。"""
    time.sleep(random.uniform(*rng))


def shot(page: Page, name: str):
    """除錯截圖。"""
    ts = datetime.now().strftime("%H%M%S")
    path = config.SHOTS_DIR / f"{ts}_{name}.png"
    try:
        page.screenshot(path=str(path))
        print(f"   📸 {path.name}")
    except Exception as e:
        print(f"   (截圖失敗: {e})")


def load_listings() -> pd.DataFrame:
    if not config.LISTINGS_CSV.exists():
        raise FileNotFoundError(
            f"找不到物件清單: {config.LISTINGS_CSV}\n"
            f"請先複製 data/listings_sample.csv 成 listings.csv 並填入資料。"
        )
    df = pd.read_csv(config.LISTINGS_CSV, dtype=str).fillna("")
    print(f"讀到 {len(df)} 筆物件。")
    return df


def post_one(page: Page, row: pd.Series, dry_run: bool):
    """發布單一物件。selector 採多重備援,FB 改版時較不易整個壞掉。"""
    print(f"\n▶ 發布: {row.get('title', '(無標題)')}")
    page.goto(config.MARKETPLACE_CREATE_URL, wait_until="domcontentloaded")
    human_pause((2, 4))
    shot(page, "01_create_page")

    # --- 上傳照片 ---
    photos = [p.strip() for p in str(row.get("photos", "")).split(";") if p.strip()]
    photo_paths = [str(config.PHOTOS_DIR / p) for p in photos]
    if photo_paths:
        try:
            file_input = page.locator('input[type="file"][accept*="image"]').first
            file_input.set_input_files(photo_paths, timeout=15000)
            human_pause((2, 4))
            print(f"   ✅ 上傳 {len(photo_paths)} 張照片")
        except PWTimeout:
            print("   ⚠️ 找不到照片上傳欄位(selector 需調整)")
            shot(page, "02_photo_fail")

    # --- 文字欄位:用 placeholder / label 多重定位 ---
    fields = {
        "title": ["標題", "Title"],
        "price": ["價格", "Price"],
        "description": ["說明", "描述", "Description"],
    }
    for key, labels in fields.items():
        value = str(row.get(key, "")).strip()
        if not value:
            continue
        filled = _fill_by_labels(page, labels, value)
        print(f"   {'✅' if filled else '⚠️'} {key}: {value[:30]}")
        human_pause()

    shot(page, "03_filled")
    print("   ⏳ 分類、地點、物件狀況等下拉選單,首次需人工對照畫面補上 selector。")

    if dry_run:
        print("   🧪 dry-run:停在表單,不送出。")
        return False

    # --- 送出(實際按鈕文字請第一次跑時確認)---
    submitted = _click_by_text(page, ["發布", "Publish", "下一步", "Next"])
    shot(page, "04_after_submit")
    if submitted:
        print("   ✅ 已點送出")
    else:
        print("   ⚠️ 找不到送出按鈕(selector 需調整)")
    return submitted


def _fill_by_labels(page: Page, labels, value) -> bool:
    for lab in labels:
        for sel in (
            f'input[aria-label*="{lab}"]',
            f'textarea[aria-label*="{lab}"]',
            f'input[placeholder*="{lab}"]',
            f'textarea[placeholder*="{lab}"]',
        ):
            loc = page.locator(sel).first
            try:
                if loc.count() > 0:
                    loc.click()
                    loc.fill(value)
                    return True
            except Exception:
                continue
    return False


def _click_by_text(page: Page, texts) -> bool:
    for t in texts:
        loc = page.get_by_role("button", name=t)
        try:
            if loc.count() > 0:
                loc.first.click()
                return True
        except Exception:
            continue
    return False


def run(dry_run: bool = False):
    if not config.STATE_FILE.exists():
        raise FileNotFoundError("尚未登入。請先執行: python FB/login.py")

    df = load_listings()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=config.HEADLESS)
        context = browser.new_context(
            storage_state=str(config.STATE_FILE),
            locale=config.LOCALE,
            timezone_id=config.TIMEZONE,
        )
        page = context.new_page()

        ok = 0
        for i, (_, row) in enumerate(df.iterrows(), 1):
            try:
                if post_one(page, row, dry_run):
                    ok += 1
            except Exception as e:
                print(f"   ❌ 發布失敗: {e}")
                shot(page, f"error_{i}")

            if i < len(df) and not dry_run:
                wait = random.uniform(
                    config.MIN_DELAY_BETWEEN_POSTS, config.MAX_DELAY_BETWEEN_POSTS
                )
                print(f"   ⏸ 等待 {wait:.0f} 秒再發下一則(避免被偵測)...")
                time.sleep(wait)

        print(f"\n完成。成功 {ok}/{len(df)} 則。")
        browser.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只開到表單不送出")
    args = ap.parse_args()
    run(dry_run=args.dry_run)
