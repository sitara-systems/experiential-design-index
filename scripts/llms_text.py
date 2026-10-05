"""Rendered HTML page -> plain text, for llms-full.txt."""
from __future__ import annotations

import html
import re


def html_to_text(page_html: str) -> str:
    """Main content of a rendered page as plain text (nav/header/footer,
    scripts and styles dropped; block tags become line breaks)."""
    m = re.search(r"<main\b.*?</main>", page_html, re.S | re.I)
    h = m.group(0) if m else page_html
    h = re.sub(r"<(script|style|nav|header|footer)\b.*?</\1>", "", h, flags=re.S | re.I)
    h = re.sub(r"</(p|h[1-6]|li|tr|div|section|table|ul|ol)>|<br\s*/?>", "\n", h, flags=re.I)
    h = re.sub(r"<[^>]+>", " ", h)
    h = html.unescape(h)
    h = re.sub(r"[ \t]+", " ", h)
    return re.sub(r"\n\s*\n+", "\n\n", h).strip()
