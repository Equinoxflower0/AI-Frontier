"""
build_search_index.py
====================
全站资讯搜索索引构建器。

做什么：
    扫描根目录下所有 daily-brief-YYYY-MM-DD.html，把每一期的每一条资讯
    （标题 / 摘要 / 为什么重要 / 分类 / 来源 / 原文链接 / 发布日期）提取出来，
    写成 search-index.json，供 search.html 在浏览器里做纯前端搜索。

为什么解析 HTML 而不是 JSON：
    历史各期的 scored_news.json 没有入库（scripts/data/ 被 gitignore），
    但每期日报 HTML 一定在仓库里——它就是唯一完整的"过往资讯"记录。

去重规则：
    同一条资讯（相同链接）出现在多期日报里时，只保留最早出现的那一期
    （即它的"首发日期"），避免搜索结果里同一新闻重复出现。

用法：
    python scripts/build_search_index.py          # 输出 search-index.json
"""

import json
import re
import sys
from html import unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _utf8  # noqa: F401  —— 强制 UTF-8 输出，防止 GBK 控制台崩溃

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT / "search-index.json"

BRIEF_NAME = re.compile(r"^daily-brief-(\d{4}-\d{2}-\d{2})\.html$")

# 一条资讯卡片的特征：带 category 徽章 span 的 article（首页统计卡不带这个）。
# 早期(9月)日报的卡片带 data-page-node-id 额外属性，所以用 [^>]* 容忍任意属性。
ITEM_SPLIT = re.compile(
    r'<article class="bg-white rounded-xl border border-slate-200 p-5[^>]*>(.*?)</article>',
    re.S,
)
CAT_RE = re.compile(r'<span class="bg-\w+-100[^>]*>([^<]+)</span>')
SOURCE_PUB_RE = re.compile(r'<span class="text-xs text-slate-400"[^>]*>([^<·]+?)\s*(?:·\s*([^<]*))?</span>')
TITLE_LINK_RE = re.compile(r'<h3[^>]*>\s*<a href="([^"]+)"[^>]*>(.*?)</a>\s*</h3>', re.S)
SUMMARY_RE = re.compile(r'<p class="text-sm text-slate-600 leading-relaxed"[^>]*>(.*?)</p>', re.S)
WHY_RE = re.compile(r'<strong class="text-slate-900">为什么重要：?</strong>(.*?)</p>', re.S)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def clean_text(s: str, max_len: int = 400) -> str:
    """去标签 → 反转义 → 压空白 → 截断。"""
    if not s:
        return ""
    t = unescape(TAG_RE.sub(" ", s))
    t = WS_RE.sub(" ", t).strip()
    return t[:max_len]


def parse_brief(path: Path) -> list:
    """解析一期日报，返回条目 dict 列表。"""
    doc = path.read_text(encoding="utf-8", errors="ignore")
    items = []
    for block in ITEM_SPLIT.split(doc)[1::2]:
        m = TITLE_LINK_RE.search(block)
        if not m or not m.group(1).startswith("http"):
            continue
        cat_m = CAT_RE.search(block)
        sp_m = SOURCE_PUB_RE.search(block)
        s_m = SUMMARY_RE.search(block)
        w_m = WHY_RE.search(block)
        items.append({
            "t": clean_text(m.group(2), 200),          # 标题（中文翻译）
            "l": m.group(1),                            # 原文链接
            "c": cat_m.group(1).strip() if cat_m else "综合",
            "src": sp_m.group(1).strip() if sp_m else "",
            "pub": (sp_m.group(2) or "").strip() if sp_m else "",
            "s": clean_text(s_m.group(1) if s_m else "", 400),   # 摘要
            "w": clean_text(w_m.group(1) if w_m else "", 300),  # 为什么重要
        })
    return items


def main():
    briefs = sorted(
        (p for p in ROOT.glob("daily-brief-*.html") if BRIEF_NAME.match(p.name)),
        key=lambda p: p.name,
    )
    if not briefs:
        print("[WARN] 没有找到任何 daily-brief-*.html，索引为空")
        OUTPUT_FILE.write_text("[]", encoding="utf-8")
        return

    seen = set()
    entries = []
    per_issue = []
    for path in briefs:
        date_str = BRIEF_NAME.match(path.name).group(1)
        issue_items = parse_brief(path)
        fresh = 0
        for it in issue_items:
            if it["l"] in seen:
                continue
            seen.add(it["l"])
            it["d"] = date_str
            entries.append(it)
            fresh += 1
        per_issue.append((date_str, len(issue_items), fresh))

    payload = {
        "built_at": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": len(entries),
        "issues": len(briefs),
        "items": entries,
    }
    OUTPUT_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    print("=== AI Frontier · 搜索索引 ===")
    for d, total, fresh in per_issue:
        print(f"  {d}  解析 {total:>3} 条 · 首发收录 {fresh:>3} 条")
    size_kb = OUTPUT_FILE.stat().st_size / 1024
    print(f"[OK] {OUTPUT_FILE.name}：{len(entries)} 条 · {size_kb:.0f} KB · 来自 {len(briefs)} 期日报")


if __name__ == "__main__":
    main()
