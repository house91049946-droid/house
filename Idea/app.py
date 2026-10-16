# -*- coding: utf-8 -*-
"""Idea 資料庫 Gradio 介面。

啟動:
    uv run Idea/app.py
或  python Idea/app.py

資料存在 Idea/data/ideas.db(可用環境變數 IDEA_DB_PATH 改路徑)。
"""

from __future__ import annotations

import sys
from pathlib import Path

import gradio as gr

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import DEFAULT_DB_PATH, KIND_LABELS, KINDS, STATUS_LABELS, STATUSES, IdeaDB  # noqa: E402

STATUS_CHOICES = [(STATUS_LABELS[s], s) for s in STATUSES]
FILTER_CHOICES = [("全部", "")] + STATUS_CHOICES
KIND_CHOICES = [("自動判斷", "")] + [(KIND_LABELS[k], k) for k in KINDS]
KIND_EDIT_CHOICES = [(KIND_LABELS[k], k) for k in KINDS]
KIND_FILTER_CHOICES = [("全部", "")] + KIND_EDIT_CHOICES
HEADERS = ["ID", "類型", "狀態", "優先度", "標題", "標籤", "連結", "更新時間"]


def _db() -> IdeaDB:
    # 每次操作開一個連線,避免 Gradio 多執行緒共用 sqlite 連線出錯
    return IdeaDB(DEFAULT_DB_PATH)


def _table(status: str, tag: str, query: str, kind: str = "") -> list[list]:
    with _db() as db:
        ideas = db.list(
            status=status or None, tag=tag or None, query=query or None, kind=kind or None, order="updated"
        )
    return [
        [i.id, KIND_LABELS[i.kind], STATUS_LABELS[i.status], "★" * i.priority,
         i.title, ", ".join(i.tags), i.url, i.updated_at]
        for i in ideas
    ]


def _stats_md() -> str:
    with _db() as db:
        st = db.stats()
    parts = [f"{STATUS_LABELS[s]} {st[s]}" for s in STATUSES]
    return f"**總計 {st['total']}** ｜ " + " ｜ ".join(parts)


def _tag_choices() -> list[str]:
    with _db() as db:
        return [""] + db.all_tags()


def refresh(status: str, tag: str, query: str, kind: str):
    return _table(status, tag, query, kind), _stats_md(), gr.update(choices=_tag_choices(), value=tag)


def add_idea(title, url, kind, content, tags, priority, status, f_status, f_tag, f_query, f_kind):
    try:
        with _db() as db:
            i = db.add(title, content, tags, status, priority, url=url, kind=kind or None)
    except ValueError as exc:
        raise gr.Error(str(exc))
    gr.Info(f"已收藏 #{i.id}:{i.title}")
    return ("", "", "", "", "", 3, "idea") + refresh(f_status, f_tag, f_query, f_kind)


def load_idea(evt: gr.SelectData, table: list[list]):
    """點表格某列 → 載入到編輯區。"""
    row = table[evt.index[0]]
    with _db() as db:
        i = db.get(int(row[0]))
    link = f"🔗 [{i.url}]({i.url})" if i.url else ""
    return i.id, i.title, i.url, i.kind, i.content, ", ".join(i.tags), i.priority, i.status, link


def save_idea(idea_id, title, url, kind, content, tags, priority, status, f_status, f_tag, f_query, f_kind):
    if not idea_id:
        raise gr.Error("請先在列表點選一個點子")
    try:
        with _db() as db:
            db.update(int(idea_id), title=title, url=url, kind=kind, content=content,
                      tags=tags, priority=priority, status=status)
    except (KeyError, ValueError) as exc:
        raise gr.Error(exc.args[0] if exc.args else str(exc))
    gr.Info(f"已儲存 #{int(idea_id)}")
    return refresh(f_status, f_tag, f_query, f_kind)


def delete_idea(idea_id, f_status, f_tag, f_query, f_kind):
    if not idea_id:
        raise gr.Error("請先在列表點選一個點子")
    try:
        with _db() as db:
            db.delete(int(idea_id))
    except KeyError as exc:
        raise gr.Error(exc.args[0] if exc.args else str(exc))
    gr.Info(f"已刪除 #{int(idea_id)}")
    return (None, "", "", "other", "", "", 3, "idea", "") + refresh(f_status, f_tag, f_query, f_kind)


def export_file(fmt: str) -> str:
    out = DEFAULT_DB_PATH.parent / f"ideas_export.{fmt}"
    with _db() as db:
        if fmt == "csv":
            db.export_csv(out)
        else:
            db.export_json(out)
    return str(out)


with gr.Blocks(title="Idea 資料庫") as demo:
    gr.Markdown("# 💡 Idea 資料庫\n看到有趣的功能或影片就丟進來,寫下想法,之後用標籤 / 關鍵字調閱。")
    stats = gr.Markdown(_stats_md())

    with gr.Row():
        # ---- 左:新增 ----
        with gr.Column(scale=1):
            gr.Markdown("### ➕ 收藏一個點子")
            n_title = gr.Textbox(label="標題", placeholder="例如:拖曳排序的看板 UI")
            n_url = gr.Textbox(label="來源連結(影片 / 文章 / 產品頁)", placeholder="https://...")
            n_kind = gr.Dropdown(KIND_CHOICES, value="", label="類型(不選會從網址猜)")
            n_content = gr.Textbox(label="我的想法 / 備註", lines=4, placeholder="為什麼有趣?想怎麼用?")
            n_tags = gr.Textbox(label="標籤(逗號分隔)", placeholder="ui, app")
            n_priority = gr.Slider(1, 5, value=3, step=1, label="優先度")
            n_status = gr.Dropdown(STATUS_CHOICES, value="idea", label="狀態")
            n_btn = gr.Button("收藏", variant="primary")

        # ---- 右:列表 ----
        with gr.Column(scale=2):
            gr.Markdown("### 📋 點子列表(點一列可編輯)")
            with gr.Row():
                f_kind = gr.Dropdown(KIND_FILTER_CHOICES, value="", label="類型")
                f_status = gr.Dropdown(FILTER_CHOICES, value="", label="狀態")
                f_tag = gr.Dropdown(_tag_choices(), value="", label="標籤", allow_custom_value=True)
                f_query = gr.Textbox(label="關鍵字", placeholder="搜尋標題 / 想法 / 網址 / 標籤")
            table = gr.Dataframe(
                headers=HEADERS,
                value=_table("", "", ""),
                interactive=False,
                wrap=True,
            )

    # ---- 下:編輯 ----
    gr.Markdown("### ✏️ 編輯選取的點子")
    with gr.Row():
        e_id = gr.Number(label="ID", precision=0, interactive=False)
        e_title = gr.Textbox(label="標題", scale=3)
        e_priority = gr.Slider(1, 5, value=3, step=1, label="優先度")
        e_status = gr.Dropdown(STATUS_CHOICES, value="idea", label="狀態")
    with gr.Row():
        e_url = gr.Textbox(label="來源連結", scale=3)
        e_kind = gr.Dropdown(KIND_EDIT_CHOICES, value="other", label="類型")
    e_link = gr.Markdown("")
    e_content = gr.Textbox(label="我的想法 / 備註", lines=4)
    e_tags = gr.Textbox(label="標籤(逗號分隔)")
    with gr.Row():
        e_save = gr.Button("儲存", variant="primary")
        e_del = gr.Button("刪除", variant="stop")

    with gr.Accordion("📤 匯出", open=False):
        with gr.Row():
            ex_fmt = gr.Radio(["json", "csv"], value="json", label="格式")
            ex_btn = gr.Button("產生檔案")
        ex_file = gr.File(label="下載")

    # ---- 事件 ----
    filters = [f_status, f_tag, f_query, f_kind]
    refresh_out = [table, stats, f_tag]
    for comp in filters:
        comp.change(refresh, filters, refresh_out)

    n_fields = [n_title, n_url, n_kind, n_content, n_tags, n_priority, n_status]
    e_fields = [e_id, e_title, e_url, e_kind, e_content, e_tags, e_priority, e_status]
    n_btn.click(add_idea, [*n_fields, *filters], [*n_fields, *refresh_out])
    table.select(load_idea, [table], [*e_fields, e_link])
    e_save.click(save_idea, [*e_fields[:], *filters], refresh_out)
    e_del.click(delete_idea, [e_id, *filters], [*e_fields, e_link, *refresh_out])
    ex_btn.click(export_file, [ex_fmt], [ex_file])


if __name__ == "__main__":
    demo.launch()
