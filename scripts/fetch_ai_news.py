"""
fetch_ai_news.py
================
全球 AI 前沿资讯网站 - 自动化采集脚本 (v3)

v3 升级点：
1. 信息源按「来源可信度」分级（official/media/community/selfmedia）
2. 新增官方一手源（OpenAI/Anthropic/Google/Meta/HF）
3. 新增 GitHub 高 star 项目抓取（search API）
4. 每条资讯带 source_type 和 reliability_level

使用：
  python fetch_ai_news.py
"""

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from html import unescape
import re
import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).parent))
import _utf8  # noqa: F401  —— 强制 UTF-8 输出，防止 GBK 控制台崩溃

# 共享配置：信息源 + 可信度分级
from sources_config import RSS_SOURCES, GITHUB_CONFIG, reliability_of

# 内容质量：HTML 清洗 / 链接清洗 / AI 相关性 / 去重
from content_quality import (
    strip_html, clean_link, is_paywalled, ai_relevance, dedupe_items,
)

# 仅保留最近 N 小时
HOURS_WINDOW = 36

# GitHub 高星项目按"项目创建时间"设计，单独给一个更宽的上限（天）
GITHUB_MAX_AGE_DAYS = 5

# 单源最多保留条数
MAX_PER_SOURCE = 15

# 综合/泛科技媒体：标题必须出现 AI 信号，避免"正文顺带提一句 AI"的
# 消费、医疗、地产类新闻混进 AI 前沿。
STRICT_TITLE_SOURCES = {
    "geekpark", "tmtpost", "zhidx", "ifanr", "sspai", "sootoo",
}

# 技术社区：标题常是纯技术表述（"用 xx 做 yy"），放宽到标题或描述含 AI 信号，
# 但仍要过 AI 相关性闸门，避免《道德经》这类完全无关的帖子混进来。
TECH_COMMUNITY_SOURCES = {
    "juejin", "segmentfault", "cnblogs", "hackernews", "infoq-cn",
}

# 输出文件
OUTPUT_FILE = Path(__file__).parent / "data" / "raw_news.json"

USER_AGENT = "AI-Frontier-Bot/3.0 (+https://ai-frontier.com)"


# ============================================================
# 基础抓取工具
# ============================================================

def fetch_url(url: str, timeout: int = 20, retries: int = 4) -> bytes:
    """带 User-Agent 的 GET 请求，自动重试 + 自动解压 gzip/deflate
    v4 强化：重试 4 次 + 指数退避 + gzip/deflate 自动解压"""
    import gzip
    import zlib
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    last_err = None
    for i in range(retries + 1):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                enc = resp.headers.get("Content-Encoding", "").lower()
                if enc == "gzip":
                    try:
                        raw = gzip.decompress(raw)
                    except (OSError, EOFError):
                        # 部分服务器声明 gzip 但实际不压缩，原始字节也可用
                        pass
                elif enc == "deflate":
                    try:
                        raw = zlib.decompress(raw)
                    except zlib.error:
                        pass
                return raw
        except (URLError, HTTPError, TimeoutError, OSError, Exception) as e:
            last_err = e
            if i < retries:
                wait = 1.5 ** i  # 指数退避：1, 1.5, 2.25, 3.4 秒
                time.sleep(wait)
    raise last_err


TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def clean_html(text: str, max_len: int = 500) -> str:
    """统一走 content_quality.strip_html（去标签 / 反转义 / 去导流尾巴）。"""
    return strip_html(text, max_len=max_len)


def parse_pubdate(s: str) -> datetime | None:
    """解析 RSS/Atom 时间，统一返回 UTC 时区的 aware datetime。

    注意：`%Z` 与 `... GMT` 两种格式解析出来的是 **naive datetime**（无 tzinfo）。
    对 naive 值直接调用 astimezone() 会按本机时区（东八区）解释，导致时间整体偏移 -8 小时，
    进而把 16~24 小时内发布的条目误判为超出时间窗而丢弃。因此这里显式补 UTC 时区。
    """
    if not s:
        return None
    formats = [
        "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S GMT", "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S",
    ]
    s = s.strip()
    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
        except (ValueError, TypeError):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return None


def parse_rss(xml_text: str) -> list[dict]:
    """统一解析 RSS 2.0 和 Atom"""
    items = []
    namespaces = {
        "atom": "http://www.w3.org/2005/Atom",
        "dc": "http://purl.org/dc/elements/1.1/",
        "content": "http://purl.org/rss/1.0/modules/content/",
    }
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"    [XML 解析失败] {e}")
        return items

    if root.tag.endswith("feed"):  # Atom
        ns = "{http://www.w3.org/2005/Atom}"
        for entry in root.findall(f"{ns}entry"):
            title = (entry.findtext(f"{ns}title") or "").strip()
            link_el = entry.find(f"{ns}link")
            link = (link_el.get("href") if link_el is not None else "").strip()
            pub = (entry.findtext(f"{ns}updated") or entry.findtext(f"{ns}published") or "").strip()
            desc = (entry.findtext(f"{ns}summary") or "").strip()
            if title and link:
                items.append({
                    "title": clean_html(title, 200),
                    "link": clean_link(link),
                    "pubDate": pub,
                    "description": clean_html(desc),
                })
        return items

    channel = root.find("channel")  # RSS 2.0
    if channel is None:
        return items
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or item.findtext("date") or "").strip()
        desc = (item.findtext("description") or "").strip()
        if title and link:
            items.append({
                "title": clean_html(title, 200),
                "link": clean_link(link),
                "pubDate": pub,
                "description": clean_html(desc),
            })
    return items


# ============================================================
# GitHub 高 star 项目抓取
# ============================================================

def fetch_github_trending() -> list[dict]:
    """通过 GitHub Search API 抓取最近创建的高 star 项目"""
    items = []
    since_date = (datetime.now(timezone.utc) - timedelta(days=GITHUB_CONFIG["days_back"])).strftime("%Y-%m-%d")

    for q in GITHUB_CONFIG["queries"]:
        topic = q["topic"]
        min_stars = q["min_stars"]
        label = q["label"]
        url = (f"{GITHUB_CONFIG['api_url']}?q=topic:{topic}+created:>{since_date}"
               f"+stars:>{min_stars}&sort=stars&order=desc&per_page={GITHUB_CONFIG['max_per_topic']}")
        print(f"  → GitHub 高星 [{label}] {topic}")
        try:
            raw = fetch_url(url)
            data = json.loads(raw.decode("utf-8", errors="ignore"))
            repos = data.get("items", [])
            for repo in repos:
                rel = reliability_of("community")
                repo_desc = clean_html(repo.get("description", "") or "", 200)
                items.append({
                    "title": f"{repo.get('full_name','')} — {repo_desc[:60]}",
                    "link": clean_link(repo.get("html_url", "")),
                    "pubDate": repo.get("created_at", ""),
                    "description": (
                        f"⭐ {repo.get('stargazers_count', 0)} stars · "
                        f"{repo.get('language', 'N/A')} · "
                        f"{repo_desc}"
                    )[:300],
                    "stars": repo.get("stargazers_count", 0),
                    "source_id": f"github-{topic}",
                    "source_name": f"GitHub 高星 {label}",
                    "source_category": "开源",
                    "source_lang": "en",
                    "source_type": "community",
                    "reliability_level": rel["level"],
                    # GitHub 项目按"最近 30 天"设计，跳过 24h 时间窗过滤
                    "skip_time_filter": True,
                })
            print(f"    ✓ {len(repos)} 个项目")
        except Exception as e:
            print(f"    ✗ 失败: {type(e).__name__}: {e}")
        time.sleep(0.5)

    return items


# ============================================================
# 主流程
# ============================================================

def fetch_source(src: dict) -> list[dict]:
    name = src["name"]
    stype = src.get("source_type", "selfmedia")
    rel = reliability_of(stype)
    print(f"  → {name:<20} {rel['emoji']} {rel['label']}")
    try:
        body = fetch_url(src["url"]).decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"    ✗ 失败: {type(e).__name__}")
        return []
    items = parse_rss(body)
    print(f"    ✓ 解析 {len(items)} 条")
    for it in items:
        it["source_id"] = src["id"]
        it["source_name"] = src["name"]
        it["source_category"] = src["category"]
        it["source_lang"] = src["lang"]
        it["source_type"] = stype
        it["reliability_level"] = rel["level"]
    return items


def filter_recent(items: list[dict], hours: int) -> list[dict]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)
    gh_cutoff = now - timedelta(days=GITHUB_MAX_AGE_DAYS)
    kept = []
    dropped_old = 0
    for it in items:
        # GitHub 高星项目按"项目创建时间"排序，用更宽的窗口（天），
        # 但不能无限放宽——之前 30 天窗口把 20 多天前的项目当成今日资讯。
        if it.get("skip_time_filter"):
            dt = parse_pubdate(it.get("pubDate", ""))
            if dt is None or dt >= gh_cutoff:
                kept.append(it)
            else:
                dropped_old += 1
            continue
        dt = parse_pubdate(it.get("pubDate", ""))
        if dt is None or dt >= cutoff:
            kept.append(it)
        else:
            dropped_old += 1
    if dropped_old:
        print(f"  （时间窗外丢弃 {dropped_old} 条）")
    return kept


def filter_paywall(items: list[dict]) -> list[dict]:
    """剔除付费墙文章：读者点进去看不到正文，收进来只会掉口碑。"""
    out = [it for it in items if not is_paywalled(it.get("link", ""))]
    if len(out) != len(items):
        print(f"  （付费墙丢弃 {len(items) - len(out)} 条）")
    return out


def filter_ai_relevant(items: list[dict]) -> list[dict]:
    """AI 相关性闸门：泛科技媒体要求标题含 AI 信号，技术社区放宽到全文。"""
    kept, dropped = [], []
    for it in items:
        if it.get("skip_time_filter"):      # GitHub 项目已按 topic 过滤
            kept.append(it)
            continue
        strict = it.get("source_id") in STRICT_TITLE_SOURCES
        ok, reason = ai_relevance(it, require_title=strict)
        if ok:
            kept.append(it)
        else:
            dropped.append((reason, it.get("source_name", ""), it.get("title", "")[:40]))
    if dropped:
        print(f"  （非 AI 丢弃 {len(dropped)} 条）")
        for reason, src, title in dropped[:8]:
            print(f"      - [{src}] {title} · {reason}")
    return kept


def dedupe(items: list[dict]) -> list[dict]:
    """两级去重：链接（去 tracking 参数后）+ 标题相似度。

    同一事件常被 3~4 个源同时报道（文心 5.5 三条、Claude Code 人事三条），
    只按链接去重完全无效。这里保留可信度权重最高的那条。
    """
    for it in items:
        it["source_weight"] = reliability_of(it.get("source_type", "selfmedia"))["weight"]
    return dedupe_items(items, title_key="title", link_key="link",
                        weight_key="source_weight", threshold=0.76,
                        guard_numbers=True)


def cap_per_source(items: list[dict], max_per_source: int) -> list[dict]:
    items.sort(key=lambda x: parse_pubdate(x.get("pubDate", "")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    by_src = {}
    out = []
    for it in items:
        sid = it.get("source_id", "")
        by_src[sid] = by_src.get(sid, 0) + 1
        if by_src[sid] <= max_per_source:
            out.append(it)
    return out


def main():
    print("=" * 70)
    print(f"AI Frontier · 自动采集 v4 · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"时间窗口：最近 {HOURS_WINDOW} 小时")
    print(f"RSS 源：{len(RSS_SOURCES)} 个 + GitHub 高星项目（补充）")
    print("=" * 70)

    all_items = []
    stats = {"ok": 0, "fail": 0}
    fail_log = []  # 详细失败日志（v4 新增）

    # 1. RSS 源
    for src in RSS_SOURCES:
        items = fetch_source(src)
        if items:
            stats["ok"] += 1
            all_items.extend(items)
        else:
            stats["fail"] += 1
            fail_log.append((src["name"], src["url"]))
        time.sleep(0.3)

    # 2. GitHub 高星项目（v4：国内访问不稳，失败不阻塞整体）
    gh_items = []
    try:
        gh_items = fetch_github_trending()
    except Exception as e:
        print(f"  → GitHub 高星项目整体失败（国内网络限制）：{type(e).__name__}: {e}")
        print(f"    （已跳过，不影响 RSS 主流程）")
    all_items.extend(gh_items)

    # 失败摘要（v4 新增）
    print(f"\nRSS 源成功：{stats['ok']} / 失败：{stats['fail']}（共 {len(RSS_SOURCES)}）")
    if fail_log:
        print(f"\n📋 失败清单（{len(fail_log)} 个）：")
        for name, url in fail_log[:8]:
            print(f"    ✗ {name:<16} {url}")
        if len(fail_log) > 8:
            print(f"    ... 还有 {len(fail_log)-8} 个")
    print(f"GitHub 项目：{len(gh_items)} 个（补充源，国内不稳）")
    print(f"原始条目：{len(all_items)}")

    all_items = dedupe(all_items)
    print(f"去重后：{len(all_items)}")

    all_items = filter_recent(all_items, HOURS_WINDOW)
    print(f"时间过滤后：{len(all_items)}")

    all_items = filter_paywall(all_items)
    all_items = filter_ai_relevant(all_items)
    print(f"AI 相关性过滤后：{len(all_items)}")

    # 跨源标题去重（同一事件保留最高可信度源）
    all_items = dedupe(all_items)
    print(f"跨源去重后：{len(all_items)}")

    all_items = cap_per_source(all_items, MAX_PER_SOURCE)
    print(f"单源上限后：{len(all_items)}")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_hours": HOURS_WINDOW,
        "sources_total": len(RSS_SOURCES) + len(GITHUB_CONFIG["queries"]),
        "sources_ok": stats["ok"],
        "items_total": len(all_items),
        "items": all_items,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已写入 {OUTPUT_FILE}")

    # 可信度分布
    from collections import Counter
    rel_cnt = Counter(it.get("reliability_level", "?") for it in all_items)
    print(f"\n📊 可信度分布：")
    for lvl, n in sorted(rel_cnt.items()):
        print(f"    {lvl} 级：{n} 条")

    print("\n下一步：python score_and_summarize.py --mode llm")


if __name__ == "__main__":
    main()