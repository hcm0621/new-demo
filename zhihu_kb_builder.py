#!/usr/bin/env python3
"""抓取 csbaoyan 2025 列表中的文章正文，并生成可入库的 Markdown 知识库。

重点：
1) 优先抓正文（支持知乎 Cookie）。
2) 抓不到时保留失败原因，方便补抓。
3) 每篇输出结构化摘要（院校、背景、流程、建议）。
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin
from urllib.request import Request, urlopen

CSBAOYAN_2025_URL = "https://csbaoyan.top/%E4%BF%9D%E7%A0%94%E7%BB%8F%E9%AA%8C%E8%B4%B4/2025%E5%B9%B4/"

TARGETS = [
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

# 当在线抓取 csbaoyan 失败时，可使用此映射继续抓正文。
FALLBACK_LINKS = {
    1: [
        "https://zhuanlan.zhihu.com/p/1957692666109198902",
        "https://zhuanlan.zhihu.com/p/1957555583134720721",
    ],
    2: ["http://hjw-vip.github.io/"],
    3: [
        "https://zhuanlan.zhihu.com/p/1957692666109198902",
        "https://zhuanlan.zhihu.com/p/1957555583134720721",
    ],
    4: ["https://www.xiaohongshu.com/user/profile/6503f20a0000000012006cbc"],
    5: ["https://www.xiaohongshu.com/user/profile/61cda3a2000000000201d31d"],
    6: ["https://zhuanlan.zhihu.com/p/1953411297023619478"],
    7: ["https://zhuanlan.zhihu.com/p/1954588158969750416"],
    8: ["https://zhuanlan.zhihu.com/p/1957191317231765046"],
    9: ["https://zhuanlan.zhihu.com/p/1957513765517006125"],
    10: ["https://mp.weixin.qq.com/s/Csaz3Li_R8-RlyrUnl-guw"],
    11: ["https://zhuanlan.zhihu.com/p/1949494281296384865"],
    12: ["https://zhuanlan.zhihu.com/p/1953927151016482388"],
    13: ["https://zhuanlan.zhihu.com/p/1957096969475458759"],
    14: ["https://zhuanlan.zhihu.com/p/1994179961309901376"],
}

UNIV_PATTERNS = [
    "清华", "北大", "人大", "复旦", "上交", "浙大", "南大", "同济", "东南", "哈工大", "中山", "武大", "厦大",
    "国科大", "中科院", "自动化所", "计算所", "软微", "上海AI Lab", "上科大", "华东师范", "华东理工",
]


@dataclass
class Entry:
    idx: int
    target: str
    links: list[str]


class ATagParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_a = False
        self.href = ""
        self.parts: list[str] = []
        self.items: list[tuple[str, str]] = []

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
        self.in_a = False
        if text:
            self.items.append((" ".join(text.split()), self.href.strip()))


def normalize(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\s+", "", s)
    return re.sub(r"[^\w\u4e00-\u9fff@]+", "", s)


def fetch_url(url: str, timeout: int, cookie: str = "") -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if cookie:
        headers["Cookie"] = cookie
    req = Request(url, headers=headers)
    with urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="ignore")


def extract_entries_from_csbaoyan(html: str, base_url: str, targets: list[str]) -> list[Entry]:
    parser = ATagParser()
    parser.feed(html)
    anchors = [(text, urljoin(base_url, href)) for text, href in parser.items]

    entries: list[Entry] = []
    used: set[int] = set()
    for i, target in enumerate(targets, start=1):
        nt = normalize(target)
        links: list[str] = []

        for j, (text, href) in enumerate(anchors):
            if j in used:
                continue
            ntext = normalize(text)
            if not ntext:
                continue
            if nt in ntext or ntext in nt:
                links.append(href)
                used.add(j)

        # 对含“以及关于 AI 入门建议”的条目，常见为两条链接，补充同作者紧邻链接。
        if "Axi404" in target and len(links) == 1:
            for text, href in anchors:
                if "AI" in text and "入门" in text:
                    links.append(href)
                    break

        entries.append(Entry(idx=i, target=target, links=links))
    return entries


def html_to_text(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_universities(text: str) -> list[str]:
    found = []
    for name in UNIV_PATTERNS:
        if name in text:
            found.append(name)
    return found


def summarize_text(text: str, max_points: int = 10) -> list[str]:
    # 轻量规则摘要：按句切分，优先保留包含关键信号词的句子。
    sentences = re.split(r"(?<=[。！？!?；;])", text)
    keywords = ["保研", "夏令营", "预推免", "面试", "导师", "项目", "竞赛", "科研", "院校", "建议", "时间"]
    scored: list[tuple[int, str]] = []
    for s in sentences:
        s = s.strip()
        if len(s) < 20:
            continue
        score = sum(1 for k in keywords if k in s)
        score += min(len(s) // 40, 3)
        if score > 0:
            scored.append((score, s))
    scored.sort(key=lambda x: x[0], reverse=True)

    seen = set()
    result: list[str] = []
    for _, s in scored:
        key = normalize(s[:80])
        if key in seen:
            continue
        seen.add(key)
        result.append(s)
        if len(result) >= max_points:
            break
    if not result:
        result = [text[:300]] if text else ["（未抓取到正文）"]
    return result


def build_markdown(entries: list[Entry], article_data: dict[int, dict[str, str]]) -> str:
    lines = [
        "# 2025 保研经验贴知识库（可直接上传给 AI）",
        "",
        "本文件由脚本自动生成：每篇包含原文链接、院校关键词、结构化摘要与正文节选。",
        "",
    ]

    for e in entries:
        data = article_data.get(e.idx, {})
        text = data.get("text", "")
        fetch_status = data.get("status", "unknown")
        fail_reason = data.get("reason", "")
        univs = extract_universities(text)
        summary_points = summarize_text(text, max_points=12)

        lines.append(f"## {e.idx}. {e.target}")
        lines.append("")
        if e.links:
            for link in e.links:
                lines.append(f"- 原文链接：{link}")
        else:
            lines.append("- 原文链接：未从 csbaoyan 匹配到，使用脚本回退映射")
            for link in FALLBACK_LINKS.get(e.idx, []):
                lines.append(f"  - {link}")

        lines.append(f"- 抓取状态：{fetch_status}")
        if fail_reason:
            lines.append(f"- 失败原因：{fail_reason}")
        lines.append(f"- 提取院校关键词：{', '.join(univs) if univs else '（未识别）'}")
        lines.append("- 结构化摘要：")
        for p in summary_points:
            lines.append(f"  - {p}")

        if text:
            excerpt = text[:1500]
            lines.append("- 正文节选（前 1500 字）：")
            lines.append("```text")
            lines.append(excerpt)
            lines.append("```")
        lines.append("")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="抓取并汇总保研经验贴为知识库 Markdown")
    p.add_argument("--url", default=CSBAOYAN_2025_URL)
    p.add_argument("--html-file", default="", help="离线模式：从本地 csbaoyan HTML 读取")
    p.add_argument("--cookie-file", default="", help="知乎 Cookie 文件（原样粘贴 Cookie 字符串）")
    p.add_argument("--timeout", type=int, default=30)
    p.add_argument("--output", default="zhihu_kb_2025.md")
    p.add_argument("--dump-json", default="crawl_result.json", help="保存中间抓取结果")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cookie = Path(args.cookie_file).read_text(encoding="utf-8").strip() if args.cookie_file else ""

    try:
        if args.html_file:
            cs_html = Path(args.html_file).read_text(encoding="utf-8")
        else:
            cs_html = fetch_url(args.url, timeout=args.timeout)
        entries = extract_entries_from_csbaoyan(cs_html, args.url, TARGETS)
    except Exception as exc:
        print(f"Warn: failed to fetch/parse csbaoyan ({exc}), use fallback links.")
        entries = [Entry(idx=i, target=t, links=FALLBACK_LINKS.get(i, [])) for i, t in enumerate(TARGETS, start=1)]

    article_data: dict[int, dict[str, str]] = {}

    for e in entries:
        links = e.links or FALLBACK_LINKS.get(e.idx, [])
        if not links:
            article_data[e.idx] = {"status": "failed", "reason": "no link", "text": ""}
            continue

        merged_text_parts: list[str] = []
        reasons: list[str] = []
        ok_count = 0

        for link in links:
            try:
                raw = fetch_url(link, timeout=args.timeout, cookie=cookie)
                text = html_to_text(raw)
                if "403" in text[:300] and "知乎" in text[:300]:
                    reasons.append(f"{link}: zhihu anti-bot 403")
                    continue
                if len(text) < 200:
                    reasons.append(f"{link}: content too short")
                    continue
                merged_text_parts.append(text)
                ok_count += 1
            except Exception as exc:
                reasons.append(f"{link}: {exc}")

        if ok_count > 0:
            article_data[e.idx] = {
                "status": f"success ({ok_count}/{len(links)} links)",
                "reason": " | ".join(reasons),
                "text": "\n".join(merged_text_parts),
            }
        else:
            article_data[e.idx] = {
                "status": "failed",
                "reason": " | ".join(reasons),
                "text": "",
            }

    md = build_markdown(entries, article_data)
    Path(args.output).write_text(md, encoding="utf-8")
    Path(args.dump_json).write_text(json.dumps(article_data, ensure_ascii=False, indent=2), encoding="utf-8")

    success = sum(1 for v in article_data.values() if v.get("status", "").startswith("success"))
    print(f"done: {success}/{len(entries)} entries fetched successfully")
    print(f"markdown: {args.output}")
    print(f"json: {args.dump_json}")


if __name__ == "__main__":
    main()
