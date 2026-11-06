"""
render_playground.py
====================
AI玩法实验室 - 渲染脚本

输出 playground.html：
  - Hero 区（标题 + 实时统计）
  - 筛选区（玩法类型 / 难度 / 可信度 / 复制度）
  - 玩法卡片网格（按"可玩性 + 可信度"排序）
  - 每张卡片突出：难度★、时间⏱、工具、复制度、立即打开按钮
"""

import json
import re
import sys
from datetime import datetime
from collections import Counter
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).parent))
import _utf8  # noqa: F401

from floating_home import render_floating_home

INPUT_FILE = _Path(__file__).parent / "data" / "scored_play.json"
OUTPUT_FILE = _Path(__file__).parent.parent / "playground.html"


PLAY_TYPE_META = {
    "prompt":         {"color": "indigo",  "emoji": "\U0001f4ac", "label": "Prompt 模板",     "desc": "复制即可用"},
    "tool_workflow":  {"color": "purple",  "emoji": "\U0001f9ed", "label": "工作流",          "desc": "组合多个工具"},
    "tool_chain":     {"color": "cyan",    "emoji": "\U0001f517", "label": "工具链",          "desc": "多个工具组合"},
    "runnable_demo":  {"color": "emerald", "emoji": "\U0001f680", "label": "可立即试用",      "desc": "一键跑起来"},
    "tutorial":       {"color": "amber",   "emoji": "\U0001f4d6", "label": "教程指引",        "desc": "步骤化教学"},
}


# ============================================================
# HTML 工具
# ============================================================

def _esc(s) -> str:
    """HTML 转义"""
    if not s:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _stars(n: int, max_n: int = 5) -> str:
    n = max(0, min(max_n, int(n or 0)))
    return "\u2605" * n + "\u2606" * (max_n - n)


def difficulty_badge(diff: int) -> str:
    """难度徽章"""
    diff = max(1, min(5, int(diff or 3)))
    color_map = {5: "emerald", 4: "lime", 3: "amber", 2: "orange", 1: "rose"}
    label_map = {5: "0 基础", 4: "零代码", 3: "需环境", 2: "需配置", 1: "需工程"}
    color = color_map.get(diff, "slate")
    label = label_map.get(diff, "")
    return (
        f'<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold '
        f'bg-{color}-100 text-{color}-700">'
        f'<span class="text-amber-500">{_stars(diff)}</span>'
        f'<span>{label}</span></span>'
    )


def tier_badge(item: dict) -> str:
    src = item.get("source_label", "")
    tier = item.get("source_tier", "")
    color_map = {"S": "emerald", "A": "blue", "B": "amber", "C": "slate"}
    color = color_map.get(tier, "slate")
    # v4 新增：国内源额外标"国内"红章
    domestic_flag = ""
    if item.get("is_domestic") or item.get("source_id", "").endswith("-play"):
        if not any(x in item.get("source_id", "") for x in ["github-play", "hf-space", "ph-ai", "reddit"]):
            domestic_flag = (
                f' <span class="inline-flex items-center px-1.5 py-0.5 rounded text-xs '
                f'bg-red-50 text-red-600 border border-red-200">国内</span>'
            )
    return (
        f'<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold '
        f'bg-{color}-50 text-{color}-700 border border-{color}-200">'
        f'{src} \u00b7 {tier}级</span>'
        f'{domestic_flag}'
    )


def play_type_badge(pt: str) -> str:
    m = PLAY_TYPE_META.get(pt, PLAY_TYPE_META["tool_chain"])
    return (
        f'<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold '
        f'bg-{m["color"]}-100 text-{m["color"]}-700">'
        f'{m["emoji"]} {m["label"]}</span>'
    )


def tools_badges(tools: list) -> str:
    if not tools or tools == ["未标注"]:
        return ""
    html = "".join(
        f'<span class="inline-flex items-center px-1.5 py-0.5 rounded text-xs '
        f'bg-slate-100 text-slate-600">{_esc(t)}</span>'
        for t in tools[:4]
    )
    if len(tools) > 4:
        html += f'<span class="text-xs text-slate-400">+{len(tools) - 4}</span>'
    return html


# ============================================================
# 卡片
# ============================================================

def render_card(item: dict, idx: int, tutorial_url: str = "") -> str:
    """玩法卡片（tutorial_url 不为空时显示「查看教程+原文」双按钮）"""
    title = item.get("title_zh", item.get("title", ""))
    summary = item.get("summary_zh", "")
    why = item.get("why_try", "")
    link = item.get("link", "#")
    diff = item.get("difficulty", 3)
    copy = item.get("copyable_score", 3)
    time_min = item.get("time_estimate", "30min")
    tools = item.get("tools", [])
    play_type = item.get("play_type", "tool_chain")
    pt_meta = PLAY_TYPE_META.get(play_type, PLAY_TYPE_META["tool_chain"])
    score = item.get("playability_score", 6.0)

    # 教程徽章（教程可用时显示）
    tut_badge = ''
    if tutorial_url:
        tut_badge = (
            '<span class="inline-flex items-center px-2 py-0.5 rounded-full '
            'bg-indigo-50 text-indigo-700 text-xs font-semibold border '
            'border-indigo-200" title="本站教程可用">\U0001f4d6 教程</span>'
        )

    # CTA 双按钮（不使用 f-string 嵌套）
    if tutorial_url:
        cta_html = (
            '<div class="flex items-center gap-2">'
            f'<a href="{_esc(tutorial_url)}" '
            'class="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2.5 '
            'bg-gradient-to-r from-indigo-500 to-purple-500 text-white font-semibold '
            'rounded-lg hover:shadow-lg transition text-sm">'
            '\U0001f4d6 查看教程'
            '</a>'
            f'<a href="{_esc(link)}" target="_blank" rel="noopener nofollow" '
            f'class="inline-flex items-center justify-center gap-1 px-3 py-2.5 '
            f'bg-white border border-slate-300 text-slate-700 font-medium rounded-lg '
            f'hover:border-{pt_meta["color"]}-400 hover:text-{pt_meta["color"]}-700 '
            f'transition text-xs">原文 \u2197</a>'
            '</div>'
        )
    else:
        cta_html = (
            f'<a href="{_esc(link)}" target="_blank" rel="noopener nofollow" '
            f'class="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 '
            f'bg-gradient-to-r from-{pt_meta["color"]}-500 to-{pt_meta["color"]}-600 '
            f'text-white font-semibold rounded-lg hover:shadow-lg hover:scale-[1.02] '
            f'transition-all text-sm">立即打开 \u2192</a>'
        )

    # 工具标签
    tools_block = ''
    if tools and tools != ["未标注"]:
        tools_block = (
            '<div class="flex items-center gap-1.5 mb-4 flex-wrap">'
            + tools_badges(tools)
            + '</div>'
        )

    # data-tutorials-available 标记
    tut_avail = '1' if tutorial_url else '0'

    # 注意 f-string 里的 {{ 和 }} 是字面 { 和 }
    return f'''
<article class="play-card group relative bg-white rounded-2xl border border-slate-200 p-6 hover:border-{pt_meta["color"]}-300 hover:shadow-xl transition-all duration-200"
         data-play-type="{play_type}" data-difficulty="{diff}"
         data-source-tier="{item.get("source_tier", "B")}"
         data-copyable="{copy}"
         data-score="{score}"
         data-tutorials-available="{tut_avail}">
  <!-- 顶部标签 -->
  <div class="flex items-center gap-2 mb-3 flex-wrap">
    {play_type_badge(play_type)}
    {tier_badge(item)}
    <span class="inline-flex items-center px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 text-xs font-semibold border border-amber-200" title="可玩性评分">
      \U0001f3ae {score:.1f}
    </span>
    {tut_badge}
  </div>

  <!-- 标题 -->
  <h3 class="text-lg font-bold mb-2 leading-tight text-slate-900 group-hover:text-{pt_meta["color"]}-700 transition">
    {_esc(title)}
  </h3>

  <!-- 摘要 -->
  <p class="text-sm text-slate-600 mb-3 leading-relaxed line-clamp-2">
    {_esc(summary[:150])}
  </p>

  <!-- why_try 块 -->
  <div class="bg-{pt_meta["color"]}-50 border-l-2 border-{pt_meta["color"]}-400 pl-3 pr-2 py-2 mb-4 rounded-r text-sm text-slate-700">
    <span class="text-{pt_meta["color"]}-600 font-semibold">\u2728 为什么试</span>
    <span class="ml-1">{_esc(why[:120])}</span>
  </div>

  <!-- 元数据栏 -->
  <div class="flex items-center gap-2 mb-3 flex-wrap">
    {difficulty_badge(diff)}
    <span class="inline-flex items-center px-2 py-0.5 rounded text-xs bg-blue-50 text-blue-700 border border-blue-200">
      \u23f1 约 {time_min}
    </span>
    <span class="inline-flex items-center px-2 py-0.5 rounded text-xs bg-pink-50 text-pink-700 border border-pink-200" title="可复制度">
      \U0001f4cb 复制度 {copy}/5
    </span>
  </div>

  <!-- 工具标签 -->
  {tools_block}

  <!-- CTA 按钮（双按钮：有教程显示「教程+原文」，无教程显示「立即打开」） -->
  {cta_html}

  <!-- 来源 -->
  <div class="mt-3 text-xs text-slate-400 truncate">
    {_esc(item.get("source_name", ""))}
  </div>
</article>'''
def render_filters(items: list) -> str:
    """筛选器（动态生成）"""
    # 玩法类型计数
    pt_cnt = Counter(it.get("play_type", "tool_chain") for it in items)

    # 难度 1-5 + 可信度 S/A/B/C
    diff_cnt = Counter(it.get("difficulty", 3) for it in items)
    tier_cnt = Counter(it.get("source_tier", "B") for it in items)

    pt_html = ""
    for pt, m in PLAY_TYPE_META.items():
        n = pt_cnt.get(pt, 0)
        if n == 0:
            continue          # 空筛选项没有意义，只会让页面显得内容很少
        pt_html += f'''
    <button data-filter-group="type" data-filter-value="{pt}" class="filter-btn filter-type-btn px-3 py-1.5 rounded-full bg-slate-100 text-slate-700 hover:bg-{m['color']}-100 hover:text-{m['color']}-700 text-xs">
      {m['emoji']} {m['label']} <span class="text-slate-400">({n})</span>
    </button>'''

    # 难度：5 = 最容易（复制即用），1 = 最难（需工程基础）
    diff_html = ""
    for d, label in [(5, "\U0001f331 复制即用"), (4, "\U0001f680 打开即试"),
                     (3, "\U0001f527 需装环境"), (2, "\u2699\ufe0f 需改代码"),
                     (1, "\U0001f3d7\ufe0f 需工程基础")]:
        n = diff_cnt.get(d, 0)
        if n == 0:
            continue
        diff_html += f'''
    <button data-filter-group="diff" data-filter-value="{d}" class="filter-btn filter-diff-btn px-3 py-1.5 rounded-full bg-slate-100 text-slate-700 hover:bg-emerald-100 hover:text-emerald-700 text-xs">
      {label} <span class="text-slate-400">({n})</span>
    </button>'''

    tier_html = ""
    tier_color = {"S": "emerald", "A": "blue", "B": "amber", "C": "slate"}
    for t in ["S", "A", "B", "C"]:
        tier_label = {"S": "\U0001f7e2 官方", "A": "\U0001f535 权威", "B": "\U0001f7e1 社区", "C": "\u26aa 自媒体"}[t]
        n = tier_cnt.get(t, 0)
        if n == 0:
            continue
        tier_html += f'''
    <button data-filter-group="tier" data-filter-value="{t}" class="filter-btn filter-tier-btn px-3 py-1.5 rounded-full bg-slate-100 text-slate-700 hover:bg-{tier_color[t]}-100 hover:text-{tier_color[t]}-700 text-xs">
      {tier_label} <span class="text-slate-400">({n})</span>
    </button>'''

    return f'''
<div class="bg-white border border-slate-200 rounded-2xl p-5 mb-8 space-y-4">
  <div>
    <div class="text-xs text-slate-500 mb-2 font-semibold">\U0001f3ae 按玩法类型</div>
    <div class="flex items-center gap-2 flex-wrap">
      {pt_html}
    </div>
  </div>
  <div>
    <div class="text-xs text-slate-500 mb-2 font-semibold">\u2b50 按上手难度</div>
    <div class="flex items-center gap-2 flex-wrap">
      {diff_html}
    </div>
  </div>
  <div>
    <div class="text-xs text-slate-500 mb-2 font-semibold">\U0001f50d 按可信度</div>
    <div class="flex items-center gap-2 flex-wrap">
      {tier_html}
    </div>
  </div>
  <div class="flex items-center gap-3 pt-2 border-t border-slate-100">
    <button id="resetFilter" class="text-xs text-slate-500 hover:text-slate-900 underline">
      \u21ba 重置所有筛选
    </button>
    <span class="text-xs text-slate-400">
      当前显示 <span id="showCount" class="font-bold text-slate-900">{len(items)}</span> 条 / 共 {len(items)} 条
    </span>
  </div>
</div>'''


# ============================================================
# JS 筛选
# ============================================================

JS_FILTER = """
<script>
(function() {
  var activeType = 'all', activeDiff = 'all', activeTier = 'all';
  var cards = document.querySelectorAll('.play-card');

  function applyFilter() {
    var n = 0;
    cards.forEach(function(c) {
      var t = c.getAttribute('data-play-type');
      var d = c.getAttribute('data-difficulty');
      var tier = c.getAttribute('data-source-tier');
      var match = (activeType === 'all' || t === activeType) &&
                  (activeDiff === 'all' || d === activeDiff) &&
                  (activeTier === 'all' || tier === activeTier);
      c.style.display = match ? '' : 'none';
      if (match) n++;
    });
    document.getElementById('showCount').textContent = n;

    // 空状态
    var empty = document.getElementById('playEmpty');
    if (empty) empty.style.display = n === 0 ? '' : 'none';
  }

  document.querySelectorAll('.filter-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var g = btn.getAttribute('data-filter-group');
      var v = btn.getAttribute('data-filter-value');

      // 切换激活态
      var group = btn.parentElement;
      group.querySelectorAll('.filter-btn').forEach(function(b) {
        b.className = b.className.replace(/bg-\\S+-200 text-\\S+-700 font-bold/g, '').trim();
      });
      btn.classList.add('bg-' + (g === 'type' ? 'indigo' : g === 'diff' ? 'emerald' : 'amber') + '-200', 'font-bold');

      if (g === 'type') activeType = v;
      if (g === 'diff') activeDiff = v;
      if (g === 'tier') activeTier = v;
      applyFilter();
    });
  });

  document.getElementById('resetFilter').addEventListener('click', function(e) {
    e.preventDefault();
    activeType = activeDiff = activeTier = 'all';
    document.querySelectorAll('.filter-btn').forEach(function(b) {
      b.className = b.className.replace(/bg-\\S+-200 font-bold/g, '').trim();
    });
    applyFilter();
  });
})();
</script>
"""


# ============================================================
# 主渲染
# ============================================================

def render_html(items: list) -> str:
    # 统计
    total = len(items)
    by_type = Counter(it.get("play_type", "tool_chain") for it in items)
    n_official = sum(1 for it in items if it.get("source_tier") == "S")
    avg_diff = sum(it.get("difficulty", 3) for it in items) / total if total > 0 else 3

    # Hero 副标题按真实数据拼，不写死；为 0 的项直接不出现
    _hero_parts = []
    if by_type.get("runnable_demo"):
        _hero_parts.append(f"{by_type['runnable_demo']} 个打开即试")
    if by_type.get("prompt"):
        _hero_parts.append(f"{by_type['prompt']} 份可复制 Prompt")
    if by_type.get("tutorial"):
        _hero_parts.append(f"{by_type['tutorial']} 篇跟着做的教程")
    hero_sub = " \u00b7 ".join(_hero_parts) or "只收录能上手的内容"

    # 加载教程缓存（v5 教程社区）
    cache = {}
    cache_file = _Path(__file__).parent / "data" / "tutorials_cache.json"
    if cache_file.exists():
        try:
            with open(cache_file, encoding="utf-8") as f:
                cache = json.load(f)
        except (json.JSONDecodeError, OSError):
            cache = {}

    import hashlib
    def _cache_key(item):
        title_hash = hashlib.md5(item.get("title", "").encode("utf-8")).hexdigest()[:8]
        return f"{item.get('source_id', 'unknown')}-{title_hash}"

    def _render_with_tutorial(item, idx):
        ckey = _cache_key(item)
        tut = cache.get(ckey, {}).get("tutorial", {})
        tutorial_url = f"tutorials/{ckey}.html" if tut and not tut.get("_fallback") else ""
        return render_card(item, idx, tutorial_url)

    cards = "\n".join(_render_with_tutorial(it, i) for i, it in enumerate(items, 1))

    # 头部导航 + 顶部 logo
    today = datetime.now().strftime("%Y-%m-%d")

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI玩法实验室 · 全球 AI 前沿资讯</title>
<meta name="description" content="全球AI可复制的玩法项目 · prompt模板 · 工具工作流 · 立即试用">
<link rel="stylesheet" href="assets/tailwind.css">
<style>
  body {{ font-family: "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; }}
  .play-card {{ transition: all .2s ease; }}
  .filter-btn {{ transition: all .15s ease; cursor: pointer; user-select: none; }}
  .filter-btn:hover {{ transform: translateY(-1px); }}
</style>
</head>
<body class="bg-slate-50 text-slate-900">

<!-- 顶部导航 -->
<nav class="bg-white border-b border-slate-200 sticky top-0 z-40">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="flex items-center justify-between h-16">
      <a href="index.html" class="flex items-center gap-2">
        <span class="text-2xl">\U0001f30d</span>
        <span class="font-bold text-lg">AI Frontier</span>
        <span class="text-xs text-slate-400 ml-2">| 全球AI前沿</span>
      </a>
      <div class="hidden md:flex items-center gap-6 text-sm font-medium">
        <a href="index.html" class="text-slate-600 hover:text-slate-900">资讯</a>
        <a href="playground.html" class="text-slate-900 border-b-2 border-indigo-500">玩法实验室</a>
        <a href="tutorials/index.html" class="text-slate-600 hover:text-slate-900 flex items-center gap-1">全部教程</a>
        <a href="archive.html" class="text-slate-600 hover:text-slate-900">📅 往期资讯</a>
        <a href="daily-brief-{today}.html" class="text-slate-600 hover:text-slate-900">日报</a>
      </div>
    </div>
  </div>
</nav>

<!-- Hero -->
<header class="bg-gradient-to-br from-indigo-600 via-purple-600 to-pink-600 text-white">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16">
    <div class="text-xs font-bold tracking-widest uppercase opacity-80 mb-2">PLAYGROUND</div>
    <h1 class="text-3xl sm:text-4xl lg:text-5xl font-bold mb-4">\U0001f3ae AI玩法实验室</h1>
    <p class="text-lg sm:text-xl opacity-90 mb-6 max-w-3xl">
      {hero_sub}
    </p>

    <!-- 数据 -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 max-w-3xl">
      <div class="bg-white/10 backdrop-blur border border-white/20 rounded-xl p-4">
        <div class="text-2xl sm:text-3xl font-bold">{total}</div>
        <div class="text-sm opacity-80 mt-1">玩法项目</div>
      </div>
      <div class="bg-white/10 backdrop-blur border border-white/20 rounded-xl p-4">
        <div class="text-2xl sm:text-3xl font-bold">{by_type.get('runnable_demo', 0)}</div>
        <div class="text-sm opacity-80 mt-1">可立即试用</div>
      </div>
      <div class="bg-white/10 backdrop-blur border border-white/20 rounded-xl p-4">
        <div class="text-2xl sm:text-3xl font-bold">{by_type.get('prompt', 0)}</div>
        <div class="text-sm opacity-80 mt-1">Prompt 模板</div>
      </div>
      <div class="bg-white/10 backdrop-blur border border-white/20 rounded-xl p-4">
        <div class="text-2xl sm:text-3xl font-bold">{avg_diff:.1f}</div>
        <div class="text-sm opacity-80 mt-1">平均难度\uff085=最易\uff09</div>
      </div>
    </div>
  </div>
</header>

<!-- 主体 -->
<main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">

  <!-- 筛选器 -->
  {render_filters(items)}

  <!-- 卡片网格 -->
  <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
    {cards}
  </div>

  <!-- 空状态 -->
  <div id="playEmpty" style="display:none;" class="mt-12 text-center py-16 bg-white rounded-2xl border border-slate-200">
    <div class="text-5xl mb-3">\U0001f914</div>
    <div class="text-slate-500">当前筛选条件下暂无玩法，试试调整筛选器。</div>
    <button onclick="document.getElementById('resetFilter').click()" class="mt-4 text-indigo-600 hover:underline text-sm">
      重置筛选条件
    </button>
  </div>

</main>

<!-- 底部 -->
<footer class="bg-slate-900 text-slate-400 mt-20">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 text-center text-sm">
    <p>\U0001f30d AI Frontier \u00b7 全球 AI 前沿资讯 \u00b7 玩法实验室</p>
    <p class="mt-2 text-xs opacity-60">玩法均经人工规则筛选：新闻通稿、付费墙、无可操作内容不计入 \u00b7 点\u300c立即打开\u300d前往原文</p>
  </div>
</footer>

{JS_FILTER}
{render_floating_home(href="index.html", label="返回首页")}
</body>
</html>
'''


def main():
    if not INPUT_FILE.exists():
        print(f"[ERROR] {INPUT_FILE} 不存在，先跑 fetch_ai_play.py + score_play.py")
        sys.exit(1)
    with open(INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items", [])
    print(f"\U0001f3ae 渲染 {len(items)} 条玩法到 playground.html")

    html = render_html(items)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"[OK] {OUTPUT_FILE}  ({len(html.encode('utf-8'))/1024:.1f} KB)")


if __name__ == "__main__":
    main()
