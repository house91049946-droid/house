# -*- coding: utf-8 -*-
"""IdeaDB 核心邏輯測試(用記憶體 SQLite,不碰真實資料)。"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import IdeaDB, guess_kind, normalize_tags  # noqa: E402


class GuessKindTest(unittest.TestCase):
    def test_guess(self):
        self.assertEqual(guess_kind(""), "feature")
        self.assertEqual(guess_kind("https://youtu.be/abc"), "video")
        self.assertEqual(guess_kind("https://www.YouTube.com/watch?v=1"), "video")
        self.assertEqual(guess_kind("https://example.com/post"), "article")


class NormalizeTagsTest(unittest.TestCase):
    def test_string_dedup_and_lower(self):
        self.assertEqual(normalize_tags(" App, app ,Finance，,"), ["app", "finance"])

    def test_iterable_and_none(self):
        self.assertEqual(normalize_tags(["A", "b"]), ["a", "b"])
        self.assertEqual(normalize_tags(None), [])


class IdeaDBTest(unittest.TestCase):
    def setUp(self):
        self.db = IdeaDB(":memory:")

    def tearDown(self):
        self.db.close()

    def test_add_and_get(self):
        i = self.db.add("  記帳 App ", "內容", tags="app, Finance", priority=4)
        self.assertEqual(i.title, "記帳 App")
        self.assertEqual(i.tags, ["app", "finance"])
        self.assertEqual(i.status, "idea")
        self.assertEqual(self.db.get(i.id).priority, 4)
        self.assertEqual((i.url, i.kind), ("", "feature"))

    def test_url_and_kind(self):
        v = self.db.add("影片", url=" https://youtu.be/abc ")
        self.assertEqual((v.url, v.kind), ("https://youtu.be/abc", "video"))
        f = self.db.add("功能", url="https://x.com/a", kind="feature")
        self.assertEqual(f.kind, "feature")
        with self.assertRaises(ValueError):
            self.db.add("x", kind="nope")
        self.assertEqual([i.id for i in self.db.list(kind="video")], [v.id])
        self.assertEqual([i.id for i in self.db.list(query="youtu")], [v.id])
        u = self.db.update(v.id, url="", kind="other")
        self.assertEqual((u.url, u.kind), ("", "other"))

    def test_validation(self):
        with self.assertRaises(ValueError):
            self.db.add("   ")
        with self.assertRaises(ValueError):
            self.db.add("x", priority=9)
        with self.assertRaises(ValueError):
            self.db.add("x", status="nope")
        with self.assertRaises(KeyError):
            self.db.get(999)

    def test_list_filters(self):
        a = self.db.add("做網站", tags="web", priority=2)
        b = self.db.add("做 App", "手機記帳", tags="app,finance", priority=5)
        self.db.set_status(a.id, "doing")

        self.assertEqual([i.id for i in self.db.list(status="doing")], [a.id])
        self.assertEqual([i.id for i in self.db.list(tag="finance")], [b.id])
        self.assertEqual([i.id for i in self.db.list(query="記帳")], [b.id])
        self.assertEqual([i.id for i in self.db.list(order="priority")], [b.id, a.id])
        self.assertEqual(self.db.all_tags(), ["app", "finance", "web"])

    def test_update_and_delete(self):
        i = self.db.add("舊標題")
        u = self.db.update(i.id, title="新標題", status="done", tags="x")
        self.assertEqual((u.title, u.status, u.tags), ("新標題", "done", ["x"]))
        with self.assertRaises(ValueError):
            self.db.update(i.id, bogus=1)
        self.db.delete(i.id)
        with self.assertRaises(KeyError):
            self.db.get(i.id)
        with self.assertRaises(KeyError):
            self.db.delete(i.id)

    def test_stats_and_export(self):
        self.db.add("a")
        self.db.add("b", status="done")
        st = self.db.stats()
        self.assertEqual((st["idea"], st["done"], st["total"]), (1, 1, 2))
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self.db.export_json(Path(d) / "x.json"), 2)
            self.assertEqual(self.db.export_csv(Path(d) / "x.csv"), 2)
            self.assertIn("a", (Path(d) / "x.csv").read_text(encoding="utf-8-sig"))
            other = IdeaDB(":memory:")
            self.assertEqual(other.import_json(Path(d) / "x.json"), 2)
            self.assertEqual(other.import_json(Path(d) / "x.json"), 0)  # 重複略過
            self.assertEqual(other.stats()["total"], 2)
            other.close()


if __name__ == "__main__":
    unittest.main()
