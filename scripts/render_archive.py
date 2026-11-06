"""
render_archive.py
=================
AI Frontier · 往期资讯归档页渲染

扫描根目录下的 daily-brief-YYYY-MM-DD.html，提取：
  - 日期 / 条数 / 信息源数
  - 分类分布
  - 今日 TOP 3 标题

输出：archive.html（按月份分组 + 月份筛选 + 关键词搜索）

设计要点：
  - 纯静态，无 fetch/XHR，file:// 双击也能打开
  - 不依赖额外数据文件，历史日报即使没有 JSON 也能归档
  - 新生成的日报只要文件名符合规范就会自动进入归档
"""

import html
import re
import sys
from collections import Counter, OrderedDict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _utf8  # noqa: F401
from floating_home import render_floating_home

ROOT = Path(__file__).parent.parent
OUTPUT_FILE = ROOT / "archive.html"
PATTERN = re.compile(r"^daily-brief-(\d{4}-\d{2}-\d{2})\.html$")

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

CATEGORY_META = {
    "大模型": {"color": "red",    "emoji": "🤖", "label": "大模型"},
    "开源":   {"color": "purple", "emoji": "💻", "label": "开源"},
    "论文":   {"color": "blue",   "emoji": "📚", "label": "论文"},
    "产业":   {"color": "green",  "emoji": "🏢", "label": "产业"},
    "工具":   {"color": "yellow", "emoji": "🛠️", "label": "工具"},
    "观点":   {"color": "pink",   "emoji": "💡", "label": "观点"},
    "综合":   {"color": "slate",  "emoji": "📰", "label": "综合"},
}

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def clean_text(s: str) -> str:
    """去标签、反转义、压缩空白。"""
    s = TAG_RE.sub("", s or "")
    s = html.unescape(s)
    return WS_RE.sub(" ", s).strip()


def extract_total(doc: str) -> int:
    m = re.search(r"全球\s*AI\s*前沿\s*Top\s*(\d+)", doc)
    if m:
        return int(m.group(1))
    # 兜底：数条目卡片
    return len(re.findall(r'<article class="bg-white rounded-xl border border-slate-200 p-5', doc))


def extract_source_count(doc: str) -> int:
    m = re.search(r"从\s*(\d+)\s*个权威源", doc)
    return int(m.group(1)) if m else 0


def extract_categories(doc: str) -> list:
    """返回 [(分类, 条数), ...]，保持日报中的原顺序。"""
    out = []
    for m in re.finditer(
        r'<section id="cat-([^"]+)".*?<span class="text-xs text-slate-400">(\d+)\s*条</span>',
        doc,
        re.S,
    ):
        out.append((html.unescape(m.group(1)), int(m.group(2))))
    return out


def extract_top_titles(doc: str, limit: int = 3) -> list:
    """提取 TOP3 标题（TOP3 卡片的 h3 类名不含 hover:）。"""
    titles = []
    for m in re.finditer(
        r'<h3 class="text-lg font-bold mb-2 leading-snug"><a[^>]*>(.*?)</a></h3>',
        doc,
        re.S,
    ):
        t = clean_text(m.group(1))
        if t:
            titles.append(t)
        if len(titles) >= limit:
            break
    if titles:
        return titles
    # 兜底：任意 h3 标题
    for m in re.finditer(r"<h3[^>]*>(.*?)</h3>", doc, re.S):
        t = clean_text(m.group(1))
        if t:
            titles.append(t)
        if len(titles) >= limit:
            break
    return titles


def parse_brief(path: Path):
    try:
        doc = path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  [WARN] 跳过 {path.name}：{e}")
        return None

    date_str = PATTERN.match(path.name).group(1)
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    total = extract_total(doc)

    return {
        "date": date_str,
        "month": date_str[:7],
        "day": dt.strftime("%d"),
        "day_label": f"{dt.month}月{dt.day:02d}日",
        "weekday": WEEKDAYS[dt.weekday()],
        "total": total,
        "sources": extract_source_count(doc),
        "categories": extract_categories(doc),
        "titles": extract_top_titles(doc),
        "href": path.name,
        "is_latest": False,
        "search": (date_str + " " + " ".join(extract_top_titles(doc, 5))).lower(),
    }


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def render_category_chips(categories) -> str:
    chips = ""
    for cat, n in categories:
        meta = CATEGORY_META.get(cat, CATEGORY_META["综合"])
        c = meta["color"]
        chips += (
            f'<span class="inline-flex items-center gap-1 bg-{c}-50 text-{c}-700 '
            f'border border-{c}-100 text-xs px-2 py-0.5 rounded-full">'
            f'{meta["emoji"]} {esc(meta["label"])} <span class="opacity-60">{n}</span></span>'
        )
    return chips


def render_titles(titles, href) -> str:
    if not titles:
        return '<p class="text-sm text-slate-400">本期暂无标题摘要</p>'
    lis = ""
    for i, t in enumerate(titles, 1):
        lis += (
            f'<li class="flex gap-2 items-start">'
            f'<span class="text-xs font-bold text-slate-400 mt-0.5 shrink-0">{i}</span>'
            f'<a href="{esc(href)}" class="text-sm text-slate-600 hover:text-blue-600 leading-snug">'
            f'{esc(t)}</a></li>'
        )
    return f'<ul class="space-y-1.5">{lis}</ul>'


def render_card(item) -> str:
    latest_badge = (
        '<span class="text-xs font-semibold text-white bg-blue-600 px-2 py-0.5 rounded-full">最新</span>'
        if item["is_latest"] else ""
    )
    return f'''
      <article class="day-card bg-white rounded-xl border border-slate-200 p-5 sm:p-6 transition-all duration-200"
               data-month="{item["month"]}" data-search="{esc(item["search"])}">
        <div class="flex gap-4 sm:gap-6">
          <div class="shrink-0 w-14 sm:w-16 text-center pt-1">
            <div class="text-2xl sm:text-3xl font-bold text-slate-900 leading-none">{item["day"]}</div>
            <div class="text-xs text-slate-400 mt-1.5">{item["weekday"]}</div>
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap mb-2">
              <a href="{esc(item["href"])}" class="font-bold text-slate-900 hover:text-blue-600">{item["day_label"]} 简报</a>
              {latest_badge}
              <span class="text-xs text-slate-500">{item["total"]} 条</span>
              <span class="text-xs text-slate-300">·</span>
              <span class="text-xs text-slate-500">{item["sources"]} 个源</span>
            </div>
            <div class="flex items-center gap-1.5 flex-wrap mb-3">{render_category_chips(item["categories"])}</div>
            {render_titles(item["titles"], item["href"])}
          </div>
          <div class="hidden sm:flex items-center">
            <a href="{esc(item["href"])}"
               class="whitespace-nowrap text-sm font-medium text-blue-600 hover:text-blue-700 border border-blue-200 hover:border-blue-300 rounded-lg px-3 py-2 transition">
              阅读 →
            </a>
          </div>
        </div>
      </article>'''


def render_html(items) -> str:
    total_issues = len(items)
    total_news = sum(i["total"] for i in items)
    month_counts = Counter(i["month"] for i in items)
    months = sorted(month_counts, reverse=True)

    def fmt_month(m: str) -> str:
        y, mm = m.split("-")
        return f"{y} 年 {int(mm)} 月"

    first_month, last_month = months[-1], months[0]
    span_text = (
        fmt_month(first_month) if len(months) == 1
        else f"{fmt_month(first_month)} — {fmt_month(last_month)}"
    )

    # 月份筛选按钮
    filters = (
        f'<button data-month="all" class="month-btn px-3.5 py-1.5 rounded-full text-sm font-medium '
        f'bg-blue-600 text-white transition">全部 <span class="opacity-70">{total_issues}</span></button>'
    )
    for m in months:
        y, mm = m.split("-")
        filters += (
            f'<button data-month="{m}" class="month-btn px-3.5 py-1.5 rounded-full text-sm font-medium '
            f'bg-white text-slate-600 border border-slate-200 hover:border-blue-300 hover:text-blue-600 transition">'
            f'{y} 年 {int(mm)} 月 <span class="opacity-60">{month_counts[m]}</span></button>'
        )

    # 按月分组
    blocks = ""
    for m in months:
        group = [i for i in items if i["month"] == m]
        y, mm = m.split("-")
        cards = "\n".join(render_card(i) for i in group)
        blocks += f'''
      <section class="month-block" data-month="{m}">
        <div class="flex items-center gap-3 mt-10 mb-4 first:mt-0">
          <h2 class="text-lg font-bold text-slate-900">{y} 年 {int(mm)} 月</h2>
          <span class="text-xs text-slate-400">{len(group)} 期</span>
          <div class="flex-1 h-px bg-slate-200"></div>
        </div>
        <div class="space-y-4">{cards}</div>
      </section>'''

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>往期资讯归档 · AI Frontier</title>
<meta name="description" content="AI Frontier 往期日报归档：按月份浏览历史 AI 前沿资讯，共 {total_issues} 期、{total_news} 条。">
<link rel="stylesheet" href="assets/tailwind.css">
<style>
  body {{ font-family: "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; }}
  .day-card:hover {{ transform: translateY(-2px); box-shadow: 0 10px 30px -12px rgba(15,23,42,.18); border-color: #cbd5e1; }}
</style>
</head>
<body class="bg-slate-50 text-slate-900">

<!-- 顶部导航 -->
<header class="bg-white/80 backdrop-blur-md border-b border-slate-200 sticky top-0 z-50">
  <div class="max-w-6xl mx-auto px-4 sm:px-6">
    <div class="flex items-center justify-between h-16">
      <a href="index.html" class="flex items-center gap-2">
        <span class="text-2xl">🌐</span>
        <span class="font-bold text-lg">AI Frontier</span>
        <span class="text-xs text-slate-400 ml-2 hidden sm:inline">| 全球AI前沿</span>
      </a>
      <nav class="hidden md:flex items-center gap-6 text-sm font-medium text-slate-600">
        <a href="index.html" class="hover:text-blue-600">今日</a>
        <a href="archive.html" class="text-blue-600 border-b-2 border-blue-500 pb-0.5">📅 往期</a>
        <a href="playground.html" class="hover:text-indigo-600">🎮 玩法实验室</a>
        <a href="tutorials/index.html" class="hover:text-indigo-600">📚 全部教程</a>
      </nav>
    </div>
  </div>
</header>

<!-- Hero -->
<section class="bg-gradient-to-br from-slate-900 via-blue-900 to-blue-700 text-white">
  <div class="max-w-6xl mx-auto px-4 sm:px-6 py-12">
    <div class="text-xs tracking-widest text-blue-300 mb-3">ARCHIVE</div>
    <h1 class="text-3xl sm:text-4xl font-bold mb-3">📅 往期资讯</h1>
    <p class="text-blue-100 text-sm mb-7">共 <strong class="text-white">{total_issues}</strong> 期 · 累计 <strong class="text-white">{total_news}</strong> 条 · 覆盖 {span_text}</p>
    <div class="max-w-md">
      <div class="relative">
        <svg class="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-4.35-4.35M17 11a6 6 0 11-12 0 6 6 0 0112 0z"/>
        </svg>
        <input id="q" type="text" placeholder="搜索日期或标题关键词…"
               class="w-full bg-white text-slate-900 placeholder-slate-400 text-sm pl-10 pr-4 py-2.5 rounded-lg border border-white/20 focus:outline-none focus:ring-2 focus:ring-blue-400">
      </div>
    </div>
  </div>
</section>

<main class="max-w-6xl mx-auto px-4 sm:px-6 py-8">

  <!-- 筛选 -->
  <div class="flex flex-wrap items-center gap-2 mb-2">
    {filters}
    <div class="ml-auto text-xs text-slate-400">共 <span id="countHint">{total_issues}</span> 期</div>
  </div>

  <!-- 列表 -->
  <div id="list">{blocks}
  </div>

  <!-- 空状态 -->
  <div id="empty" class="hidden text-center py-20">
    <div class="text-4xl mb-3">🔍</div>
    <p class="text-slate-600 font-medium">没有找到匹配的日报</p>
    <p class="text-sm text-slate-400 mt-1">换个关键词，或点「全部」查看所有往期</p>
  </div>

</main>

<footer class="border-t border-slate-200 bg-white">
  <div class="max-w-6xl mx-auto px-4 py-8 text-center text-xs text-slate-400">
    AI Frontier · 往期资讯归档 · 数据来自公开 RSS 源，每日自动更新
  </div>
</footer>

{render_floating_home("index.html", "返回首页")}

<script>
(function () {{
  var input = document.getElementById('q');
  var buttons = Array.prototype.slice.call(document.querySelectorAll('.month-btn'));
  var cards = Array.prototype.slice.call(document.querySelectorAll('.day-card'));
  var blocks = Array.prototype.slice.call(document.querySelectorAll('.month-block'));
  var empty = document.getElementById('empty');
  var hint = document.getElementById('countHint');
  var month = 'all';

  function apply() {{
    var kw = (input.value || '').trim().toLowerCase();
    var shown = 0;

    cards.forEach(function (card) {{
      var okMonth = (month === 'all') || (card.getAttribute('data-month') === month);
      var okKw = !kw || (card.getAttribute('data-search') || '').indexOf(kw) !== -1;
      var visible = okMonth && okKw;
      card.style.display = visible ? '' : 'none';
      if (visible) shown++;
    }});

    blocks.forEach(function (block) {{
      var any = block.querySelectorAll('.day-card:not([style*="display: none"])').length;
      block.style.display = any ? '' : 'none';
    }});

    empty.classList.toggle('hidden', shown !== 0);
    hint.textContent = shown;
  }}

  buttons.forEach(function (btn) {{
    btn.addEventListener('click', function () {{
      month = btn.getAttribute('data-month');
      buttons.forEach(function (b) {{
        var active = b === btn;
        b.className = 'month-btn px-3.5 py-1.5 rounded-full text-sm font-medium transition ' +
          (active
            ? 'bg-blue-600 text-white'
            : 'bg-white text-slate-600 border border-slate-200 hover:border-blue-300 hover:text-blue-600');
      }});
      apply();
    }});
  }});

  input.addEventListener('input', apply);
  apply();
}})();
</script>
</body>
</html>'''


def main():
    files = sorted(
        (p for p in ROOT.glob("daily-brief-*.html") if PATTERN.match(p.name)),
        key=lambda p: p.name,
        reverse=True,
    )
    print(f"=== AI Frontier · 渲染往期归档 ===")
    if not files:
        print("[WARN] 没有找到任何 daily-brief-*.html，生成空归档页")

    items = [it for it in (parse_brief(p) for p in files) if it]
    if items:
        items[0]["is_latest"] = True

    OUTPUT_FILE.write_text(render_html(items), encoding="utf-8")
    print(f"   归档期数：{len(items)}")
    print(f"   累计资讯：{sum(i['total'] for i in items)} 条")
    print(f"   OK {OUTPUT_FILE.name} · {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
