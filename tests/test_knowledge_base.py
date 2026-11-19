import os
import tempfile
import unittest
from unittest import mock

from flipper_mcp import knowledge_base as kb


class KnowledgeBase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = os.path.join(tmp.name, "knowledge")  # not created yet, like a fresh clone
        patcher = mock.patch.object(kb, "KB_DIR", self.dir)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_slug(self):
        self.assertEqual(kb.slug("WiFi Capture / Crack!"), "wifi-capture-crack")
        self.assertEqual(kb.slug("***"), "note")

    def test_slug_blocks_path_traversal(self):
        self.assertNotIn("/", kb.slug("../../etc/passwd"))
        self.assertNotIn("..", kb.slug("../../etc/passwd"))

    def test_empty_state_is_friendly(self):
        self.assertIn("no knowledge yet", kb.list_notes())
        self.assertIn("no knowledge yet", kb.search_notes("x"))
        self.assertIn("no note 'missing'", kb.read_note("missing"))

    def test_save_then_read_and_list(self):
        self.assertEqual(kb.save_note("IR Remote", "use ir rx raw"), "saved -> knowledge/ir-remote.md")
        text = kb.read_note("ir remote")  # topic is matched by slug
        self.assertTrue(text.startswith("# IR Remote\n"))
        self.assertIn("use ir rx raw", text)
        self.assertEqual(kb.list_notes(), "- ir-remote : IR Remote")

    def test_append_adds_a_second_dated_section(self):
        kb.save_note("t", "first")
        kb.save_note("t", "second")
        text = kb.read_note("t")
        self.assertIn("first", text)
        self.assertIn("second", text)
        self.assertEqual(text.count("\n## "), 2)

    def test_replace_discards_old_content(self):
        kb.save_note("t", "old")
        kb.save_note("t", "new", append=False)
        text = kb.read_note("t")
        self.assertNotIn("old", text)
        self.assertIn("new", text)

    def test_search_is_case_insensitive_and_reports_location(self):
        kb.save_note("wifi", "Handshake needs deauth")
        hits = kb.search_notes("HANDSHAKE")
        self.assertRegex(hits, r"^wifi:\d+: Handshake needs deauth$")

    def test_search_no_match(self):
        kb.save_note("wifi", "x")
        self.assertEqual(kb.search_notes("zzz"), "no matches for 'zzz'")

    def test_list_ignores_non_markdown(self):
        kb.save_note("a", "x")
        with open(os.path.join(self.dir, ".gitignore"), "w") as fh:
            fh.write("*\n")
        self.assertEqual(kb.list_notes().count("\n"), 0)


if __name__ == "__main__":
    unittest.main()
