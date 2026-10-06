# -*- coding: utf-8 -*-
"""Idea 資料庫命令列工具。

範例:
    python Idea/cli.py add "拖曳排序的看板 UI" -u https://youtu.be/xxxx -c "想用在待辦 App" -t ui,app
    python Idea/cli.py list
    python Idea/cli.py list --kind video
    python Idea/cli.py list --status doing --tag app
    python Idea/cli.py search 記帳
    python Idea/cli.py show 1
    python Idea/cli.py edit 1 --status doing --priority 5
    python Idea/cli.py done 1
    python Idea/cli.py rm 1
    python Idea/cli.py tags
    python Idea/cli.py export ideas.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import DEFAULT_DB_PATH, KIND_LABELS, KINDS, STATUS_LABELS, STATUSES, Idea, IdeaDB  # noqa: E402


def _fmt_row(i: Idea) -> str:
    tags = " ".join(f"#{t}" for t in i.tags)
    stars = "★" * i.priority + "☆" * (5 - i.priority)
    return f"[{i.id:>3}] {KIND_LABELS[i.kind]} {STATUS_LABELS[i.status]:<6} {stars}  {i.title}  {tags}".rstrip()


def _print_ideas(ideas: list[Idea]) -> None:
    if not ideas:
        print("(沒有符合的點子)")
        return
    for i in ideas:
        print(_fmt_row(i))
    print(f"共 {len(ideas)} 筆")


def _print_detail(i: Idea) -> None:
    print(f"#{i.id}  {i.title}")
    print(f"類型:{KIND_LABELS[i.kind]}   狀態:{STATUS_LABELS[i.status]}   優先度:{i.priority}/5")
    print(f"標籤:{', '.join(i.tags) or '(無)'}")
    print(f"連結:{i.url or '(無)'}")
    print(f"建立:{i.created_at}   更新:{i.updated_at}")
    if i.content:
        print("-" * 40)
        print(i.content)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Idea 資料庫")
    p.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite 檔案路徑(預設 Idea/data/ideas.db)")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="新增點子")
    a.add_argument("title")
    a.add_argument("-c", "--content", default="", help="我的想法 / 備註")
    a.add_argument("-u", "--url", default="", help="來源連結(影片 / 文章 / 產品頁)")
    a.add_argument("-k", "--kind", choices=KINDS, help="類型(不填會從網址猜)")
    a.add_argument("-t", "--tags", default="", help="標籤,逗號分隔")
    a.add_argument("-p", "--priority", type=int, default=3, help="優先度 1~5")
    a.add_argument("-s", "--status", choices=STATUSES, default="idea")

    ls = sub.add_parser("list", help="列出點子")
    ls.add_argument("--status", choices=STATUSES)
    ls.add_argument("--kind", choices=KINDS)
    ls.add_argument("--tag")
    ls.add_argument("--order", choices=["updated", "created", "priority", "id"], default="updated")

    s = sub.add_parser("search", help="關鍵字搜尋(標題 / 內容 / 標籤)")
    s.add_argument("query")

    sh = sub.add_parser("show", help="顯示單一點子詳情")
    sh.add_argument("id", type=int)

    e = sub.add_parser("edit", help="修改點子")
    e.add_argument("id", type=int)
    e.add_argument("--title")
    e.add_argument("-c", "--content")
    e.add_argument("-u", "--url")
    e.add_argument("-k", "--kind", choices=KINDS)
    e.add_argument("-t", "--tags")
    e.add_argument("-p", "--priority", type=int)
    e.add_argument("-s", "--status", choices=STATUSES)

    for name, status in (("done", "done"), ("doing", "doing"), ("drop", "dropped")):
        q = sub.add_parser(name, help=f"把點子標為 {STATUS_LABELS[status]}")
        q.add_argument("id", type=int)
        q.set_defaults(quick_status=status)

    r = sub.add_parser("rm", help="刪除點子")
    r.add_argument("id", type=int)

    sub.add_parser("tags", help="列出所有標籤")
    sub.add_parser("stats", help="各狀態數量")

    ex = sub.add_parser("export", help="匯出成 .json 或 .csv")
    ex.add_argument("path")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    with IdeaDB(args.db) as db:
        try:
            if args.cmd == "add":
                i = db.add(args.title, args.content, args.tags, args.status, args.priority,
                           url=args.url, kind=args.kind)
                print("已新增:", _fmt_row(i))
            elif args.cmd == "list":
                _print_ideas(db.list(status=args.status, kind=args.kind, tag=args.tag, order=args.order))
            elif args.cmd == "search":
                _print_ideas(db.list(query=args.query))
            elif args.cmd == "show":
                _print_detail(db.get(args.id))
            elif args.cmd == "edit":
                fields = {
                    k: v
                    for k, v in (
                        ("title", args.title),
                        ("content", args.content),
                        ("url", args.url),
                        ("kind", args.kind),
                        ("tags", args.tags),
                        ("priority", args.priority),
                        ("status", args.status),
                    )
                    if v is not None
                }
                if not fields:
                    print("沒有指定要修改的欄位")
                    return 1
                print("已更新:", _fmt_row(db.update(args.id, **fields)))
            elif args.cmd in ("done", "doing", "drop"):
                print("已更新:", _fmt_row(db.set_status(args.id, args.quick_status)))
            elif args.cmd == "rm":
                db.delete(args.id)
                print(f"已刪除 #{args.id}")
            elif args.cmd == "tags":
                tags = db.all_tags()
                print("\n".join(f"#{t}" for t in tags) if tags else "(尚無標籤)")
            elif args.cmd == "stats":
                st = db.stats()
                for s in STATUSES:
                    print(f"{STATUS_LABELS[s]:<6} {st[s]}")
                print(f"總計     {st['total']}")
            elif args.cmd == "export":
                path = Path(args.path)
                if path.suffix.lower() == ".csv":
                    n = db.export_csv(path)
                else:
                    n = db.export_json(path)
                print(f"已匯出 {n} 筆到 {path}")
        except (KeyError, ValueError) as exc:
            msg = exc.args[0] if exc.args else str(exc)
            print(f"錯誤:{msg}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
