"""
fetch_ai_play.py
================
AI玩法实验室 - 自动化采集脚本

数据源（按优先级）：
  1. GitHub awesome-* 主题仓库（S级官方/高可信）
  2. HuggingFace Spaces 热门（A级官方）
  3. Reddit r/ChatGPT / r/LocalLLaMA 月度精华（B级社区）
  4. Product Hunt AI 频道（B级社区）

输出：
  scripts/data/raw_play.json —— 每条玩法条目带 6 个玩法专属字段
"""

import sys
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path as _Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from xml.etree import ElementTree as ET
from html import unescape
from pathlib import Path

sys.path.insert(0, str(_Path(__file__).parent))
import _utf8  # noqa: F401

from sources_play_config import (
    AWESOME_REPOS, HF_CONFIG, PRODUCT_HUNT_RSS, REDDIT_RSS,
    DOMESTIC_PLAY_SOURCES,  # v4 新增：国内玩法源
    infer_play_type, infer_tools, infer_difficulty, infer_copyable_score,
    TIME_ESTIMATE_DEFAULT,
)
from sources_config import reliability_of, RELIABILITY_LEVELS

OUTPUT_FILE = Path(__file__).parent / "data" / "raw_play.json"
USER_AGENT = "AI-Frontier-Play-Bot/1.0 (+https://ai-frontier.com)"


# ============================================================
# 工具函数
# ============================================================

def _get(url, timeout=20, retries=4, accept=None):
    """带重试 + gzip/deflate 自动解压的 GET 请求（v4 强化）"""
    import gzip
    import zlib
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
    }
    if accept:
        headers["Accept"] = accept
    last_err = None
    for attempt in range(retries):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                # 自动解压（v4）
                enc = resp.headers.get("Content-Encoding", "").lower()
                if enc == "gzip":
                    try:
                        raw = gzip.decompress(raw)
                    except (OSError, EOFError):
                        pass
                elif enc == "deflate":
                    try:
                        raw = zlib.decompress(raw)
                    except zlib.error:
                        pass
                ct = resp.headers.get("Content-Type", "")
                encoding = "utf-8"
                if "charset=" in ct:
                    encoding = ct.split("charset=", 1)[1].split(";")[0]
                return raw.decode(encoding, errors="replace")
        except (URLError, HTTPError, TimeoutError) as e:
            last_err = e
            print(f"    retry {attempt+1}/{retries}: {type(e).__name__}: {e}")
            time.sleep(1.5 ** attempt)  # 指数退避
    print(f"    all retries failed: {last_err}")
    return None


def _enrich(item: dict) -> dict:
    """为每条玩法补全元数据"""
    item.setdefault("play_type", infer_play_type(item))
    item.setdefault("difficulty", infer_difficulty(item))
    item.setdefault("copyable_score", infer_copyable_score(item))
    item.setdefault("tools", infer_tools(item))
    item.setdefault("time_estimate", TIME_ESTIMATE_DEFAULT.get(item["play_type"], "30min"))
    item.setdefault("is_demo", item["play_type"] == "runnable_demo")

    src_type = item.get("source_type", "community")
    rl = reliability_of(src_type)
    item["source_tier"] = rl["level"]
    item["source_color"] = rl["color"]
    item["source_emoji"] = rl["emoji"]
    item["source_label"] = rl["label"]
    item["source_weight"] = rl["weight"]
    return item


# ============================================================
# 1. GitHub awesome 系列 + 高 star 项目
# ============================================================

def _fetch_github_search(query: str, min_stars: int, limit: int = 5):
    """用 GitHub Search API 查 repo"""
    import urllib.parse
    q = urllib.parse.quote(query)
    url = (
        f"https://api.github.com/search/repositories"
        f"?q={q}+stars:>{min_stars}&sort=stars&order=desc"
    )
    data = _get(url, accept="application/vnd.github+json")
    if not data:
        return []
    try:
        j = json.loads(data)
        return j.get("items", [])[:limit]
    except Exception as e:
        print(f"    json parse fail: {e}")
        return []


def collect_github():
    """抓 awesome 系列 + 高 star 项目，返回玩法条目的 dict 列表"""
    out = []
    print("[1/4] GitHub awesome + 高 star ...")
    for cfg in AWESOME_REPOS:
        q = cfg["query"]
        repos = _fetch_github_search(cfg["query"], cfg["min_stars"], limit=3)
        for r in repos:
            full = r.get("full_name", "")
            desc = (r.get("description") or "").strip()
            out.append({
                "title": f"{full}: {(desc or q)[:50]}",
                "link": r.get("html_url"),
                "description": (
                    f"⭐ {r.get('stargazers_count', 0)} stars · "
                    f"{r.get('language') or 'N/A'} · "
                    f"{desc[:200]}"
                ),
                "pubDate": r.get("updated_at", "")[:10],
                "source_id": f"github-play-{q}",
                "source_name": f"GitHub {cfg['name']}",
                "source_category": "玩法",
                "source_lang": "en",
                "source_type": cfg["source_type"],
                "play_type": cfg["play_type"],
                "is_demo": False,
                "_raw": {"stars": r.get("stargazers_count", 0),
                         "language": r.get("language")},
            })
        time.sleep(0.3)
    print(f"  ✓ GitHub: {len(out)} 条")
    return out


# ============================================================
# 2. HuggingFace Spaces（按 likes 排序）
# ============================================================

def collect_hf():
    """抓 HuggingFace Spaces trending"""
    out = []
    print("[2/4] HuggingFace Spaces ...")
    url = HF_CONFIG["api_url"] + HF_CONFIG["params"]
    data = _get(url, accept="application/json", timeout=20)
    if not data:
        print("  ✗ HF fetch failed")
        return out
    try:
        spaces = json.loads(data)
    except Exception as e:
        print(f"    json parse fail: {e}")
        return out

    keywords = HF_CONFIG["filter_keywords"]
    count = 0
    for sp in spaces:
        if count >= HF_CONFIG["max_results"]:
            break
        sid = sp.get("id", "")
        likes = sp.get("likes", 0)
        if likes < 5:
            continue
        # 只保留 AI 类相关的（关键字匹配，空过跳过）
        if not any(k in sid.lower() for k in keywords):
            continue
        sdk = (sp.get("sdk") or "gradio").strip()
        out.append({
            "title": sid.replace("-", " ").title(),
            "link": f"https://huggingface.co/spaces/{sid}",
            "description": (
                f"HF Spaces · ❤ {likes} · SDK: {sdk} · "
                f"{(sp.get('description') or '点击立即试用')[:180]}"
            ),
            "pubDate": sp.get("lastModified", "")[:10],
            "source_id": f"hf-space-{sid}",
            "source_name": "HuggingFace Spaces",
            "source_category": "玩法",
            "source_lang": "en",
            "source_type": "media",  # HF Spaces 视为权威平台
            "play_type": "runnable_demo",
            "is_demo": True,
            "_raw": {"likes": likes, "sdk": sdk},
        })
        count += 1
    print(f"  ✓ HF Spaces: {len(out)} 条")
    return out


# ============================================================
# 3. Reddit（r/ChatGPT / r/LocalLLaMA 精华贴，按月）
# ============================================================

def _parse_rss(xml_text: str) -> list[dict]:
    """解析 RSS 2.0 / Atom 通用格式（v4：支持博客园 Atom 等）"""
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    # === RSS 2.0: <item> 标签 ===
    for item in root.iter("item"):
        title_el = item.find("title")
        link_el = item.find("link")
        desc_el = item.find("description")
        date_el = item.find("pubDate")
        if title_el is None or link_el is None:
            continue
        items.append({
            "title": (title_el.text or "").strip(),
            "link": (link_el.text or "").strip(),
            "description": unescape((desc_el.text or "").strip())[:300] if desc_el is not None else "",
            "pubDate": (date_el.text or "").strip() if date_el is not None else "",
        })

    # === Atom: <entry> 标签（博客园 / SegmentFault 等） ===
    ns_atom = "{http://www.w3.org/2005/Atom}"
    for entry in root.iter(ns_atom + "entry"):
        title_el = entry.find(ns_atom + "title")
        # Atom link 用 href 属性
        link = ""
        for link_el in entry.findall(ns_atom + "link"):
            href = link_el.get("href", "")
            rel = link_el.get("rel", "alternate")
            if href and rel in ("alternate", ""):
                link = href
                break
        if not link:
            link_el = entry.find(ns_atom + "link")
            if link_el is not None:
                link = link_el.get("href", "")
        desc_el = entry.find(ns_atom + "summary") or entry.find(ns_atom + "content")
        date_el = entry.find(ns_atom + "published") or entry.find(ns_atom + "updated")
        if title_el is None:
            continue
        items.append({
            "title": (title_el.text or "").strip(),
            "link": link.strip(),
            "description": unescape((desc_el.text or "").strip())[:300] if desc_el is not None else "",
            "pubDate": (date_el.text or "").strip() if date_el is not None else "",
        })

    return items


def collect_reddit():
    """抓 Reddit 月度精华"""
    out = []
    print("[3/4] Reddit AI 子版精华 ...")
    for cfg in REDDIT_RSS:
        data = _get(cfg["url"], timeout=20)
        if not data:
            print(f"  ✗ {cfg['name']} failed")
            continue
        items = _parse_rss(data)
        for it in items[:8]:  # 每源取前 8
            if not it["link"]:
                continue
            out.append({
                "title": it["title"][:80],
                "link": it["link"],
                "description": it["description"][:300],
                "pubDate": (it["pubDate"] or "")[:16],
                "source_id": cfg["id"],
                "source_name": cfg["name"],
                "source_category": "玩法",
                "source_lang": cfg["lang"],
                "source_type": cfg["source_type"],
                "play_type": infer_play_type(it),
            })
        print(f"  ✓ {cfg['name']}: {min(8, len(items))} 条")
        time.sleep(0.3)
    return out


# ============================================================
# 4. Product Hunt（AI 频道）
# ============================================================

def collect_producthunt():
    """抓 Product Hunt AI 频道"""
    out = []
    print("[4/4] Product Hunt ...")
    for cfg in PRODUCT_HUNT_RSS:
        data = _get(cfg["url"], timeout=20)
        if not data:
            print(f"  ✗ {cfg['name']} failed")
            continue
        items = _parse_rss(data)
        for it in items[:8]:
            if not it["link"]:
                continue
            out.append({
                "title": it["title"][:80],
                "link": it["link"],
                "description": it["description"][:300],
                "pubDate": (it["pubDate"] or "")[:16],
                "source_id": cfg["id"],
                "source_name": cfg["name"],
                "source_category": "玩法",
                "source_lang": "en",
                "source_type": cfg["source_type"],
                "play_type": infer_play_type(it),
            })
        print(f"  ✓ {cfg['name']}: {min(8, len(items))} 条")
        time.sleep(0.3)
    return out


# ============================================================
# 5. 国内玩法源（v4 新增：少数派/智东西/爱范儿/掘金/博客园）
# ============================================================

def collect_domestic():
    """抓国内玩法源（少数派/智东西/爱范儿/掘金/博客园），严格 AI 关键词过滤 + 排除词过滤"""
    out = []
    print("[5/5] 国内玩法源 ...")
    for cfg in DOMESTIC_PLAY_SOURCES:
        data = _get(cfg["url"], timeout=20)
        if not data:
            print(f"  ✗ {cfg['name']} 抓取失败（不影响其他源）")
            continue
        items = _parse_rss(data)
        if not items:
            print(f"  ✗ {cfg['name']} 解析为空")
            continue

        # 严格过滤：标题或描述必须含 AI 关键词，且不能含排除关键词
        keywords = [k.lower() for k in cfg.get("filter_keywords", [])]
        exclude = [k.lower() for k in cfg.get("exclude_keywords", [])]
        max_n = cfg.get("max_results", 8)
        filtered = []
        for it in items:
            title = (it.get("title", "")).lower()
            desc = (it.get("description", "")).lower()
            text = title + " " + desc
            # 排除关键词命中 → 跳过
            if any(k in text for k in exclude):
                continue
            # AI 关键词必须在标题或描述中出现
            if any(k in text for k in keywords):
                filtered.append(it)
            if len(filtered) >= max_n:
                break

        if not filtered:
            print(f"  ⚠ {cfg['name']}: 严格过滤后无 AI 相关内容（这源暂时不产出）")
            continue

        print(f"  ✓ {cfg['name']}: {len(filtered)} 条玩法（严格 AI 匹配）")

        for it in filtered:
            out.append({
                "title": it["title"][:80],
                "link": it["link"],
                "description": it["description"][:300],
                "pubDate": (it["pubDate"] or "")[:16],
                "source_id": cfg["id"],
                "source_name": cfg["name"],
                "source_category": "玩法",
                "source_lang": cfg.get("lang", "zh"),
                "source_type": cfg["source_type"],
                "play_type": cfg.get("play_type", "tool_chain"),
                "is_domestic": True,  # 国内源标记
            })
        time.sleep(0.3)
    return out


# ============================================================
# 去重 + 主流程
# ============================================================

def _normalize_link(link: str) -> str:
    """统一 GitHub / HF 链接，做去重 key"""
    if not link:
        return ""
    link = link.split("?")[0].rstrip("/").lower()
    return link


def dedupe(items: list[dict]) -> list[dict]:
    """按 link 去重"""
    seen = set()
    out = []
    for it in items:
        k = _normalize_link(it.get("link", ""))
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


def main():
    started = datetime.now(timezone.utc).isoformat()
    print(f"🎮 AI玩法实验室 · 抓取开始\n")

    all_items = []
    all_items.extend(collect_github())       # 1. GitHub awesome
    all_items.extend(collect_hf())           # 2. HF Spaces
    all_items.extend(collect_reddit())       # 3. Reddit
    all_items.extend(collect_producthunt())  # 4. Product Hunt
    all_items.extend(collect_domestic())     # 5. v4 国内玩法源

    # 去重
    all_items = dedupe(all_items)

    # 补全元数据
    all_items = [_enrich(it) for it in all_items]

    # 按"可复制度 + 可信度"排序（同权重优先级：可复制度 ↑ + S级信任 ↑）
    def sort_key(it):
        copy_score = -it.get("copyable_score", 3)  # 高可复制度在前
        diff = -it.get("difficulty", 3)             # 难度高(简单)在前
        wt = -it.get("source_weight", 1.0)
        return (copy_score, diff, wt)
    all_items.sort(key=sort_key)

    # 统计
    by_type = {}
    by_tier = {}
    for it in all_items:
        by_type[it["play_type"]] = by_type.get(it["play_type"], 0) + 1
        by_tier[it["source_label"]] = by_tier.get(it["source_label"], 0) + 1

    result = {
        "items": all_items,
        "items_total": len(all_items),
        "by_type": by_type,
        "by_tier": by_tier,
        "fetched_at": started,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n========================================")
    print(f"\U0001f3ae 共抓取 {len(all_items)} 条玩法")
    print(f"  按玩法类型: {by_type}")
    print(f"  按可信度等级: {by_tier}")
    print(f"  输出文件: {OUTPUT_FILE}")
    print(f"========================================")


if __name__ == "__main__":
    main()
