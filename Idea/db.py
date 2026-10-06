# -*- coding: utf-8 -*-
"""Idea 資料庫核心:用 SQLite 收集「看到有趣的功能 / 影片」,方便日後調閱。

只依賴 Python 標準函式庫,CLI 與 Gradio UI 都共用這個模組。

資料表 ideas 欄位:
- id          自動編號
- title       標題(必填)
- content     我的想法 / 備註(為什麼有趣、想怎麼做)
- url         來源連結(影片 / 文章 / 產品頁),可空
- kind        類型:feature / video / article / other
- tags        標籤,以逗號分隔儲存(例如 "app,side-project")
- status      狀態:idea / doing / done / dropped
- priority    優先度 1(低)~5(高),預設 3
- created_at  建立時間(ISO 8601)
- updated_at  最後更新時間(ISO 8601)
"""

from __future__ import annotations

import csv
import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = Path(os.environ.get("IDEA_DB_PATH", BASE_DIR / "data" / "ideas.db"))

KINDS = ("feature", "video", "article", "other")
KIND_LABELS = {
    "feature": "🧩 功能",
    "video": "🎬 影片",
    "article": "📄 文章",
    "other": "📌 其他",
}

STATUSES = ("idea", "doing", "done", "dropped")
STATUS_LABELS = {
    "idea": "💡 點子",
    "doing": "🚧 進行中",
    "done": "✅ 完成",
    "dropped": "🗑️ 放棄",
}


@dataclass
class Idea:
    id: int
    title: str
    content: str
    url: str
    kind: str
    tags: list[str]
    status: str
    priority: int
    created_at: str
    updated_at: str

    def to_dict(self) -> dict:
        return asdict(self)


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def normalize_tags(tags: str | Iterable[str] | None) -> list[str]:
    """把 "a, b ,c" 或 ["a","b"] 整理成去重、去空白、小寫的 list。"""
    if tags is None:
        return []
    if isinstance(tags, str):
        parts = tags.replace("，", ",").split(",")
    else:
        parts = list(tags)
    seen: list[str] = []
    for p in parts:
        t = p.strip().lower()
        if t and t not in seen:
            seen.append(t)
    return seen


VIDEO_HOSTS = ("youtube.com", "youtu.be", "bilibili.com", "vimeo.com", "tiktok.com", "instagram.com/reel")


def guess_kind(url: str) -> str:
    """沒指定類型時,從網址猜:影片網站 → video,其他有網址 → article,沒網址 → feature。"""
    u = (url or "").strip().lower()
    if not u:
        return "feature"
    if any(h in u for h in VIDEO_HOSTS):
        return "video"
    return "article"


def _row_to_idea(row: sqlite3.Row) -> Idea:
    return Idea(
        id=row["id"],
        title=row["title"],
        content=row["content"],
        url=row["url"],
        kind=row["kind"],
        tags=normalize_tags(row["tags"]),
        status=row["status"],
        priority=row["priority"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class IdeaDB:
    """簡單的 SQLite 包裝。可當 context manager 使用。"""

    def __init__(self, path: str | os.PathLike = DEFAULT_DB_PATH):
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    # ---- 基礎 ----
    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS ideas (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT NOT NULL,
                content    TEXT NOT NULL DEFAULT '',
                url        TEXT NOT NULL DEFAULT '',
                kind       TEXT NOT NULL DEFAULT 'other',
                tags       TEXT NOT NULL DEFAULT '',
                status     TEXT NOT NULL DEFAULT 'idea',
                priority   INTEGER NOT NULL DEFAULT 3,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ideas_status ON ideas(status);
            """
        )
        self.conn.commit()
        # 舊版資料庫沒有 url / kind 欄位時自動補上
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(ideas)")}
        if "url" not in cols:
            self.conn.execute("ALTER TABLE ideas ADD COLUMN url TEXT NOT NULL DEFAULT ''")
        if "kind" not in cols:
            self.conn.execute("ALTER TABLE ideas ADD COLUMN kind TEXT NOT NULL DEFAULT 'other'")
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "IdeaDB":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---- 新增 / 讀取 ----
    def add(
        self,
        title: str,
        content: str = "",
        tags: str | Iterable[str] | None = None,
        status: str = "idea",
        priority: int = 3,
        url: str = "",
        kind: str | None = None,
    ) -> Idea:
        title = title.strip()
        if not title:
            raise ValueError("標題不可為空")
        if status not in STATUSES:
            raise ValueError(f"status 必須是 {STATUSES} 其中之一")
        priority = int(priority)
        if not 1 <= priority <= 5:
            raise ValueError("priority 必須在 1~5 之間")
        url = (url or "").strip()
        if kind is None:
            kind = guess_kind(url)
        if kind not in KINDS:
            raise ValueError(f"kind 必須是 {KINDS} 其中之一")
        now = _now()
        cur = self.conn.execute(
            "INSERT INTO ideas (title, content, url, kind, tags, status, priority, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (title, content.strip(), url, kind, ",".join(normalize_tags(tags)), status, priority, now, now),
        )
        self.conn.commit()
        return self.get(cur.lastrowid)

    def get(self, idea_id: int) -> Idea:
        row = self.conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone()
        if row is None:
            raise KeyError(f"找不到 id={idea_id} 的點子")
        return _row_to_idea(row)

    def list(
        self,
        status: str | None = None,
        tag: str | None = None,
        query: str | None = None,
        kind: str | None = None,
        order: str = "updated",
    ) -> list[Idea]:
        """列出點子。可依狀態、類型、標籤、關鍵字(標題 / 內容 / 網址 / 標籤)過濾。"""
        where: list[str] = []
        params: list = []
        if status:
            where.append("status = ?")
            params.append(status)
        if kind:
            where.append("kind = ?")
            params.append(kind)
        if query:
            like = f"%{query.strip()}%"
            where.append("(title LIKE ? OR content LIKE ? OR url LIKE ? OR tags LIKE ?)")
            params += [like, like, like, like]
        order_sql = {
            "updated": "updated_at DESC",
            "created": "created_at DESC",
            "priority": "priority DESC, updated_at DESC",
            "id": "id ASC",
        }.get(order, "updated_at DESC")
        sql = "SELECT * FROM ideas"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += f" ORDER BY {order_sql}"
        ideas = [_row_to_idea(r) for r in self.conn.execute(sql, params)]
        if tag:
            t = tag.strip().lower()
            ideas = [i for i in ideas if t in i.tags]
        return ideas

    def all_tags(self) -> list[str]:
        """回傳目前所有用過的標籤(依使用次數排序)。"""
        counts: dict[str, int] = {}
        for row in self.conn.execute("SELECT tags FROM ideas"):
            for t in normalize_tags(row["tags"]):
                counts[t] = counts.get(t, 0) + 1
        return sorted(counts, key=lambda t: (-counts[t], t))

    def stats(self) -> dict[str, int]:
        result = {s: 0 for s in STATUSES}
        for row in self.conn.execute("SELECT status, COUNT(*) AS n FROM ideas GROUP BY status"):
            result[row["status"]] = row["n"]
        result["total"] = sum(result[s] for s in STATUSES)
        return result

    # ---- 更新 / 刪除 ----
    def update(self, idea_id: int, **fields) -> Idea:
        """更新指定欄位:title / content / url / kind / tags / status / priority。"""
        allowed = {"title", "content", "url", "kind", "tags", "status", "priority"}
        bad = set(fields) - allowed
        if bad:
            raise ValueError(f"不支援的欄位:{sorted(bad)}")
        self.get(idea_id)  # 不存在會丟 KeyError
        sets: list[str] = []
        params: list = []
        for key, value in fields.items():
            if key == "tags":
                value = ",".join(normalize_tags(value))
            elif key == "status":
                if value not in STATUSES:
                    raise ValueError(f"status 必須是 {STATUSES} 其中之一")
            elif key == "priority":
                value = int(value)
                if not 1 <= value <= 5:
                    raise ValueError("priority 必須在 1~5 之間")
            elif key == "title":
                value = str(value).strip()
                if not value:
                    raise ValueError("標題不可為空")
            elif key == "kind":
                if value not in KINDS:
                    raise ValueError(f"kind 必須是 {KINDS} 其中之一")
            elif key in ("content", "url"):
                value = str(value or "").strip()
            sets.append(f"{key} = ?")
            params.append(value)
        if sets:
            sets.append("updated_at = ?")
            params.append(_now())
            params.append(idea_id)
            self.conn.execute(f"UPDATE ideas SET {', '.join(sets)} WHERE id = ?", params)
            self.conn.commit()
        return self.get(idea_id)

    def set_status(self, idea_id: int, status: str) -> Idea:
        return self.update(idea_id, status=status)

    def delete(self, idea_id: int) -> None:
        self.get(idea_id)
        self.conn.execute("DELETE FROM ideas WHERE id = ?", (idea_id,))
        self.conn.commit()

    # ---- 匯出 ----
    def export_json(self, path: str | os.PathLike) -> int:
        ideas = [i.to_dict() for i in self.list(order="id")]
        Path(path).write_text(json.dumps(ideas, ensure_ascii=False, indent=2), encoding="utf-8")
        return len(ideas)

    def export_csv(self, path: str | os.PathLike) -> int:
        ideas = self.list(order="id")
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["id", "title", "content", "url", "kind", "tags", "status", "priority", "created_at", "updated_at"]
            )
            for i in ideas:
                writer.writerow(
                    [i.id, i.title, i.content, i.url, i.kind, ",".join(i.tags),
                     i.status, i.priority, i.created_at, i.updated_at]
                )
        return len(ideas)
