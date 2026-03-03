#!/usr/bin/env python3
"""Crawl article titles (and optional links) from csbaoyan pages.

Default use case:
  python zhihu_title_crawler.py \
      --url "https://csbaoyan.top/保研经验贴/2025年/" \
      --keyword "知乎" \
      --output zhihu_titles.txt

The script uses only Python standard library to keep setup simple.
"""

from __future__ import annotations

import argparse
import json
import ssl
from dataclasses import asdict, dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin
from urllib.request import Request, urlopen


@dataclass
class TitleRecord:
    title: str
    href: str


class AnchorParser(HTMLParser):
    """Extract all anchor text + href from HTML."""

    def __init__(self) -> None:
        super().__init__()
        self._in_anchor = False
        self._href = ""
        self._text_parts: list[str] = []
        self.records: list[TitleRecord] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        self._in_anchor = True
        attr_map = dict(attrs)
        self._href = attr_map.get("href") or ""
        self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_anchor:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._in_anchor:
            return
        text = unescape("".join(self._text_parts)).strip()
        if text:
            self.records.append(TitleRecord(title=text, href=self._href.strip()))
        self._in_anchor = False
        self._href = ""
        self._text_parts = []


def fetch_html(url: str, timeout: int = 20) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0 Safari/537.36"
            )
        },
    )

    # Some environments have strict SSL interception; this makes local execution easier.
    ssl_ctx = ssl.create_default_context()
    with urlopen(req, timeout=timeout, context=ssl_ctx) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="ignore")


def extract_titles(
    html: str,
    base_url: str,
    keyword: str = "",
    must_include_at_sign: bool = False,
) -> list[TitleRecord]:
    parser = AnchorParser()
    parser.feed(html)

    results: list[TitleRecord] = []
    seen: set[tuple[str, str]] = set()

    for r in parser.records:
        title = " ".join(r.title.split())
        href = urljoin(base_url, r.href)

        if keyword and keyword not in title and keyword not in href:
            continue
        if must_include_at_sign and "@" not in title:
            continue

        key = (title, href)
        if key in seen:
            continue
        seen.add(key)
        results.append(TitleRecord(title=title, href=href))

    return results


def save_lines(records: Iterable[TitleRecord], output: Path) -> None:
    lines = [f"{r.title}\t{r.href}" for r in records]
    output.write_text("\n".join(lines), encoding="utf-8")


def save_json(records: Iterable[TitleRecord], output: Path) -> None:
    payload = [asdict(r) for r in records]
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Crawl titles from a web page (e.g. csbaoyan).")
    p.add_argument(
        "--url",
        default="https://csbaoyan.top/%E4%BF%9D%E7%A0%94%E7%BB%8F%E9%AA%8C%E8%B4%B4/2025%E5%B9%B4/",
        help="Target page URL.",
    )
    p.add_argument("--keyword", default="", help="Only keep records containing this keyword.")
    p.add_argument(
        "--must-include-at-sign",
        action="store_true",
        help="Only keep titles containing '@', matching your sample format.",
    )
    p.add_argument(
        "--output",
        default="zhihu_titles.txt",
        help="Output file path.",
    )
    p.add_argument(
        "--format",
        choices=["txt", "json"],
        default="txt",
        help="Output format.",
    )
    p.add_argument(
        "--html-file",
        default="",
        help="Read HTML from local file instead of network (for offline testing).",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.html_file:
        html = Path(args.html_file).read_text(encoding="utf-8")
    else:
        html = fetch_html(args.url)

    records = extract_titles(
        html=html,
        base_url=args.url,
        keyword=args.keyword,
        must_include_at_sign=args.must_include_at_sign,
    )

    out = Path(args.output)
    if args.format == "json":
        save_json(records, out)
    else:
        save_lines(records, out)

    print(f"Saved {len(records)} records to {out}")


if __name__ == "__main__":
    main()
