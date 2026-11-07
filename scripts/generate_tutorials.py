"""
generate_tutorials.py
====================
AI 玩法实验室 · LLM 教程生成脚本（v1）

输入：scored_play.json + tutorials_cache.json（增量缓存）
输出：更新 tutorials_cache.json

策略：
1. 每天只对前 N 条玩法（按分数排序）生成完整教程，节省 token
2. 缓存：title+url 没变就复用，变了才重新生成
3. 中文玩法直接生成（已经是中文描述）
4. LLM 失败时回退（标记 skip，下次重试）
5. JSON 严格解析（剥 Markdown 包裹）
"""

import json
import os
import re
import sys
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path as _Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

sys.path.insert(0, str(_Path(__file__).parent))
import _utf8  # noqa: F401

from tutorials_schema import TUTORIAL_PROMPT_ZH, TUTORIAL_FIELDS
from content_quality import safe_filename

# ============================================================
# 路径 & 配置
# ============================================================
SCORED_FILE = _Path(__file__).parent / "data" / "scored_play.json"
CACHE_FILE = _Path(__file__).parent / "data" / "tutorials_cache.json"

MAX_NEW_TUTORIALS_PER_DAY = 20   # 每天最多生成 20 篇新教程（防 token 浪费）
MAX_TUTORIALS_TOTAL = 60         # 缓存上限（最热 60 篇）

# 教程排序权重：playability_score * 1.5 + (可复制度 * 0.5)
SORT_WEIGHT_PLAYS = 1.5
SORT_WEIGHT_COPY = 0.5


# ============================================================
# LLM 调用（与 score_play.py 风格一致）
# ============================================================

def call_llm(prompt: str, api_key: str, base_url: str = "https://api.deepseek.com",
             model: str = "deepseek-chat", timeout: int = 60) -> str:
    """调用 DeepSeek 兼容 API，返回原始文本"""
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.4,
        "max_tokens": 2000,
    }).encode()
    req = Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode())
    return result["choices"][0]["message"]["content"].strip()


def parse_llm_json(text: str) -> dict:
    """剥 Markdown 包裹 + 解析 JSON"""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


# ============================================================
# 教程生成主逻辑
# ============================================================

def build_prompt(item: dict) -> str:
    """拼装教程生成的 LLM Prompt"""
    return TUTORIAL_PROMPT_ZH.format(
        title=item.get("title_zh") or item.get("title", "")[:200],
        source=item.get("source_name", "未知来源"),
        source_url=item.get("link", ""),
        play_type=item.get("play_type", "tool_chain"),
        difficulty=item.get("difficulty", 3),
        tools=", ".join(item.get("tools", [])) or "未标注",
        description=(item.get("description") or item.get("summary_zh") or "")[:500],
    )


def generate_one(item: dict, api_key: str) -> dict:
    """对一条玩法生成教程，LLM 失败抛异常"""
    prompt = build_prompt(item)
    text = call_llm(prompt, api_key)
    tutorial = parse_llm_json(text)
    # 字段完整性校验（缺关键字段则视为失败）
    for f in ("intro", "background", "steps", "expected_result", "summary"):
        if f not in tutorial:
            raise ValueError(f"missing field: {f}")
    if not isinstance(tutorial.get("steps"), list) or len(tutorial["steps"]) < 2:
        raise ValueError("steps 数量不足")
    return tutorial


def fallback_tutorial(item: dict) -> dict:
    """LLM 失败时的占位教程（保留卡片展示 + 原文链接）"""
    title = item.get("title_zh") or item.get("title", "未命名玩法")
    return {
        "_fallback": True,
        "intro": f"本玩法来自 {item.get('source_name', '未知来源')}，LLM 暂未生成详细教程，可直接查看原文。",
        "background": item.get("description", "")[:300] or "暂无描述",
        "prerequisites": [],
        "steps": [
            {"title": "查看原文", "content": f"由于 token 限额或网络问题，本玩法暂未生成结构化教程。请直接访问原文链接查看详细内容。", "tip": ""}
        ],
        "expected_result": "",
        "faq": [],
        "variants": [],
        "summary": item.get("summary_zh", "")[:80] or title,
    }


# ============================================================
# 排序 + 缓存管理
# ============================================================

def calc_priority(item: dict) -> float:
    """教程生成优先级：可玩性 * 1.5 + 可复制度 * 0.5 + 难度加成（越简单越优先）"""
    plays = float(item.get("playability_score", 5))
    copy = float(item.get("copyable_score", 3))
    diff = float(item.get("difficulty", 3))  # 5 = 最简单
    return plays * SORT_WEIGHT_PLAYS + copy * SORT_WEIGHT_COPY + diff * 0.3


def load_cache() -> dict:
    """加载教程缓存，兼容空文件"""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_cache(cache: dict):
    """保存教程缓存"""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def cache_signature(item: dict) -> str:
    """缓存签名：title + url 一致则视为同一玩法"""
    return f"{item.get('title', '')[:80]}|{item.get('link', '')[:120]}"


def cache_key(item: dict) -> str:
    """缓存 key：source_id + 标题 hash 前 8 位（解决同源多篇 key 冲突）

    source_id 必须做文件名安全化：HF Space 的 id 形如 "mfakename/Z-Image-Turbo"，
    带斜杠，直接当 key 会把 "/" 带进教程页文件名，Linux 上直接 FileNotFoundError。
    """
    title_hash = hashlib.md5(item.get("title", "").encode("utf-8")).hexdigest()[:8]
    return f"{safe_filename(item.get('source_id', 'unknown'))}-{title_hash}"


# ============================================================
# 主流程
# ============================================================

def main():
    if not SCORED_FILE.exists():
        print(f"[ERROR] 找不到 {SCORED_FILE}，先跑 score_play.py")
        sys.exit(1)

    with open(SCORED_FILE, encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items", [])
    print(f"📚 AI 玩法实验室 · 教程生成")
    print(f"   玩法总数：{len(items)}")

    # 加载 .env（DEEPSEEK_API_KEY）
    env_file = _Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("[WARN] 未配置 DEEPSEEK_API_KEY，全部走 fallback（仅展示原文链接）")
    else:
        print("[OK] 检测到 API key，将 LLM 生成教程")

    # 加载缓存
    cache = load_cache()
    print(f"   缓存命中：{len(cache)} 篇已生成教程")

    # 按优先级排序
    ranked = sorted(items, key=calc_priority, reverse=True)

    # 筛选待生成：不在缓存 OR 缓存签名不一致 OR fallback 占位
    to_generate = []
    for it in ranked:
        ckey = cache_key(it)
        sig = cache_signature(it)
        prev = cache.get(ckey)
        # 没有缓存 或 签名变了 或 上次 fallback → 加入待生成
        if not prev or prev.get("_sig") != sig or prev.get("tutorial", {}).get("_fallback"):
            to_generate.append(it)

    # 限制每天最多生成数量（按优先级取前 N）
    if len(to_generate) > MAX_NEW_TUTORIALS_PER_DAY:
        to_generate = to_generate[:MAX_NEW_TUTORIALS_PER_DAY]
    print(f"   待生成：{len(to_generate)} 篇（按优先级排序）")

    # 真正生成
    generated = 0
    fallback_cnt = 0
    for i, it in enumerate(to_generate, 1):
        ckey = cache_key(it)
        title = (it.get("title_zh") or it.get("title", ""))[:40]
        print(f"  [{i}/{len(to_generate)}] {title} ...", end="")

        tutorial = None
        if api_key:
            try:
                tutorial = generate_one(it, api_key)
                generated += 1
                print(" ✓ LLM")
            except Exception as e:
                print(f" ⚠ {type(e).__name__}: {str(e)[:50]}")
                tutorial = fallback_tutorial(it)
                fallback_cnt += 1
        else:
            tutorial = fallback_tutorial(it)
            fallback_cnt += 1
            print(" ⏭ fallback")

        cache[ckey] = {
            "_sig": cache_signature(it),
            "tutorial": tutorial,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "play_meta": {  # 缓存元数据供渲染使用
                "title_zh": it.get("title_zh") or it.get("title", ""),
                "title_en": it.get("title", ""),
                "source_id": it.get("source_id", ""),
                "source_name": it.get("source_name", ""),
                "source_label": it.get("source_label", ""),
                "source_tier": it.get("source_tier", ""),
                "source_color": it.get("source_color", ""),
                "source_emoji": it.get("source_emoji", ""),
                "play_type": it.get("play_type", "tool_chain"),
                "difficulty": it.get("difficulty", 3),
                "time_estimate": it.get("time_estimate", "30min"),
                "tools": it.get("tools", []),
                "link": it.get("link", ""),
                "is_domestic": it.get("is_domestic", False),
                "tags": it.get("tags", []),
                "playability_score": it.get("playability_score", 5.0),
            },
        }
        time.sleep(0.6)  # API 限流保护

    # 缓存上限：保留优先级最高的 MAX_TUTORIALS_TOTAL 条
    if len(cache) > MAX_TUTORIALS_TOTAL:
        item_map = {cache_key(it): it for it in items}
        sorted_cache_keys = sorted(
            cache.keys(),
            key=lambda k: calc_priority(item_map.get(k, {})),
            reverse=True
        )[:MAX_TUTORIALS_TOTAL]
        cache = {k: cache[k] for k in sorted_cache_keys if k in cache}
        print(f"   缓存清理：保留 {MAX_TUTORIALS_TOTAL} 篇优先级最高的教程")

    save_cache(cache)

    # 统计
    total = len(cache)
    real_cnt = sum(1 for v in cache.values() if not v.get("tutorial", {}).get("_fallback"))
    print(f"\n========================================")
    print(f"📚 教程生成完成")
    print(f"   本次新生成：{generated} 篇（LLM 成功）")
    print(f"   本次 fallback：{fallback_cnt} 篇")
    print(f"   缓存总数：{total} 篇（其中 {real_cnt} 篇高质量）")
    print(f"   输出文件：{CACHE_FILE}")
    print(f"========================================")


if __name__ == "__main__":
    main()