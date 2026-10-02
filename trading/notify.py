"""Telegram 通知與確認。環境變數 TELEGRAM_BOT_TOKEN、TELEGRAM_CHAT_ID。"""
from __future__ import annotations

import os
import time

import requests

API = "https://api.telegram.org/bot{token}/{method}"


def _cfg() -> tuple[str, str]:
    tok, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        raise RuntimeError("缺少 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")
    return tok, chat


def send(text: str) -> None:
    tok, chat = _cfg()
    requests.post(
        API.format(token=tok, method="sendMessage"),
        json={"chat_id": chat, "text": text, "parse_mode": "Markdown"},
        timeout=20,
    ).raise_for_status()


def wait_for_reply(keyword: str = "ok", timeout_sec: int = 6 * 3600) -> bool:
    """等你在 Telegram 回覆 keyword。逾時回 False。"""
    tok, chat = _cfg()
    offset = None
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        r = requests.get(
            API.format(token=tok, method="getUpdates"),
            params={"timeout": 30, "offset": offset},
            timeout=40,
        ).json()
        for u in r.get("result", []):
            offset = u["update_id"] + 1
            msg = u.get("message", {})
            if str(msg.get("chat", {}).get("id")) == str(chat):
                text = (msg.get("text") or "").strip().lower()
                if text == keyword:
                    return True
                if text in ("no", "cancel", "取消"):
                    return False
    return False
