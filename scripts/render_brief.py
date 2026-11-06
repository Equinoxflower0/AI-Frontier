"""
render_brief.py
===============
全球 AI 前沿资讯网站 - 日报渲染器 (v1)

输入：scripts/data/scored_news.json
输出：daily-brief-YYYY-MM-DD.html（自动按当天日期命名）

使用：
  python render_brief.py
  python render_brief.py --top 15 --output daily-brief.html
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _utf8  # noqa: F401  —— 强制 UTF-8 输出，防止 GBK 控制台崩溃
from floating_home import render_floating_home

from sources_config import reliability_of

INPUT_FILE = Path(__file__).parent / "data" / "scored_news.json"
DEFAULT_OUTPUT = Path(__file__).parent.parent / "daily-brief-{date}.html"

CATEGORY_META = {
    "大模型": {"color": "red",    "emoji": "🤖", "label": "大模型动态"},
    "开源":   {"color": "purple", "emoji": "💻", "label": "开源生态"},
    "论文":   {"color": "blue",   "emoji": "📚", "label": "学术前沿"},
    "产业":   {"color": "green",  "emoji": "🏢", "label": "产业动态"},
    "工具":   {"color": "yellow", "emoji": "🛠️", "label": "工具与产品"},
    "观点":   {"color": "pink",   "emoji": "💡", "label": "观点评论"},
    "综合":   {"color": "slate",  "emoji": "📰", "label": "综合资讯"},
}

# 可信度徽章颜色映射（tailwind 类名需静态展开）
RELIABILITY_BADGE = {
    "official":  "bg-emerald-100 text-emerald-700",
    "media":     "bg-blue-100 text-blue-700",
    "community": "bg-amber-100 text-amber-700",
    "selfmedia": "bg-slate-200 text-slate-600",
}


def reliability_badge_html(source_type: str) -> str:
    """生成可信度徽章"""
    rel = reliability_of(source_type)
    cls = RELIABILITY_BADGE.get(source_type, RELIABILITY_BADGE["selfmedia"])
    return (f'<span class="{cls} text-xs font-semibold px-2 py-0.5 rounded" '
            f'title="{rel["desc"]}">{rel["emoji"]} {rel["label"]} · {rel["level"]}级</span>')


def score_bar_html(score: float) -> str:
    pct = min(100, max(0, int(score * 10)))
    color = "#ef4444" if score >= 8 else "#f59e0b" if score >= 6 else "#94a3b8"
    return f'''
    <div class="flex items-center gap-2">
      <div class="w-20 h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div style="width:{pct}%;background:{color}" class="h-full rounded-full"></div>
      </div>
      <span class="text-xs font-bold" style="color:{color}">{score:.1f}</span>
    </div>'''


def render_item(item: dict, rank: int = None) -> str:
    title_zh = item.get("title_zh", item.get("title", ""))
    summary = item.get("summary_zh", "")
    why = item.get("why_important", "")
    score = item.get("score", 0)
    link = item.get("link", "#")
    cat = item.get("category", "综合")
    source = item.get("source_name", "")
    lang = item.get("source_lang", "zh")
    pub = item.get("pubDate", "")
    stype = item.get("source_type", "selfmedia")

    meta_color = CATEGORY_META.get(cat, CATEGORY_META["综合"])["color"]
    lang_badge = f'<span class="bg-slate-100 text-slate-600 text-xs px-2 py-0.5 rounded">EN</span>' if lang == "en" else ''
    rel_badge = reliability_badge_html(stype)

    why_html = f'''
      <p class="text-sm text-slate-700 leading-relaxed mb-3 mt-2">
        <strong class="text-slate-900">为什么重要：</strong>{why}
      </p>''' if why else ''

    pub_short = pub[:16] if pub else "今日"

    return f'''
    <article class="bg-white rounded-xl border border-slate-200 p-5 hover:border-{meta_color}-300 transition">
      <div class="flex items-start justify-between mb-3 gap-4">
        <div class="flex items-center gap-2 flex-wrap">
          <span class="bg-{meta_color}-100 text-{meta_color}-700 text-xs font-semibold px-2 py-0.5 rounded">{cat}</span>
          {rel_badge}
          {lang_badge}
          <span class="text-xs text-slate-400">{source} · {pub_short}</span>
        </div>
        {score_bar_html(score)}
      </div>
      <h3 class="text-lg font-bold mb-2 leading-snug hover:text-blue-600">
        <a href="{link}" target="_blank" rel="noopener">{title_zh}</a>
      </h3>
      <p class="text-sm text-slate-600 leading-relaxed">{summary}</p>
      {why_html}
    </article>'''


def render_category_section(cat: str, items: list) -> str:
    if not items:
        return ""
    meta = CATEGORY_META.get(cat, CATEGORY_META["综合"])
    color = meta["color"]
    items_html = "\n".join(render_item(it) for it in items)
    return f'''
    <section id="cat-{cat}" class="mb-10 scroll-mt-20">
      <div class="flex items-center gap-3 mb-5">
        <div class="w-1.5 h-6 bg-{color}-500 rounded"></div>
        <h2 class="text-xl font-bold">{meta["emoji"]} {meta["label"]}</h2>
        <span class="text-xs text-slate-400">{len(items)} 条</span>
      </div>
      <div class="space-y-4">{items_html}</div>
    </section>'''


def render_html(items: list, date_str: str) -> str:
    total = len(items)
    by_cat = {}
    for it in items:
        c = it.get("category", "综合")
        by_cat.setdefault(c, []).append(it)

    top3 = items[:3]
    top10 = items[:10]

    speed_html = "\n".join(
        f'<li><strong>{i+1}.</strong> <a href="{it.get("link","#")}" class="text-slate-700 hover:text-blue-600">{it.get("title_zh", it.get("title",""))[:50]}…</a></li>'
        for i, it in enumerate(top10)
    )

    sections_html = "\n".join(render_category_section(c, items) for c, items in by_cat.items())

    # TOP 3 大卡片
    top3_html = ""
    for i, it in enumerate(top3):
        title_zh = it.get("title_zh", it.get("title", ""))
        summary = it.get("summary_zh", "")
        cat = it.get("category", "综合")
        score = it.get("score", 0)
        link = it.get("link", "#")
        meta = CATEGORY_META.get(cat, CATEGORY_META["综合"])
        top3_html += f'''
      <article class="bg-white rounded-xl border border-slate-200 overflow-hidden hover:shadow-lg transition">
        <div class="h-2 bg-gradient-to-r from-{meta['color']}-500 to-{meta['color']}-300"></div>
        <div class="p-6">
          <div class="flex items-center justify-between mb-3">
            <span class="bg-{meta['color']}-100 text-{meta['color']}-700 text-xs font-semibold px-2 py-1 rounded">第 {i+1} 名 · {cat}</span>
            {score_bar_html(score)}
          </div>
          <h3 class="text-lg font-bold mb-2 leading-snug"><a href="{link}" target="_blank" rel="noopener nofollow">{title_zh}</a></h3>
          <p class="text-sm text-slate-600">{summary[:120]}…</p>
        </div>
      </article>'''

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{date_str} 今日 AI 简报 · AI Frontier</title>
<link rel="stylesheet" href="assets/tailwind.css">
<style>
  body {{ font-family: "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; }}
  article:hover {{ transform: translateY(-1px); transition: all 0.2s; }}
</style>
</head>
<body class="bg-slate-50">

<header class="bg-white border-b border-slate-200">
  <div class="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
    <a href="index.html" class="flex items-center gap-2 text-slate-600 hover:text-blue-600">
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
      <span class="text-sm">返回首页</span>
    </a>
    <div class="flex items-center gap-4">
      <a href="archive.html" class="text-sm text-slate-600 hover:text-blue-600">📅 往期资讯</a>
      <div class="text-sm text-slate-500">{date_str} · 周{datetime.strptime(date_str, "%Y-%m-%d").weekday()+1 if False else "—"}</div>
    </div>
  </div>
</header>

<section class="bg-gradient-to-br from-slate-900 via-blue-900 to-blue-700 text-white">
  <div class="max-w-4xl mx-auto px-4 py-12">
    <div class="text-sm text-blue-200 mb-2">每日 AI 简报 · AI Frontier</div>
    <h1 class="text-3xl sm:text-4xl font-bold mb-3">{date_str}<br>全球 AI 前沿 Top {total}</h1>
    <p class="text-blue-100 text-sm">从 {len(set(it.get("source_id","") for it in items))} 个权威源筛选 · 自动评分 · 约 5 分钟读完</p>
  </div>
</section>

<main class="max-w-4xl mx-auto px-4 py-10">

  <!-- 一分钟速览 -->
  <div class="bg-white rounded-xl border border-slate-200 p-6 mb-8">
    <h2 class="font-bold mb-4 text-lg">⚡ 一分钟速览</h2>
    <ol class="space-y-2 text-sm">
      {speed_html}
    </ol>
  </div>

  <!-- TOP 3 -->
  <div class="mb-12">
    <div class="flex items-center gap-3 mb-5">
      <div class="w-1.5 h-6 bg-yellow-500 rounded"></div>
      <h2 class="text-xl font-bold">⭐ 今日必看 TOP 3</h2>
    </div>
    <div class="grid md:grid-cols-3 gap-4">{top3_html}
    </div>
  </div>

  <!-- 按分类 -->
  {sections_html}

  <!-- 结尾 -->
  <div class="bg-white rounded-xl border border-slate-200 p-6 text-center mt-12">
    <p class="text-sm text-slate-600 mb-4">
      📮 <a href="#subscribe" class="text-blue-600 hover:underline">订阅每日 AI 简报</a>，每天 8 点送达邮箱。
    </p>
    <div class="flex justify-center gap-4 text-xs text-slate-500">
      <a href="#" class="hover:text-blue-600">分享</a>
      <span>·</span>
      <a href="#" class="hover:text-blue-600">反馈</a>
      <span>·</span>
      <a href="#" class="hover:text-blue-600">往期回顾</a>
    </div>
  </div>

</main>

<footer class="bg-slate-900 text-slate-400 py-8 mt-12">
  <div class="max-w-4xl mx-auto px-4 text-center text-xs">
    © 2026 AI Frontier · 内容来源：Unite.AI / AI 科技评论 / 量子位 / MIT Tech Review 等
  </div>
</footer>

{render_floating_home("index.html", "返回首页")}

</body>
</html>'''
    return html


def main():
    if not INPUT_FILE.exists():
        print(f"❌ 输入文件不存在：{INPUT_FILE}")
        print("请先运行：python fetch_ai_news.py && python score_and_summarize.py")
        return

    with open(INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("items", [])
    date_str = datetime.now().strftime("%Y-%m-%d")
    output = Path(__file__).parent.parent / f"daily-brief-{date_str}.html"

    print("=" * 70)
    print(f"AI Frontier · 渲染日报 · {date_str}")
    print("=" * 70)
    print(f"📥 加载 {len(items)} 条评分后资讯")

    html = render_html(items, date_str)
    output.write_text(html, encoding="utf-8")

    print(f"✅ 已写入 {output}")
    print(f"   文件大小：{output.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()