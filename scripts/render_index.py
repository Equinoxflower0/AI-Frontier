"""
render_index.py
================
AI Frontier · 首页渲染（v2 · 含 AI玩法实验室）

输出：index.html
"""
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _utf8  # noqa: F401
from floating_home import render_floating_home

INPUT_FILE = Path(__file__).parent / "data" / "scored_news.json"
PLAY_FILE  = Path(__file__).parent / "data" / "scored_play.json"
OUTPUT_FILE = Path(__file__).parent.parent / "index.html"

CATEGORY_META = {
    "大模型": {"color": "red",    "emoji": "🤖", "label": "大模型"},
    "开源":   {"color": "purple", "emoji": "💻", "label": "开源"},
    "论文":   {"color": "blue",   "emoji": "📚", "label": "论文"},
    "产业":   {"color": "green",  "emoji": "🏢", "label": "产业"},
    "工具":   {"color": "yellow", "emoji": "🛠️", "label": "工具"},
    "观点":   {"color": "pink",   "emoji": "💡", "label": "观点"},
    "综合":   {"color": "slate",  "emoji": "📰", "label": "综合"},
}

RELIAB_BADGE = {
    "S": {"color": "emerald", "label": "官方一手 · S级"},
    "A": {"color": "blue",    "label": "权威媒体 · A级"},
    "B": {"color": "amber",   "label": "技术社区 · B级"},
    "C": {"color": "slate",   "label": "自媒体 · C级"},
}


def esc(s):
    if not s:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def render_hero_card(item, rank):
    title = item.get("title_zh", item.get("title", ""))
    summary = item.get("summary_zh", "")
    cat = item.get("category", "综合")
    link = item.get("link", "#")
    source = item.get("source_name", "")
    meta = CATEGORY_META.get(cat, CATEGORY_META["综合"])
    color = meta["color"]
    grad = {
        "red":    "from-red-500 to-orange-500",
        "purple": "from-purple-500 to-pink-500",
        "blue":   "from-blue-500 to-cyan-500",
        "green":  "from-green-500 to-emerald-500",
        "yellow": "from-amber-500 to-yellow-500",
        "pink":   "from-pink-500 to-rose-500",
        "slate":  "from-slate-500 to-slate-400",
    }.get(color, "from-slate-500 to-slate-400")

    return f'''
    <a href="{esc(link)}" target="_blank" rel="noopener"
       class="bg-white rounded-xl border border-slate-200 overflow-hidden card-hover block">
      <div class="h-2 bg-gradient-to-r {grad}"></div>
      <div class="p-6">
        <div class="flex items-center gap-2 mb-3">
          <span class="bg-{color}-100 text-{color}-700 text-xs font-semibold px-2 py-1 rounded">{meta['emoji']} {cat}</span>
          <span class="text-xs text-slate-400">{esc(source)}</span>
        </div>
        <h3 class="font-bold text-lg mb-2 leading-snug text-slate-900">{esc(title)}</h3>
        <p class="text-sm text-slate-600 mb-4 leading-relaxed">{esc(summary[:110])}</p>
        <div class="flex items-center justify-between text-xs">
          <span class="text-slate-400">第 {rank} 名 · 点击阅读原文</span>
          <span class="text-blue-600 font-medium">详情 →</span>
        </div>
      </div>
    </a>'''


def render_feed_item(item):
    title = item.get("title_zh", item.get("title", ""))
    summary = item.get("summary_zh", "")
    cat = item.get("category", "综合")
    link = item.get("link", "#")
    source = item.get("source_name", "")
    score = item.get("score", 0)
    lang = item.get("source_lang", "zh")
    stype = item.get("source_type", "community")
    rel_tier = {"official": "S", "media": "A", "community": "B", "selfmedia": "C"}.get(stype, "B")
    meta = CATEGORY_META.get(cat, CATEGORY_META["综合"])
    color = meta["color"]
    lang_badge = '<span class="bg-slate-100 text-slate-600 text-xs px-2 py-0.5 rounded">EN</span>' if lang == "en" else ''
    rb = RELIAB_BADGE.get(rel_tier, RELIAB_BADGE["B"])
    rel_badge = f'<span class="bg-{rb["color"]}-50 text-{rb["color"]}-700 text-xs font-semibold px-2 py-0.5 rounded">{rb["label"]}</span>'

    pub = item.get("pubDate", "")
    date_disp = pub[5:7] + "-" + pub[8:10] if len(pub) >= 10 else "今天"
    day = pub[8:10] if len(pub) >= 10 else "—"

    return f'''
    <article class="bg-white border border-slate-200 rounded-lg p-5 card-hover feed-item"
             data-source-type="{stype}" data-category="{cat}">
      <div class="flex items-start gap-4">
        <div class="text-center shrink-0 w-14">
          <div class="text-2xl font-bold text-blue-600">{day}</div>
          <div class="text-xs text-slate-400">{esc(date_disp)}</div>
        </div>
        <div class="flex-1">
          <div class="flex items-center gap-2 mb-2 flex-wrap">
            <span class="bg-{color}-100 text-{color}-700 text-xs font-semibold px-2 py-0.5 rounded">{cat}</span>
            {rel_badge}
            {lang_badge}
            <span class="text-xs text-slate-400">{esc(source)}</span>
          </div>
          <h3 class="font-semibold mb-2 leading-snug">
            <a href="{esc(link)}" target="_blank" rel="noopener" class="text-slate-900 hover:text-blue-600">{esc(title)}</a>
          </h3>
          <p class="text-sm text-slate-600 mb-3">{esc(summary[:130])}</p>
          <div class="flex items-center gap-3 text-xs text-slate-500">
            <span>📌 重要性 {score:.1f}/10</span>
            <span>·</span>
            <a href="{esc(link)}" target="_blank" rel="noopener" class="text-blue-600 hover:underline">阅读原文 →</a>
          </div>
        </div>
      </div>
    </article>'''


def render_play_card(it):
    title = it.get("title_zh", "")[:30]
    summary = it.get("summary_zh", "")[:90]
    diff = int(it.get("difficulty", 3) or 3)
    copy = int(it.get("copyable_score", 3) or 3)
    time_min = it.get("time_estimate", "30min")
    score = float(it.get("playability_score", 6.0))
    link = it.get("link", "#")
    tools = it.get("tools", []) or []
    play_type = it.get("play_type", "tool_chain")
    src_tier = it.get("source_tier", "B")
    tier_color = {"S": "emerald", "A": "blue", "B": "amber", "C": "slate"}.get(src_tier, "amber")
    type_label = {
        "prompt": "💬 Prompt", "tool_chain": "🔗 工具链",
        "tool_workflow": "🧪 工作流", "runnable_demo": "🚀 在线", "tutorial": "📖 教程",
    }.get(play_type, "🧪 玩法")

    tools_html = "".join(
        '<span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] bg-slate-100 text-slate-600">' + esc(t) + '</span>'
        for t in tools[:3]
    )
    body = (
        '<a href="' + esc(link) + '" target="_blank" rel="noopener" '
        'class="group bg-white rounded-xl border border-slate-200 p-4 hover:border-indigo-300 hover:shadow-lg transition-all block">'
        '<div class="flex items-center gap-2 mb-2 text-[10px]">'
        '<span class="px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-700 font-semibold">' + type_label + '</span>'
        '<span class="px-1.5 py-0.5 rounded bg-' + tier_color + '-50 text-' + tier_color + '-700 font-semibold">' + src_tier + '级</span>'
        '<span class="ml-auto text-amber-600">🎯 ' + f"{score:.1f}" + '</span>'
        '</div>'
        '<h4 class="font-bold text-sm leading-snug mb-2 text-slate-900 group-hover:text-indigo-700 transition line-clamp-2">' + esc(title) + '</h4>'
        '<p class="text-xs text-slate-500 line-clamp-2 mb-3">' + esc(summary) + '</p>'
        '<div class="flex items-center gap-1.5 text-[10px]">'
        '<span class="text-amber-500">' + ("★" * diff + "☆" * (5 - diff)) + '</span>'
        '<span class="text-slate-400">⏱ ' + time_min + '</span>'
        '<span class="text-slate-400">📋 ' + str(copy) + '/5</span>'
        '</div>'
    )
    if tools_html:
        body += '<div class="flex gap-1 mt-2">' + tools_html + '</div>'
    body += '</a>'
    return body


def render_play_section(plays):
    if not plays:
        return ""
    plays_top = plays[:6]
    n_play = len(plays)
    n_demo = sum(1 for it in plays if it.get("play_type") == "runnable_demo")
    n_prompt = sum(1 for it in plays if it.get("play_type") == "prompt")
    avg_diff = sum(int(it.get("difficulty", 3) or 3) for it in plays) / len(plays) if plays else 3

    cards = "\n".join(render_play_card(it) for it in plays_top)

    return f'''
<!-- AI玩法实验室 -->
<section id="playground" class="bg-gradient-to-br from-indigo-50 via-white to-purple-50 border-y border-indigo-100">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
    <div class="flex items-end justify-between mb-8 flex-wrap gap-4">
      <div>
        <div class="text-sm text-indigo-600 font-semibold mb-1">PLAYGROUND</div>
        <h2 class="text-2xl sm:text-3xl font-bold mb-2">🎮 AI 玩法实验室</h2>
        <p class="text-slate-600 max-w-2xl text-sm">5 分钟能上手的 AI 玩法 · prompt 模板、工作流、可在线 Demo，看完就能试。</p>
      </div>
      <a href="playground.html" class="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-5 py-2.5 rounded-lg shadow transition">
        进入玩法实验室 →
      </a>
    </div>
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
      <div class="bg-white/80 backdrop-blur border border-indigo-100 rounded-xl p-4">
        <div class="text-2xl font-bold text-indigo-700">{n_play}</div>
        <div class="text-xs text-slate-500 mt-1">玩法项目</div>
      </div>
      <div class="bg-white/80 backdrop-blur border border-indigo-100 rounded-xl p-4">
        <div class="text-2xl font-bold text-indigo-700">{n_demo}</div>
        <div class="text-xs text-slate-500 mt-1">可立即试用</div>
      </div>
      <div class="bg-white/80 backdrop-blur border border-indigo-100 rounded-xl p-4">
        <div class="text-2xl font-bold text-indigo-700">{n_prompt}</div>
        <div class="text-xs text-slate-500 mt-1">Prompt 模板</div>
      </div>
      <div class="bg-white/80 backdrop-blur border border-indigo-100 rounded-xl p-4">
        <div class="text-2xl font-bold text-indigo-700">{avg_diff:.1f}</div>
        <div class="text-xs text-slate-500 mt-1">平均难度（越低越易）</div>
      </div>
    </div>
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">{cards}
    </div>
    <div class="text-center mt-6">
      <a href="playground.html" class="text-sm text-indigo-600 hover:text-indigo-700 font-medium border border-indigo-200 rounded-full px-6 py-2 hover:bg-indigo-50 transition inline-block">
        查看全部 {n_play} 个玩法 →
      </a>
    </div>
  </div>
</section>
'''


def render_html(items, date_str, plays=()):
    top3 = items[:3]
    feed = items

    cat_cnt = Counter(it.get("category", "综合") for it in items)
    total = len(items)
    cat_link_paper_open = "论文" if cat_cnt.get("论文", 0) > 0 else "开源" if cat_cnt.get("开源", 0) > 0 else "综合"

    nav_cards = ""
    for cat, meta in CATEGORY_META.items():
        n = cat_cnt.get(cat, 0)
        color = meta["color"]
        nav_cards += f'''
        <button onclick="applyCategory('{cat}'); document.getElementById('feed').scrollIntoView({{behavior:'smooth'}});" class="group bg-slate-50 hover:bg-{color}-50 border border-slate-200 hover:border-{color}-200 rounded-xl p-5 text-center transition cursor-pointer">
          <div class="w-12 h-12 mx-auto mb-3 rounded-lg bg-{color}-100 group-hover:bg-{color}-200 flex items-center justify-center transition">
            <span class="text-2xl">{meta['emoji']}</span>
          </div>
          <div class="font-semibold">{meta['label']}</div>
          <div class="text-xs text-slate-500 mt-1">{n} 条今日</div>
        </button>'''

    cat_buttons = ""
    for cat, meta in CATEGORY_META.items():
        n = cat_cnt.get(cat, 0)
        if n == 0:
            continue
        cat_buttons += (
            f'<button onclick="applyCategory(\'{cat}\')" data-value="{cat}" '
            f'class="cat-btn px-3 py-1.5 rounded-full bg-slate-100 text-slate-600 text-xs">'
            f'{meta["emoji"]} {meta["label"]} <span class="opacity-60">{n}</span></button>'
        )

    hero_cards = "\n".join(render_hero_card(it, i + 1) for i, it in enumerate(top3))
    feed_items = "\n".join(render_feed_item(it) for it in feed)
    play_section_html = render_play_section(plays)

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Frontier · 全球 AI 前沿咨询</title>
<meta name="description" content="每天 5 分钟，掌握全球 AI 前沿动态 + AI 玩法实验室。">
<script src="https://cdn.tailwindcss.com"></script>
<style>
  html {{ scroll-behavior: smooth; }}
  body {{ font-family: "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; }}
  .card-hover {{ transition: all .2s ease; }}
  .card-hover:hover {{ transform: translateY(-2px); box-shadow: 0 10px 30px -10px rgba(0,0,0,0.15); }}
</style>
</head>
<body class="bg-slate-50 text-slate-900">

<!-- 顶部导航 -->
<header class="bg-white/80 backdrop-blur-md border-b border-slate-200 sticky top-0 z-50">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="flex items-center justify-between h-16">
      <a href="index.html" class="flex items-center gap-2">
        <span class="text-2xl">🌐</span>
        <span class="font-bold text-lg">AI Frontier</span>
        <span class="text-xs text-slate-400 ml-2">| 全球AI前沿</span>
      </a>
      <nav class="hidden md:flex items-center gap-6 text-sm font-medium text-slate-600">
        <a href="#top" class="hover:text-blue-600">今日</a>
        <a href="playground.html" class="hover:text-indigo-600">🎮 玩法实验室</a>
        <a href="daily-brief-{date_str}.html" class="hover:text-blue-600">日报</a>
        <a href="#categories" class="hover:text-blue-600">板块</a>
        <a href="#feed" class="hover:text-blue-600">资讯流</a>
      </nav>
    </div>
  </div>
</header>

<!-- Hero -->
<section id="top" class="bg-gradient-to-br from-slate-900 via-blue-900 to-blue-700 text-white">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
    <div class="grid md:grid-cols-2 gap-10 items-center">
      <div>
        <div class="inline-flex items-center gap-2 bg-white/10 backdrop-blur px-3 py-1 rounded-full text-xs mb-6">
          <span class="w-2 h-2 bg-red-400 rounded-full"></span>
          <span>{date_str} · 已自动更新</span>
        </div>
        <h1 class="text-4xl sm:text-5xl font-bold leading-tight mb-4">每天 5 分钟<br>掌握全球 <span class="text-yellow-300">AI 前沿</span></h1>
        <p class="text-lg text-blue-100 mb-8 leading-relaxed">聚合全球顶尖 AI 信息源 + AI 玩法实验室 · 自动筛选 + 摘要 + 中英对照。</p>
        <div class="flex flex-wrap gap-3">
          <a href="#feed" class="bg-white text-blue-900 font-semibold px-6 py-3 rounded-lg hover:bg-blue-50 transition">浏览资讯 →</a>
          <a href="playground.html" class="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-6 py-3 rounded-lg transition">🎮 进入玩法实验室</a>
        </div>
      </div>
      <div class="grid grid-cols-2 gap-4">
        <a href="daily-brief-{date_str}.html" class="bg-white/10 backdrop-blur border border-white/20 rounded-xl p-5 hover:bg-white/20 transition group block">
          <div class="text-3xl font-bold">{total}</div>
          <div class="text-sm text-blue-100 mt-1">今日收录资讯</div>
          <div class="text-xs text-yellow-300 mt-2 opacity-0 group-hover:opacity-100 transition">查看完整日报 →</div>
        </a>
        <a href="daily-brief-{date_str}.html" class="bg-white/10 backdrop-blur border border-white/20 rounded-xl p-5 hover:bg-white/20 transition group block">
          <div class="text-3xl font-bold">{len(set(it.get("source_id") for it in items))}</div>
          <div class="text-sm text-blue-100 mt-1">活跃信息源</div>
        </a>
        <a href="daily-brief-{date_str}.html#cat-{cat_link_paper_open}" class="bg-white/10 backdrop-blur border border-white/20 rounded-xl p-5 hover:bg-white/20 transition group block">
          <div class="text-3xl font-bold">{cat_cnt.get("论文", 0) + cat_cnt.get("开源", 0)}</div>
          <div class="text-sm text-blue-100 mt-1">论文 + 开源</div>
        </a>
        <a href="daily-brief-{date_str}.html#cat-产业" class="bg-white/10 backdrop-blur border border-white/20 rounded-xl p-5 hover:bg-white/20 transition group block">
          <div class="text-3xl font-bold">{cat_cnt.get("产业", 0)}</div>
          <div class="text-sm text-blue-100 mt-1">产业大事</div>
        </a>
      </div>
    </div>
  </div>
</section>

<!-- 今日必看 TOP 3 -->
<section class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
  <div class="text-sm text-blue-600 font-semibold mb-1">TODAY</div>
  <h2 class="text-2xl sm:text-3xl font-bold mb-6">今日必看 TOP 3</h2>
  <div class="grid grid-cols-1 md:grid-cols-3 gap-5">{hero_cards}
  </div>
</section>

<!-- AI 玩法实验室 -->
{play_section_html}

<!-- 板块导航 -->
<section id="categories" class="bg-white border-y border-slate-200">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
    <div class="text-center mb-10">
      <div class="text-sm text-blue-600 font-semibold mb-1">CATEGORIES</div>
      <h2 class="text-2xl sm:text-3xl font-bold">六大板块，一站式跟进</h2>
      <p class="text-slate-500 mt-2 text-sm">点击任意板块 → 自动筛选并滚到资讯流</p>
    </div>
    <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">{nav_cards}
    </div>
  </div>
</section>

<!-- 完整资讯流 -->
<section id="feed" class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
  <div class="flex items-end justify-between mb-4">
    <div>
      <div class="text-sm text-blue-600 font-semibold mb-1">FEED</div>
      <h2 class="text-2xl sm:text-3xl font-bold">完整资讯流</h2>
    </div>
    <a href="daily-brief-{date_str}.html" class="text-sm text-blue-600 hover:underline">看完整日报 →</a>
  </div>

  <!-- 板块筛选 + 可信度筛选 -->
  <div class="bg-white border border-slate-200 rounded-xl p-4 mb-6 space-y-3">
    <div class="flex items-center gap-2 flex-wrap text-sm">
      <span class="font-semibold text-slate-700 mr-2">板块：</span>
      <button onclick="applyCategory('all')" data-value="all" class="cat-btn px-3 py-1.5 rounded-full bg-blue-600 text-white text-xs">全部</button>
      {cat_buttons}
    </div>
    <div class="flex items-center gap-2 flex-wrap text-sm">
      <span class="font-semibold text-slate-700 mr-2">可信度：</span>
      <button onclick="filterRel('all')" data-rel="all" class="rel-btn px-3 py-1.5 rounded-full bg-blue-600 text-white text-xs">全部</button>
      <button onclick="filterRel('official')" data-rel="official" class="rel-btn px-3 py-1.5 rounded-full bg-slate-100 text-slate-600 text-xs">🟢 官方一手</button>
      <button onclick="filterRel('media')" data-rel="media" class="rel-btn px-3 py-1.5 rounded-full bg-slate-100 text-slate-600 text-xs">🔵 权威媒体</button>
      <button onclick="filterRel('community')" data-rel="community" class="rel-btn px-3 py-1.5 rounded-full bg-slate-100 text-slate-600 text-xs">🟡 技术社区</button>
      <button onclick="filterRel('selfmedia')" data-rel="selfmedia" class="rel-btn px-3 py-1.5 rounded-full bg-slate-100 text-slate-600 text-xs">⚪ 自媒体</button>
    </div>
    <div class="text-xs text-slate-400">
      当前显示 <span id="showCount" class="font-bold text-slate-900">{total}</span> 条 / 共 {total} 条
    </div>
  </div>

  <div class="space-y-3">{feed_items}
  </div>
</section>

<!-- 底部 -->
<footer class="bg-slate-900 text-slate-400 mt-20">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 text-center text-sm">
    <p>🌐 AI Frontier · 全球 AI 前沿咨询 · v2.0</p>
    <p class="mt-2 text-xs opacity-60">每天 08:00 自动更新 · DeepSeek LLM 智能摘要 · 玩法 + 资讯</p>
  </div>
</footer>

<script>
var activeCat = 'all', activeRel = 'all';
function applyFilter() {{
  var items = document.querySelectorAll('.feed-item');
  var n = 0;
  items.forEach(function(item) {{
    var cat = item.getAttribute('data-category');
    var st  = item.getAttribute('data-source-type');
    var match = (activeCat === 'all' || cat === activeCat) &&
                (activeRel === 'all' || st === activeRel);
    item.style.display = match ? '' : 'none';
    if (match) n++;
  }});
  document.getElementById('showCount').textContent = n;
}}
function applyCategory(c) {{
  activeCat = c;
  document.querySelectorAll('.cat-btn').forEach(function(b){{
    b.className = b.className.replace(/bg-blue-600 text-white/g, '').trim();
    if (b.getAttribute('data-value') === c) {{ b.classList.add('bg-blue-600','text-white'); }}
  }});
  applyFilter();
}}
function filterRel(t) {{
  activeRel = t;
  document.querySelectorAll('.rel-btn').forEach(function(b){{
    b.className = b.className.replace(/bg-blue-600 text-white/g, '').trim();
    if (b.getAttribute('data-rel') === t) {{ b.classList.add('bg-blue-600','text-white'); }}
  }});
  applyFilter();
}}
</script>

{render_floating_home(href="#top", label="返回顶部")}
</body>
</html>
'''


def main():
    if not INPUT_FILE.exists():
        print(f"[ERROR] {INPUT_FILE} 不存在")
        return

    with open(INPUT_FILE, encoding="utf-8") as f:
        items = json.load(f).get("items", [])
    date_str = datetime.now().strftime("%Y-%m-%d")

    plays = []
    if PLAY_FILE.exists():
        try:
            plays = json.load(open(PLAY_FILE, encoding="utf-8")).get("items", [])
        except Exception:
            plays = []

    print(f"=== AI Frontier · 生成首页 === {date_str}")
    print(f"   资讯 {len(items)} 条  玩法 {len(plays)} 条")
    html = render_html(items, date_str, plays)
    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"   OK {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
