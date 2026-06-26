# -*- coding: utf-8 -*-
"""首次登入:開啟瀏覽器讓你手動登入 FB(含 2FA),成功後把 session 存下來。

之後 poster.py 會重複使用這個 session,不用每次重登。

用法:
    python FB/login.py
"""
from playwright.sync_api import sync_playwright

import config


def main():
    print("=" * 50)
    print("開啟瀏覽器,請在視窗中手動登入 Facebook")
    print("(帳號、密碼、兩步驟驗證都在視窗裡完成)")
    print("登入完成、看到首頁後,回到這個終端機按 Enter")
    print("=" * 50)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(locale=config.LOCALE, timezone_id=config.TIMEZONE)
        page = context.new_page()
        page.goto("https://www.facebook.com/", wait_until="domcontentloaded")

        input(">>> 登入完成後,在這裡按 Enter 儲存 session...")

        config.AUTH_DIR.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(config.STATE_FILE))
        print(f"\n✅ session 已儲存到: {config.STATE_FILE}")
        print("以後執行發文就不用再登入了(除非 FB 要求重新驗證)。")
        browser.close()


if __name__ == "__main__":
    main()
