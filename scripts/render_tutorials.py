"""
render_tutorials.py
===================
AI 玩法实验室 · 教程详情页渲染脚本

输入：tutorials_cache.json + scored_play.json
输出：tutorials/<cache_key>.html （每篇教程一个独立页面）

教程页结构（仿"零度博客"风格）：
  1. 顶部导航 + 面包屑
  2. Hero 区（标题 / 标签 / 难度 / 时间 / 工具 / 来源徽章）
  3. 自动目录（从步骤生成锚点）
  4. 章节正文：
     - 这是什么（intro）
     - 为什么值得玩（background）
     - 你需要准备（prerequisites）
     - 一步步教你做（steps）
     - 完成后你会得到（expected_result）
     - 常见问题（faq）
     - 进阶玩法（variants）
     - 一句话总结（summary）
  5. 底部相关推荐（同 play_type 的 3 条）
  6. 悬浮返回按钮
"""

import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).parent))
import _utf8  # noqa: F401

from floating_home import render_floating_home
from tutorials_schema import TUTORIAL_HTML_STRUCTURE

CACHE_FILE = _Path(__file__).parent / "data" / "tutorials_cache.json"
SCORED_FILE = _Path(__file__).parent / "data" / "scored_play.json"
OUTPUT_DIR = _Path(__file__).parent.parent / "tutorials"


PLAY_TYPE_META = {
    "prompt":         {"color": "indigo",  "emoji": "💬", "label": "Prompt 模板"},
    "tool_workflow":  {"color": "purple",  "emoji": "🧭", "label": "工作流"},
    "tool_chain":     {"color": "cyan",    "emoji": "🔗", "label": "工具链"},
    "runnable_demo":  {"color": "emerald", "emoji": "🚀", "label": "可立即试用"},
    "tutorial":       {"color": "amber",   "emoji": "📖", "label": "教程指引"},
}


# ============================================================
# HTML 工具
# ============================================================

def _esc(s) -> str:
    if not s:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _safe_url(u) -> str:
    """只放行合法的 http(s) 链接。

    LLM 生成 prerequisites 时，常把说明文字塞进 url 字段（如“无”“根据你使用的
    群聊工具官网下载”），直接输出会变成死链。此处做白名单校验，非法值一律丢弃。
    """
    if not u:
        return ""
    s = str(u).strip()
    if not s or any(c in s for c in " \t\r\n\"'<>"):
        return ""
    low = s.lower()
    if not (low.startswith("http://") or low.startswith("https://")):
        return ""
    # 必须有域名部分
    rest = s.split("://", 1)[1]
    if not rest or "." not in rest.split("/", 1)[0]:
        return ""
    return s


def _stars(n: int, max_n: int = 5) -> str:
    n = max(0, min(max_n, int(n or 0)))
    return "★" * n + "☆" * (max_n - n)


# ============================================================
# 章节渲染器
# ============================================================

def render_intro(text: str) -> str:
    return f'''
<section class="bg-gradient-to-br from-indigo-50 via-purple-50 to-pink-50 border-l-4 border-indigo-400 rounded-r-2xl p-6 mb-8">
  <div class="text-sm font-bold text-indigo-700 mb-2">📌 这是什么</div>
  <p class="text-base text-slate-800 leading-relaxed">{_esc(text)}</p>
</section>'''


def render_background(text: str) -> str:
    return f'''
<section class="mb-8">
  <h2 class="text-2xl font-bold text-slate-900 mb-3 flex items-center gap-2">
    <span class="text-3xl">🎯</span> 为什么值得玩
  </h2>
  <p class="text-base text-slate-700 leading-loose bg-amber-50 border border-amber-200 rounded-xl p-5">
    {_esc(text)}
  </p>
</section>'''


def render_prerequisites(items: list) -> str:
    if not items:
        return ""
    lis = ""
    for p in items:
        name = _esc(p.get("name", ""))
        desc = _esc(p.get("desc", ""))
        url = _safe_url(p.get("url", ""))
        url_html = f' <a href="{_esc(url)}" target="_blank" rel="noopener" class="text-blue-600 hover:underline text-sm">→ 访问</a>' if url else ""
        lis += f'''
    <li class="bg-white border border-slate-200 rounded-lg p-4">
      <div class="font-semibold text-slate-900">{name} {url_html}</div>
      <div class="text-sm text-slate-600 mt-1">{desc}</div>
    </li>'''
    return f'''
<section id="prerequisites" class="mb-10">
  <h2 class="text-2xl font-bold text-slate-900 mb-3 flex items-center gap-2">
    <span class="text-3xl">🧰</span> 你需要准备
  </h2>
  <ul class="grid grid-cols-1 md:grid-cols-2 gap-3">
    {lis}
  </ul>
</section>'''


def render_steps(steps: list) -> str:
    if not steps:
        return ""
    html = ""
    for i, step in enumerate(steps, 1):
        title = _esc(step.get("title", f"第 {i} 步"))
        content = _esc(step.get("content", ""))
        tip = _esc(step.get("tip", ""))
        tip_html = f'''
        <div class="mt-3 bg-amber-50 border-l-2 border-amber-400 rounded-r px-3 py-2 text-sm text-amber-800">
          💡 <span class="font-semibold">小贴士：</span>{tip}
        </div>''' if tip else ""
        html += f'''
    <div id="step-{i}" class="relative pl-12 pb-8 border-l-2 border-indigo-200 last:border-l-0">
      <div class="absolute -left-5 top-0 w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 text-white font-bold flex items-center justify-center shadow-lg">
        {i}
      </div>
      <h3 class="text-lg font-bold text-slate-900 mb-2">{title}</h3>
      <div class="text-base text-slate-700 leading-loose">{content}</div>
      {tip_html}
    </div>'''
    return f'''
<section id="steps" class="mb-10">
  <h2 class="text-2xl font-bold text-slate-900 mb-6 flex items-center gap-2">
    <span class="text-3xl">📝</span> 一步步教你做
  </h2>
  <div class="space-y-0">{html}
  </div>
</section>'''


def render_expected(text: str) -> str:
    if not text:
        return ""
    return f'''
<section class="mb-10">
  <h2 class="text-2xl font-bold text-slate-900 mb-3 flex items-center gap-2">
    <span class="text-3xl">✨</span> 完成后你会得到
  </h2>
  <div class="bg-emerald-50 border border-emerald-200 rounded-xl p-5 text-base text-slate-800 leading-loose">
    {_esc(text)}
  </div>
</section>'''


def render_faq(faqs: list) -> str:
    if not faqs:
        return ""
    items_html = ""
    for f in faqs:
        q = _esc(f.get("q", ""))
        a = _esc(f.get("a", ""))
        items_html += f'''
    <details class="bg-white border border-slate-200 rounded-lg group">
      <summary class="cursor-pointer p-4 font-semibold text-slate-900 flex items-center justify-between">
        <span>{q}</span>
        <span class="text-slate-400 group-open:rotate-180 transition-transform">▼</span>
      </summary>
      <div class="px-4 pb-4 text-sm text-slate-700 leading-loose">{a}</div>
    </details>'''
    return f'''
<section id="faq" class="mb-10">
  <h2 class="text-2xl font-bold text-slate-900 mb-3 flex items-center gap-2">
    <span class="text-3xl">❓</span> 常见问题
  </h2>
  <div class="space-y-2">{items_html}
  </div>
</section>'''


def render_variants(variants: list) -> str:
    if not variants:
        return ""
    items = "".join(
        f'<li class="bg-white border border-purple-200 rounded-lg p-4 text-slate-800">🔹 {_esc(v)}</li>'
        for v in variants
    )
    return f'''
<section class="mb-10">
  <h2 class="text-2xl font-bold text-slate-900 mb-3 flex items-center gap-2">
    <span class="text-3xl">🚀</span> 进阶玩法
  </h2>
  <ul class="grid grid-cols-1 md:grid-cols-3 gap-3">{items}</ul>
</section>'''


def render_summary(text: str) -> str:
    if not text:
        return ""
    return f'''
<section class="mb-12">
  <h2 class="text-2xl font-bold text-slate-900 mb-3 flex items-center gap-2">
    <span class="text-3xl">💡</span> 一句话总结
  </h2>
  <blockquote class="bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 text-white text-lg font-semibold rounded-2xl p-6 shadow-lg">
    {_esc(text)}
  </blockquote>
</section>'''


def render_toc(tut: dict, has_prereq: bool, has_steps: bool) -> str:
    """自动生成目录"""
    items = []
    if has_prereq:
        items.append(("prerequisites", "🧰 准备工具"))
    if has_steps:
        items.append(("steps", "📝 操作步骤"))
    if tut.get("expected_result"):
        items.append(("expected", "✨ 预期效果"))
    if tut.get("faq"):
        items.append(("faq", "❓ 常见问题"))
    if tut.get("variants"):
        items.append(("variants", "🚀 进阶玩法"))

    if not items:
        return ""
    lis = "".join(
        f'<li><a href="#{aid}" class="block py-1.5 text-sm text-slate-700 hover:text-indigo-600 hover:underline">→ {label}</a></li>'
        for aid, label in items
    )
    return f'''
<aside class="bg-slate-50 border border-slate-200 rounded-xl p-5 mb-8">
  <div class="text-xs font-bold text-slate-500 mb-3 uppercase tracking-wide">目录</div>
  <ul class="space-y-0.5">{lis}</ul>
</aside>'''


def render_related(items: list) -> str:
    """相关推荐：同 play_type 的其他教程"""
    if not items:
        return ""
    cards = ""
    for it in items:
        title = _esc(it.get("title", ""))
        href = _esc(it.get("href", "#"))
        meta = _esc(it.get("meta", ""))
        diff = it.get("difficulty", 3)
        cards += f'''
    <a href="{href}" class="block bg-white border border-slate-200 rounded-xl p-4 hover:border-indigo-300 hover:shadow-md transition">
      <div class="text-xs text-slate-500 mb-1">{meta}</div>
      <div class="font-semibold text-slate-900 mb-2 line-clamp-2">{title}</div>
      <div class="text-xs text-amber-500">{_stars(diff)}</div>
    </a>'''
    return f'''
<section class="mb-12">
  <h2 class="text-2xl font-bold text-slate-900 mb-4 flex items-center gap-2">
    <span class="text-3xl">📚</span> 相关教程
  </h2>
  <div class="grid grid-cols-1 md:grid-cols-3 gap-4">{cards}</div>
</section>'''


def render_source_meta(meta: dict) -> str:
    """Hero 区域的元信息条"""
    source = _esc(meta.get("source_name", ""))
    source_label = _esc(meta.get("source_label", ""))
    tier = _esc(meta.get("source_tier", "B"))
    color = meta.get("source_color", "slate")
    link = _esc(meta.get("link", "#"))
    is_domestic = meta.get("is_domestic", False)
    domestic_flag = '<span class="px-1.5 py-0.5 rounded text-xs bg-red-50 text-red-600 border border-red-200">国内</span>' if is_domestic else ""

    return f'''
<div class="flex items-center gap-2 mb-4 flex-wrap">
  <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-{color}-50 text-{color}-700 border border-{color}-200">
    {source} · {tier}级
  </span>
  {domestic_flag}
  <span class="inline-flex items-center px-2 py-0.5 rounded text-xs bg-slate-100 text-slate-600">
    {source_label}
  </span>
  <a href="{link}" target="_blank" rel="noopener" class="text-xs text-blue-600 hover:underline ml-auto">
    查看原文 →
  </a>
</div>'''


def render_tools_meta(tools: list) -> str:
    if not tools or tools == ["未标注"]:
        return ""
    items = "".join(
        f'<span class="inline-flex items-center px-2 py-1 rounded text-xs bg-cyan-50 text-cyan-700 border border-cyan-200">{_esc(t)}</span>'
        for t in tools[:5]
    )
    return f'''
<div class="mb-4">
  <div class="text-xs text-slate-500 mb-2 font-semibold">🛠 涉及工具</div>
  <div class="flex items-center gap-1.5 flex-wrap">{items}</div>
</div>'''


# ============================================================
# 单篇教程页 HTML
# ============================================================

def render_tutorial_page(ckey: str, meta: dict, tut: dict, related: list) -> str:
    title = meta.get("title_zh") or meta.get("title_en") or "未命名玩法"
    play_type = meta.get("play_type", "tool_chain")
    pt_meta = PLAY_TYPE_META.get(play_type, PLAY_TYPE_META["tool_chain"])
    diff = meta.get("difficulty", 3)
    time_min = meta.get("time_estimate", "30min")
    tools = meta.get("tools", [])

    body = ""

    # 1. Intro
    if tut.get("intro"):
        body += render_intro(tut["intro"])

    # 2. TOC
    body += render_toc(tut,
                       bool(tut.get("prerequisites")),
                       bool(tut.get("steps")))

    # 3. Background
    if tut.get("background"):
        body += render_background(tut["background"])

    # 4. Prerequisites
    body += render_prerequisites(tut.get("prerequisites", []))

    # 5. Steps（核心）
    body += render_steps(tut.get("steps", []))

    # 6. Expected
    body += render_expected(tut.get("expected_result", ""))

    # 7. FAQ
    body += render_faq(tut.get("faq", []))

    # 8. Variants
    body += render_variants(tut.get("variants", []))

    # 9. Summary
    body += render_summary(tut.get("summary", ""))

    # 10. Related
    body += render_related(related)

    # fallback 标记
    fallback_banner = ""
    if tut.get("_fallback"):
        fallback_banner = '''
<div class="bg-amber-50 border border-amber-300 rounded-xl p-4 mb-8 text-sm text-amber-800">
  ⚠️ 本教程由 AI 自动生成占位内容，详细教程正在生成中。点击上方"查看原文"可访问原始资源。
</div>'''

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(title)} - AI 玩法教程 · AI Frontier</title>
<link rel="stylesheet" href="../assets/tailwind.css">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif; }}
  details[open] summary {{ background: #f8fafc; }}
  .line-clamp-2 {{ display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
  html {{ scroll-behavior: smooth; }}
</style>
</head>
<body class="bg-slate-50 min-h-screen">

<!-- 顶部导航 -->
<nav class="bg-white border-b border-slate-200 sticky top-0 z-40">
  <div class="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
    <div class="flex items-center gap-2 text-sm">
      <a href="../index.html" class="text-slate-500 hover:text-slate-900">首页</a>
      <span class="text-slate-300">/</span>
      <a href="../playground.html" class="text-slate-500 hover:text-slate-900">玩法实验室</a>
      <span class="text-slate-300">/</span>
      <a href="../archive.html" class="text-slate-500 hover:text-slate-900">往期资讯</a>
      <span class="text-slate-300">/</span>
      <span class="text-slate-900 font-semibold">教程</span>
    </div>
    <div class="text-xs text-slate-400">
      {datetime.now().strftime("%Y-%m-%d")}
    </div>
  </div>
</nav>

<!-- Hero 区 -->
<header class="bg-gradient-to-br from-indigo-600 via-purple-600 to-pink-600 text-white">
  <div class="max-w-4xl mx-auto px-4 py-10">
    <div class="flex items-center gap-2 mb-3 flex-wrap">
      <span class="px-2 py-0.5 rounded-full bg-white/20 text-white text-xs font-semibold backdrop-blur">
        {pt_meta["emoji"]} {pt_meta["label"]}
      </span>
      <span class="px-2 py-0.5 rounded-full bg-white/20 text-white text-xs font-semibold backdrop-blur">
        {_stars(diff)} · {diff}/5
      </span>
      <span class="px-2 py-0.5 rounded-full bg-white/20 text-white text-xs font-semibold backdrop-blur">
        ⏱ 约 {time_min}
      </span>
    </div>
    <h1 class="text-3xl md:text-4xl font-black leading-tight mb-3">{_esc(title)}</h1>
    {fallback_banner}
  </div>
</header>

<!-- 主体 -->
<main class="max-w-4xl mx-auto px-4 py-8">

  <!-- 来源元信息 -->
  <div class="bg-white rounded-2xl border border-slate-200 p-5 mb-8">
    {render_source_meta(meta)}
    {render_tools_meta(tools)}
  </div>

  {body}

  <!-- 底部 -->
  <footer class="text-center text-sm text-slate-400 mt-16 pt-8 border-t border-slate-200">
    <p>本教程由 AI 玩法实验室 · LLM 自动生成 · 仅供学习参考</p>
    <p class="mt-2"><a href="../playground.html" class="text-indigo-600 hover:underline">← 返回玩法实验室</a></p>
  </footer>
</main>

{render_floating_home("../playground.html")}

</body>
</html>'''


# ============================================================
# 主流程
# ============================================================

def main():
    if not CACHE_FILE.exists():
        print(f"[ERROR] 找不到 {CACHE_FILE}，先跑 generate_tutorials.py")
        sys.exit(1)

    with open(CACHE_FILE, encoding="utf-8") as f:
        cache = json.load(f)

    # 加载 scored_play.json 用于"相关推荐"
    all_plays = []
    if SCORED_FILE.exists():
        with open(SCORED_FILE, encoding="utf-8") as f:
            all_plays = json.load(f).get("items", [])

    # 创建 tutorials 目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # 只清理"不在本次缓存里"的过期页面。
    # 旧写法是整目录 unlink 后重建（每天 60+ 次删除），会触发批量删除安全拦截；
    # 增量清理后正常情况只有 0~2 个文件需要删。
    valid_names = {f"{k}.html" for k in cache} | {"index.html"}
    for f in OUTPUT_DIR.glob("*.html"):
        if f.name not in valid_names:
            f.unlink()

    print(f"📚 渲染教程详情页")
    print(f"   缓存条目：{len(cache)}")

    generated = 0
    skipped = 0
    for ckey, entry in cache.items():
        meta = entry.get("play_meta", {})
        tut = entry.get("tutorial", {})
        if not tut or not meta:
            skipped += 1
            continue

        # 找相关推荐（同 play_type，排除自己）
        pt = meta.get("play_type", "tool_chain")
        related = []
        for p in all_plays:
            if p.get("play_type") == pt and p.get("source_id", "") != meta.get("source_id", ""):
                related.append({
                    "title": p.get("title_zh") or p.get("title", ""),
                    "href": "../playground.html#play-" + str(p.get("source_id", "")),
                    "meta": f'{p.get("source_name", "")} · 难度 {p.get("difficulty", 3)}/5',
                    "difficulty": p.get("difficulty", 3),
                })
                if len(related) >= 3:
                    break
        if len(related) < 3:
            # 不足 3 条，补其他玩法
            for p in all_plays:
                if p.get("source_id", "") != meta.get("source_id", "") and not any(r["title"] == p.get("title_zh", p.get("title", "")) for r in related):
                    related.append({
                        "title": p.get("title_zh") or p.get("title", ""),
                        "href": "../playground.html",
                        "meta": f'{p.get("source_name", "")} · 难度 {p.get("difficulty", 3)}/5',
                        "difficulty": p.get("difficulty", 3),
                    })
                    if len(related) >= 3:
                        break

        # 渲染
        html = render_tutorial_page(ckey, meta, tut, related)
        out_path = OUTPUT_DIR / f"{ckey}.html"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        generated += 1

    # 写教程索引页（便于浏览所有教程）
    print(f"   渲染详情页：{generated} 篇（跳过 {skipped} 条无 meta）")

    # 生成 tutorials/index.html（教程总目录）
    tutorial_items = []
    for ckey, entry in cache.items():
        meta = entry.get("play_meta", {})
        tut = entry.get("tutorial", {})
        if not meta:
            continue
        tutorial_items.append({
            "ckey": ckey,
            "title": meta.get("title_zh") or meta.get("title_en", ""),
            "play_type": meta.get("play_type", "tool_chain"),
            "source_name": meta.get("source_name", ""),
            "source_tier": meta.get("source_tier", "B"),
            "source_color": meta.get("source_color", "slate"),
            "difficulty": meta.get("difficulty", 3),
            "intro": tut.get("intro", "")[:120] if tut else "",
            "is_domestic": meta.get("is_domestic", False),
            "is_fallback": tut.get("_fallback", False) if tut else True,
        })
    # 按教程质量排序（fallback 在后）
    tutorial_items.sort(key=lambda x: (x["is_fallback"], -1 if x["is_domestic"] else 0))

    # 教程索引页
    cards = ""
    for it in tutorial_items:
        pt_meta = PLAY_TYPE_META.get(it["play_type"], PLAY_TYPE_META["tool_chain"])
        cards += f'''
    <a href="{it["ckey"]}.html" class="block bg-white border border-slate-200 rounded-xl p-5 hover:border-indigo-300 hover:shadow-md transition">
      <div class="flex items-center gap-2 mb-2 flex-wrap">
        <span class="px-2 py-0.5 rounded text-xs bg-{pt_meta["color"]}-100 text-{pt_meta["color"]}-700 font-semibold">{pt_meta["emoji"]} {pt_meta["label"]}</span>
        <span class="px-2 py-0.5 rounded text-xs bg-{it["source_color"]}-50 text-{it["source_color"]}-700">{it["source_name"]}</span>
        {'<span class="px-2 py-0.5 rounded text-xs bg-red-50 text-red-600">国内</span>' if it["is_domestic"] else ""}
        {'<span class="px-2 py-0.5 rounded text-xs bg-amber-50 text-amber-700">占位</span>' if it["is_fallback"] else ""}
      </div>
      <h3 class="text-base font-bold text-slate-900 mb-2 line-clamp-2">{_esc(it["title"])}</h3>
      <p class="text-sm text-slate-600 line-clamp-2 mb-2">{_esc(it["intro"])}</p>
      <div class="text-xs text-amber-500">{_stars(it["difficulty"])}</div>
    </a>'''

    index_html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI 玩法教程 · AI Frontier</title>
<link rel="stylesheet" href="../assets/tailwind.css">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif; }}
  .line-clamp-2 {{ display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
</style>
</head>
<body class="bg-slate-50 min-h-screen">

<nav class="bg-white border-b border-slate-200 sticky top-0 z-40">
  <div class="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
    <div class="flex items-center gap-2 text-sm">
      <a href="../index.html" class="text-slate-500 hover:text-slate-900">首页</a>
      <span class="text-slate-300">/</span>
      <a href="../playground.html" class="text-slate-500 hover:text-slate-900">玩法实验室</a>
      <span class="text-slate-300">/</span>
      <a href="../archive.html" class="text-slate-500 hover:text-slate-900">往期资讯</a>
      <span class="text-slate-300">/</span>
      <span class="text-slate-900 font-semibold">全部教程</span>
    </div>
    <input type="text" id="searchInput" placeholder="搜索教程标题或简介..."
           class="px-3 py-1.5 border border-slate-300 rounded-lg text-sm w-64 focus:outline-none focus:ring-2 focus:ring-indigo-500">
  </div>
</nav>

<header class="bg-gradient-to-br from-indigo-600 via-purple-600 to-pink-600 text-white">
  <div class="max-w-6xl mx-auto px-4 py-10 text-center">
    <div class="text-5xl mb-3">📚</div>
    <h1 class="text-3xl md:text-4xl font-black mb-3">AI 玩法教程</h1>
    <p class="text-base text-white/90">每篇都是结构化实战教程 · 像零度博客那样一步步教你</p>
    <div class="mt-4 text-sm text-white/80">共 {len(tutorial_items)} 篇教程</div>
  </div>
</header>

<main class="max-w-6xl mx-auto px-4 py-10">
  <div id="cardGrid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
    {cards}
  </div>
</main>

<script>
  document.getElementById('searchInput').addEventListener('input', function(e) {{
    const q = e.target.value.toLowerCase();
    document.querySelectorAll('#cardGrid > a').forEach(card => {{
      card.style.display = card.textContent.toLowerCase().includes(q) ? '' : 'none';
    }});
  }});
</script>

{render_floating_home("../playground.html")}

</body>
</html>'''

    index_path = OUTPUT_DIR / "index.html"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)
    print(f"   教程索引页：{index_path}")
    print(f"\n========================================")
    print(f"✅ 教程页渲染完成")
    print(f"   详情页：{generated} 篇")
    print(f"   索引页：1 个")
    print(f"   输出目录：{OUTPUT_DIR}")
    print(f"========================================")


if __name__ == "__main__":
    main()