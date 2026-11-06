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
from content_quality import strip_html

INPUT_FILE = _Path(__file__).parent / "data" / "raw_play.json"
OUTPUT_FILE = _Path(__file__).parent / "data" / "scored_play.json"


PLAY_PROMPT = """你是 AI 玩法推荐编辑。给你一条玩法项目（可能是 prompt 模板、工具工作流、可在线试的 Demo、教程）。

【标题】{title}
【来源】{source}
【描述】{description}
【链接】{link}
【玩法类型】{play_type}

请严格按 JSON 格式返回（不要 Markdown 代码块包装，不要其他文字）：
{{
  "title_zh": "<中文标题，≤25字，说清『用什么做什么』，不要写成新闻标题>",
  "summary_zh": "<中文一句话摘要，≤80字，说清能产出什么>",
  "why_try": "<为什么值得试，≤100字。必须写出至少一个具体点：上手耗时 / 需要什么工具或账号 / 产出物是什么 / 适合谁>",
  "difficulty": <1-5 整数; 5=复制 prompt 就能用, 4=打开网页就能试, 3=本地装环境 30 分钟内, 2=要配依赖或改代码, 1=需工程基础>,
  "playability_score": <0-10 小数; 综合考虑: 是否能立即用、可复制度、有趣程度>
}}

【硬性要求】
- why_try 里**不要**写"可直接按 GitHub 链接运行"，除非链接确实以 github.com 开头
- 如果链接不是 GitHub，就不要提 GitHub
- 不要写"值得一试""非常实用"这类空话，要给具体信息
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
    """LLM 失败时的回退文案。

    旧版这里固定返回「可直接按 GitHub 链接运行」，而 45 条里有 25 条链接根本不在
    GitHub 上——这是事实错误，比文案模板化更伤可信度。现在按玩法类型给出
    各不相同、且与真实链接一致的说明。
    """
    title = strip_html(item.get("title", ""))
    desc = strip_html(item.get("description", ""))
    link = item.get("link", "") or ""
    host = ""
    try:
        from urllib.parse import urlsplit
        host = urlsplit(link).netloc.lower()
    except ValueError:
        pass
    is_github = "github.com" in host
    is_demo = item.get("play_type") == "runnable_demo" or "huggingface.co" in host
    tools = item.get("tools") or []
    tool = tools[0] if tools and tools[0] != "未标注" else "这个工具"
    minutes = (item.get("time_estimate") or "30min").replace("min", " 分钟").replace("1h", "1 小时")

    if is_demo:
        why = "打开链接即可在浏览器里试用，不用装环境；先用默认示例跑一遍，再换成自己的输入。"
    elif is_github:
        why = f"仓库 README 里有安装命令和示例，照着跑通大约 {minutes}；建议先看 issues 里的踩坑记录。"
    elif item.get("play_type") == "prompt":
        why = f"把提示词整段复制给 {tool}，换成自己的素材即可，不需要写代码。"
    elif item.get("play_type") == "tutorial":
        why = f"按文中步骤走一遍约 {minutes}，遇到报错可对照原文的截图和命令逐条核对。"
    else:
        why = f"文中有可复用的操作步骤，照着做约 {minutes}；建议先读完整流程再动手。"

    return {
        "title_zh": title[:60],
        "summary_zh": (desc or title)[:120],
        "why_try": why,
        "difficulty": item.get("difficulty", 3),
        "playability_score": 6.0,
    }


def _sanitize_llm_result(r: dict, item: dict) -> dict:
    """清洗 LLM 输出：去 HTML 标签、修正与链接不符的表述。"""
    out = {
        "title_zh": strip_html(r.get("title_zh", ""), max_len=60) or strip_html(item.get("title", ""), 60),
        "summary_zh": strip_html(r.get("summary_zh", "") or r.get("summary", ""), max_len=200),
        "why_try": strip_html(r.get("why_try", ""), max_len=220),
        "difficulty": int(r.get("difficulty", item.get("difficulty", 3)) or 3),
        "playability_score": round(float(r.get("playability_score", 6.0) or 6.0), 1),
    }
    out["difficulty"] = max(1, min(5, out["difficulty"]))
    out["playability_score"] = max(0.0, min(10.0, out["playability_score"]))
    # 链接不在 GitHub 时，禁止出现「按 GitHub 链接运行」这类事实错误
    if "github" in out["why_try"].lower() and "github.com" not in (item.get("link") or "").lower():
        out["why_try"] = fallback(item)["why_try"]
    if not out["summary_zh"]:
        out["summary_zh"] = fallback(item)["summary_zh"]
    if not out["why_try"]:
        out["why_try"] = fallback(item)["why_try"]
    return out


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

        # 中文条目也要过 LLM：旧版直接跳过，导致 why_try 只能套模板句，
        # 45 条里 25 条文案完全相同且与链接事实不符。
        if use_llm:
            try:
                r = call_llm(it, api_key)
                it.update(_sanitize_llm_result(r, it))
                success += 1
                print(f" -> \u2713")
            except Exception as e:
                print(f" -> \u26a0\ufe0f {type(e).__name__}, 回退规则")
                it.update(fallback(it))
                failed += 1
        else:
            it.update(fallback(it))

        # 与页面统计口径保持一致：可立即试用 = runnable_demo
        it["is_demo"] = it.get("play_type") == "runnable_demo"
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
