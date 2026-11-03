#!/usr/bin/env python3
"""Tests for x_intent.py. They only compare strings."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import x_intent


class IntentTests(unittest.TestCase):
    def test_encodes_text_and_preserves_source_link(self) -> None:
        text = "简评\n来源：https://example.com/a?b=1&c=2"
        url = x_intent.build_intent_url(text)
        self.assertTrue(url.startswith("https://x.com/intent/post?text="))
        parts = urlsplit(url)
        self.assertEqual(parts.netloc, "x.com")
        self.assertEqual(parts.path, "/intent/post")
        query = parse_qs(parts.query, keep_blank_values=True)
        self.assertEqual(query["text"], [text])
        self.assertNotIn("in_reply_to", query)
        self.assertNotIn("&c=2", url.split("?", 1)[1].split("text=", 1)[0])

    def test_reply_adds_numeric_id(self) -> None:
        url = x_intent.build_intent_url("回复一句", "1234567890123456789")
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(query["in_reply_to"], ["1234567890123456789"])
        self.assertEqual(query["text"], ["回复一句"])

    def test_rejects_empty_text_and_bad_ids(self) -> None:
        with self.assertRaises(ValueError):
            x_intent.build_intent_url("   ")
        with self.assertRaises(ValueError):
            x_intent.build_intent_url("hi", "12abc")
        with self.assertRaises(ValueError):
            x_intent.build_intent_url("hi", "https://x.com/i/status/1")
        with self.assertRaises(ValueError):
            x_intent.build_intent_url("hi", "")


if __name__ == "__main__":
    unittest.main()
