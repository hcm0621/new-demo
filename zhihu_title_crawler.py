#!/usr/bin/env python3
"""按指定顺序提取 csbaoyan 页面中的目标经验贴，并生成 README 列表。"""

from __future__ import annotations

import argparse
import re
import ssl
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import quote_plus, urljoin
from urllib.request import Request, urlopen


DEFAULT_URL = "https://csbaoyan.top/%E4%BF%9D%E7%A0%94%E7%BB%8F%E9%AA%8C%E8%B4%B4/2025%E5%B9%B4/"

DEFAULT_TARGETS = [
    "@Axi404的乘凉，我的保研经验贴以及关于 AI 入门以及泛保研相关的建议",
    "@H-WEI的小H呼噜呼噜睡的保研经验贴(北大cs、浙软、同济cs、复旦cs、上交cs等(中九低rk的梭哈历程))",
    "@Axi404的乘凉，我的保研经验贴以及关于 AI 入门以及泛保研相关的建议",
    "@石上三年的「南大智科/浙大软件/西交计科/中山计科/中山软件/深先院数字所/等」22级夏令营/预推免保研经验贴",
    "@SKST的(保研为我带来了什么?)计算机保研反焦虑贴 兼 经验贴",
    "@朝花夕拾的2025年（2026届）计算机保研回忆录（国科大杭高、上交软、上海AI Lab、中山cs、贵系工程硕博等）",
    "@forever的2025年(26届)计算机ACMer保研经验贴 [北大软微/大数据/上海创智/人大高瓴/南大计算机]-四次与清北擦肩而过后我只能选择祛魅",
    "@l9006的2025年（2026届）计算机保研经验贴——清北华五人+京二所等",
    "@若楠的2025年（2026届）计算机保研经验贴（同济cs，南大se，东南cs，南大cs，南大ai，复旦cs）",
    "@tby的保研后记 | 未知才是未来——敬每一场相遇与分别（本科双非，国科大杭高院智能学院/华东师范智能教育/上科大信息学院/华东理工信息学院等）",
    "@爱吃小浣熊干脆面的2025年（26届）末九计算机拔尖班保研回忆录（清软+软微+上交+科大+AILab+计算所+武大+空天院）",
    "@渝中半岛铝盒的2025年（26届）华五中上/无竞赛/弱科研计算机保研回忆录（南大智科/中山cs/自动化所/浙大cs/上交ai）",
    "@沉默的知更鸟的2025年（2026届）双非计算机保研（北京中关村学院，复旦机器人，自动化所，厦大MAC, 东南PALM，浙软，天大智算、上科大VDI等等）",
    "@早也不晚的2025年（2026届）四非计算机rank1也能保研华五人C9吗（复旦机器人、人大信、哈工大本部）",
]


@dataclass
class Record:
    title: str
    href: str


class AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_a = False
        self.href = ""
        self.parts: list[str] = []
        self.records: list[Record] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        self.in_a = True
        self.href = dict(attrs).get("href") or ""
        self.parts = []

    def handle_data(self, data: str) -> None:
        if self.in_a:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self.in_a:
            return
        text = unescape("".join(self.parts)).strip()
        if text:
            self.records.append(Record(title=" ".join(text.split()), href=self.href.strip()))
        self.in_a = False


def normalize(text: str) -> str:
    text = re.sub(r"\s+", "", text.lower())
    return re.sub(r"[^\w\u4e00-\u9fff@]+", "", text)


def fetch_html(url: str, timeout: int = 20) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="ignore")


def parse_anchors(html: str, base_url: str) -> list[Record]:
    parser = AnchorParser()
    parser.feed(html)
    uniq: list[Record] = []
    seen: set[tuple[str, str]] = set()
    for r in parser.records:
        href = urljoin(base_url, r.href)
        key = (r.title, href)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(Record(title=r.title, href=href))
    return uniq


def match_records(records: Iterable[Record], targets: list[str]) -> list[tuple[str, Record | None]]:
    pool = list(records)
    used: set[int] = set()
    out: list[tuple[str, Record | None]] = []
    for target in targets:
        nt = normalize(target)
        hit: Record | None = None
        hit_index = -1
        for idx, r in enumerate(pool):
            if idx in used:
                continue
            nr = normalize(r.title)
            if nt in nr or nr in nt:
                hit = r
                hit_index = idx
                break
        if hit_index >= 0:
            used.add(hit_index)
        out.append((target, hit))
    return out


def write_readme(matches: list[tuple[str, Record | None]], output: Path, source_url: str) -> None:
    lines = [
        "# 2025 保研经验贴（按你给出的顺序）",
        "",
        f"来源页面：{source_url}",
        "",
    ]
    for i, (target, hit) in enumerate(matches, start=1):
        if hit:
            lines.append(f"{i}. [{target}]({hit.href})")
        else:
            search_url = f"https://www.zhihu.com/search?type=content&q={quote_plus(target)}"
            lines.append(f"{i}. [{target}]({search_url})（未在页面中匹配到原始链接，已回退到知乎搜索）")
    lines.append("")
    output.write_text("\n".join(lines), encoding="utf-8")


def load_targets(path: str) -> list[str]:
    if not path:
        return DEFAULT_TARGETS
    lines = [x.strip() for x in Path(path).read_text(encoding="utf-8").splitlines()]
    return [x for x in lines if x]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="提取指定知乎经验贴并写成 README 列表")
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--html-file", default="", help="离线模式：从本地 HTML 读取")
    p.add_argument("--targets-file", default="", help="每行一个目标标题，不传则使用内置列表")
    p.add_argument("--output-readme", default="README.md")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    targets = load_targets(args.targets_file)
    if args.html_file:
        html = Path(args.html_file).read_text(encoding="utf-8")
        records = parse_anchors(html, args.url)
    else:
        try:
            html = fetch_html(args.url)
            records = parse_anchors(html, args.url)
        except Exception as exc:
            print(f"Warn: online fetch failed ({exc}); fallback to search links only.")
            records = []
    matches = match_records(records, targets)
    write_readme(matches, Path(args.output_readme), args.url)
    matched_count = sum(1 for _, r in matches if r)
    print(f"README generated: {args.output_readme} (matched {matched_count}/{len(matches)})")


if __name__ == "__main__":
    main()
