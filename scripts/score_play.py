"""
score_play.py
==============
AI玩法实验室 - LLM 评分+翻译脚本（v1）

输入：raw_play.json
输出：scored_play.json
每条玩法补加：
  - title_zh       中文标题（≤25字）
  - summary_zh     中文摘要（≤80字）
  - why_try        为什么值得试（≤120字）
  - difficulty     由 LLM 重校（基于内容真实难度）
  - llm_score      LLM 的"可玩性"评分 0-10

策略：
  英文玩法调 LLM 翻译/摘要/评分；中文玩法直接用原文标题。
  LLM 失败时优雅回退（保留原文）。
"""

import json
import os
import re
import sys
import time
from pathlib import Path as _Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

sys.path.insert(0, str(_Path(__file__).parent))
import _utf8  # noqa: F401

from sources_config import RELIABILITY_LEVELS, reliability_of

INPUT_FILE = _Path(__file__).parent / "data" / "raw_play.json"
OUTPUT_FILE = _Path(__file__).parent / "data" / "scored_play.json"


PLAY_PROMPT = """你是 AI 玩法推荐编辑。给你一条玩法项目（可能含 prompt、工具工作流、可在线 demo、教程等）。

【标题】{title}
【来源】{source}
【描述】{description}
【链接】{link}
【已知玩法类型】{play_type}

请严格按 JSON 格式返回（不要 Markdown 代码块包装，不要其他文字）：
{{
  "title_zh": "<中文标题，≤25字，让人一眼想试>",
  "summary_zh": "<中文一句话摘要，≤80字，重点说能干什么>",
  "why_try": "<一句话说明为什么值得试，≤120字，结合'5 分钟上手/可复制'等亮点>",
  "difficulty": <1-5 整数; 5=小白复制 prompt 就能用, 4=零代码可跑 Demo, 3=docker 一键部署, 2=需要配环境, 1=需工程基础>,
  "playability_score": <0-10 小数; 综合考虑: 是否能立即用、可复制度、有趣程度>
}}
"""


def call_llm(item: dict, api_key: str, base_url: str = "https://api.deepseek.com",
             model: str = "deepseek-chat") -> dict:
    """调用 DeepSeek/OpenAI 兼容 API"""
    prompt = PLAY_PROMPT.format(
        title=item.get("title", "")[:200],
        source=item.get("source_name", ""),
        description=(item.get("description", "") or "")[:400],
        link=item.get("link", ""),
        play_type=item.get("play_type", "tool_chain"),
    )
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }).encode()
    req = Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode())
    text = result["choices"][0]["message"]["content"].strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def fallback(item: dict) -> dict:
    """LLM 失败时回退（保持原文 + 规则推断）"""
    title = item.get("title", "")
    return {
        "title_zh": title[:60],  # 截断作显示
        "summary_zh": (item.get("description") or title)[:120],
        "why_try": "可直接按 GitHub 链接运行",
        "difficulty": item.get("difficulty", 3),
        "playability_score": 6.0,
    }


def enrich_with_rel(item: dict) -> dict:
    """补可信度徽章字段（与资讯统一）"""
    rl = reliability_of(item.get("source_type", "community"))
    item["source_tier"] = rl["level"]
    item["source_color"] = rl["color"]
    item["source_emoji"] = rl["emoji"]
    item["source_label"] = rl["label"]
    item["source_weight"] = rl["weight"]
    return item


def main():
    if not INPUT_FILE.exists():
        print(f"[ERROR] 找不到 {INPUT_FILE}，先跑 fetch_ai_play.py")
        sys.exit(1)

    with open(INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items", [])
    print(f"\U0001f3ae 共 {len(items)} 条玩法待翻译/评分")

    # 先读 .env，再读环境变量（.env 优先）
    env_file = _Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    api_key = os.environ.get("DEEPSEEK_API_KEY")

    use_llm = bool(api_key)
    if not use_llm:
        print("[WARN] 未配置 DEEPSEEK_API_KEY，将用规则模式（保留英文原文）")
    else:
        print(f"[OK] 检测到 API key，将 LLM 翻译+评分")

    out_items = []
    success = 0
    failed = 0
    for i, it in enumerate(items, 1):
        title = it.get("title", "")[:50]
        print(f"  [{i}/{len(items)}] {title}", end="")

        # 中文玩法跳过 LLM（保留中文）
        is_chinese = it.get("source_lang") == "zh"

        if use_llm and not is_chinese:
            try:
                r = call_llm(it, api_key)
                it["title_zh"] = r["title_zh"]
                it["summary_zh"] = r["summary_zh"]
                it["why_try"] = r["why_try"]
                it["difficulty"] = r.get("difficulty", it.get("difficulty", 3))
                it["playability_score"] = round(float(r.get("playability_score", 6.0)), 1)
                success += 1
                print(f" -> \u2713")
            except Exception as e:
                print(f" -> \u26a0\ufe0f {type(e).__name__}, 回退规则")
                fb = fallback(it)
                it.update(fb)
                it["playability_score"] = 6.0
                failed += 1
        else:
            fb = fallback(it)
            it.update(fb)
            it["playability_score"] = 6.0

        it = enrich_with_rel(it)
        out_items.append(it)
        time.sleep(0.25)

    # 按 playability * 可信度权重排序
    def sort_key(it):
        return (-it.get("playability_score", 6) * it.get("source_weight", 1.0),
                -it.get("copyable_score", 3))
    out_items.sort(key=sort_key)

    result = {
        "items": out_items,
        "items_total": len(out_items),
        "llm_success": success,
        "llm_failed":  failed,
        "fetched_at": data.get("fetched_at"),
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] 共 {success} 条 LLM 翻译，{failed} 条回退规则")
    print(f"     输出: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
