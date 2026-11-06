"""
generate_seo.py
===============
生成 sitemap.xml / rss.xml / robots.txt

之前站点的 sitemap 和 RSS 都是 404：
  - 搜索引擎无法完整发现 70 多个页面
  - 想订阅的人没有入口（也是"聚合一堵墙、接不了订阅"的一环）

这三个文件都从本地实际产物生成，不需要额外维护：
  - sitemap：首页 + 玩法 + 往期 + 全部日报 + 全部教程
  - rss：最新一期日报的条目（标题 / 摘要 / 原文链接）
  - robots：允许抓取并指向 sitemap

用法：python scripts/generate_seo.py
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).parent))
import _utf8  # noqa: F401
from content_quality import clean_link

ROOT = Path(__file__).parent.parent
DATA_DIR = Path(__file__).parent / "data"

BASE_URL = "https://equinoxflower0.github.io/AI-Frontier"
SITE_TITLE = "AI Frontier · 全球 AI 前沿资讯"
SITE_DESC = "每天 5 分钟掌握全球 AI 核心动态：模型发布、开源项目、论文、产业动向，以及可上手的 AI 玩法。"


def _lastmod(path: Path) -> str:
    try:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    except OSError:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def collect_pages():
    """收集要进 sitemap 的页面：(相对路径, 优先级, 更新频率)"""
    pages = []

    for name in ("index.html", "playground.html", "archive.html"):
        if (ROOT / name).exists():
            pages.append((name, "1.0" if name == "index.html" else "0.9", "daily"))

    if (ROOT / "tutorials" / "index.html").exists():
        pages.append(("tutorials/index.html", "0.8", "weekly"))

    # 日报：按日期倒序，最新的优先级最高
    briefs = sorted(ROOT.glob("daily-brief-*.html"), reverse=True)
    for i, p in enumerate(briefs):
        pages.append((p.name, "0.9" if i == 0 else "0.6", "never"))

    for p in sorted((ROOT / "tutorials").glob("*.html")):
        if p.name == "index.html":
            continue
        pages.append((f"tutorials/{p.name}", "0.6", "monthly"))

    return pages


def build_sitemap(pages) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for rel, priority, changefreq in pages:
        loc = f"{BASE_URL}/{rel}"
        lastmod = _lastmod(ROOT / rel)
        lines.append("  <url>")
        lines.append(f"    <loc>{escape(loc)}</loc>")
        lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append(f"    <changefreq>{changefreq}</changefreq>")
        lines.append(f"    <priority>{priority}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def _latest_brief_date():
    briefs = sorted(ROOT.glob("daily-brief-*.html"), reverse=True)
    if not briefs:
        return None, None
    m = re.search(r"(\d{4}-\d{2}-\d{2})", briefs[0].name)
    return briefs[0], (m.group(1) if m else None)


def build_rss(limit: int = 30) -> str:
    brief_file, date_str = _latest_brief_date()
    items = []
    data_file = DATA_DIR / "scored_news.json"
    if data_file.exists():
        try:
            payload = json.loads(data_file.read_text(encoding="utf-8"))
            items = payload.get("items", [])[:limit]
        except (json.JSONDecodeError, OSError):
            items = []

    now_rfc = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        "  <channel>",
        f"    <title>{escape(SITE_TITLE)}</title>",
        f"    <link>{BASE_URL}/</link>",
        f"    <description>{escape(SITE_DESC)}</description>",
        "    <language>zh-CN</language>",
        f"    <lastBuildDate>{now_rfc}</lastBuildDate>",
        f'    <atom:link href="{BASE_URL}/rss.xml" rel="self" type="application/rss+xml"/>',
    ]

    for it in items:
        title = it.get("title_zh") or it.get("title") or ""
        link = clean_link(it.get("link") or "") or f"{BASE_URL}/"
        summary = it.get("summary_zh") or ""
        why = it.get("why_important") or ""
        desc = summary + (f"<br/><br/><b>为什么重要：</b>{why}" if why else "")
        source = it.get("source_name") or ""
        if source:
            desc += f"<br/><i>来源：{escape(source)}</i>"
        out.append("    <item>")
        out.append(f"      <title>{escape(title)}</title>")
        out.append(f"      <link>{escape(link)}</link>")
        out.append(f'      <guid isPermaLink="true">{escape(link)}</guid>')
        out.append(f"      <description><![CDATA[{desc}]]></description>")
        if date_str:
            out.append(f"      <pubDate>{date_str} 08:00:00 +0800</pubDate>")
        out.append("    </item>")

    out.append("  </channel>")
    out.append("</rss>")
    return "\n".join(out) + "\n"


def build_robots() -> str:
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "\n"
        f"Sitemap: {BASE_URL}/sitemap.xml\n"
    )


def main():
    pages = collect_pages()
    (ROOT / "sitemap.xml").write_text(build_sitemap(pages), encoding="utf-8")
    (ROOT / "rss.xml").write_text(build_rss(), encoding="utf-8")
    (ROOT / "robots.txt").write_text(build_robots(), encoding="utf-8")

    print(f"[OK] sitemap.xml  {len(pages)} 个页面")
    print("[OK] rss.xml      最新一期日报条目")
    print("[OK] robots.txt   指向 sitemap")


if __name__ == "__main__":
    main()
