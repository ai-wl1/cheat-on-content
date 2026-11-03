#!/usr/bin/env python3
"""Build an https://x.com/intent/post URL from local text. Does not use the network."""

from __future__ import annotations

import argparse
import re
import sys
from urllib.parse import quote

_POST_ID = re.compile(r"[0-9]{1,20}\Z")


def build_intent_url(text: str, in_reply_to: str | None = None) -> str:
    """Return an intent link. `text` is percent-encoded. Reply ids must be decimal."""
    if not isinstance(text, str) or text.strip() == "":
        raise ValueError("text is empty")
    if any(ch in text for ch in ("\x00",)):
        raise ValueError("text contains a null")
    url = "https://x.com/intent/post?text=" + quote(text, safe="")
    if in_reply_to is not None:
        if not isinstance(in_reply_to, str) or _POST_ID.fullmatch(in_reply_to) is None:
            raise ValueError("in_reply_to must be a decimal post id")
        url += "&in_reply_to=" + in_reply_to
    return url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print an X compose intent URL. No network.")
    parser.add_argument("--text", required=True, help="Post text. Encode it; do not send it anywhere.")
    parser.add_argument("--in-reply-to", default=None, help="Numeric post id for a reply.")
    args = parser.parse_args(argv)
    try:
        print(build_intent_url(args.text, args.in_reply_to))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
