"""
score_and_summarize.py
======================
全球 AI 前沿咨询网站 - LLM 评分 + 摘要 (v2)

输入：scripts/data/raw_news.json
输出：scripts/data/scored_news.json

支持两种模式：
  - llm  : 调用大模型生成摘要、打分、翻译（推荐，需 API key）
  - rule : 纯规则打分 + 简单摘要（无 API 也能跑，演示用）

使用：
  export DOUBAO_API_KEY=xxx  # 或 OPENAI_API_KEY
  python score_and_summarize.py --mode llm

  # 或无 key 跑 demo
  python score_and_summarize.py --mode rule
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

sys.path.insert(0, str(Path(__file__).parent))
import _utf8  # noqa: F401  —— 强制 UTF-8 输出，防止 GBK 控制台崩溃

# 共享配置：可信度分级
from sources_config import reliability_of

INPUT_FILE = Path(__file__).parent / "data" / "raw_news.json"
OUTPUT_FILE = Path(__file__).parent / "data" / "scored_news.json"

# ============================================================
# 自动加载 .env（如果存在）
# ============================================================

def load_dotenv():
    """从项目根目录 .env 加载环境变量（不覆盖已设置的值）"""
    env_file = Path(__file__).parent.parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if key and key not in os.environ:
            os.environ[key] = val

load_dotenv()

# ============================================================
# 关键词权重（打分用）
# ============================================================

KEYWORDS_HIGH = [
    # 大模型相关
    "GPT-", "Claude", "Gemini", "Llama", "DeepSeek", "Qwen", "GLM", "Grok",
    "release", "launch", "发布", "推出", "上线",
    "open-source", "开源", "benchmark", "评测",
    "agent", "Agent", "智能体",
    # 产业相关
    "funding", "raise", "valuation", "融资", "估值", "B 轮", "IPO", "acquisition", "收购",
    "partnership", "合作",
    # 论文相关
    "paper", "arxiv", "论文", "study", "research", "survey",
]

KEYWORDS_MED = [
    "model", "LLM", "大模型", "AI", "artificial intelligence", "机器学习",
    "training", "训练", "fine-tune", "微调", "RAG", "embedding",
    "vision", "multimodal", "多模态", "图像", "video",
    "regulation", "监管", "policy", "政策",
]

KEYWORDS_LOW = [
    "tips", "tutorial", "教程", "guide", "指南", "opinion", "观点",
    "interview", "访谈", "podcast", "播客",
]


# ============================================================
# 规则打分（无 LLM 也能跑）
# ============================================================

def rule_score(item: dict) -> dict:
    """基于规则的评分与简单摘要"""
    title = item.get("title", "")
    desc = item.get("description", "")
    text = (title + " " + desc).lower()

    score = 5.0  # 基础分
    reasons = []

    # 来源可信度加权
    stype = item.get("source_type", "selfmedia")
    rel = reliability_of(stype)
    rel_weight = rel["weight"]
    score *= rel_weight
    if rel_weight != 1.0:
        reasons.append(f"{rel['emoji']} {rel['label']} 可信度 ×{rel_weight}")

    # 关键词加权
    high_hits = sum(1 for kw in KEYWORDS_HIGH if kw.lower() in text)
    med_hits = sum(1 for kw in KEYWORDS_MED if kw.lower() in text)
    low_hits = sum(1 for kw in KEYWORDS_LOW if kw.lower() in text)

    if high_hits >= 2:
        score += 1.8
        reasons.append(f"高价值词 ×{high_hits} +1.8")
    elif high_hits == 1:
        score += 1.0
        reasons.append("高价值词 ×1 +1.0")

    if med_hits >= 3:
        score += 0.6
    elif med_hits >= 1:
        score += 0.3

    if low_hits >= 1 and high_hits == 0:
        score -= 0.5
        reasons.append("内容偏教程/观点 -0.5")

    # 描述长度加成
    if len(desc) > 200:
        score += 0.3
        reasons.append("有详细描述 +0.3")

    # GitHub 高 star 加成
    stars = item.get("stars", 0)
    if stars >= 1000:
        score += 1.5
        reasons.append(f"⭐ {stars} stars +1.5")
    elif stars >= 300:
        score += 0.8
        reasons.append(f"⭐ {stars} stars +0.8")

    score = max(0.0, min(10.0, round(score, 1)))

    # 简单摘要
    lang = item.get("source_lang", "en")
    if desc and len(desc) > 20:
        summary = desc[:80].rstrip(",.;: ") + "…"
    else:
        summary = title[:80]

    need_translate = lang == "en"

    category = item.get("source_category", "综合")
    if any(k in text for k in ["paper", "arxiv", "论文", "survey"]):
        category = "论文"
    elif any(k in text for k in ["funding", "raise", "融资", "估值", "B 轮", "ipo"]):
        category = "产业"
    elif any(k in text for k in ["open-source", "开源", "github", "stars"]):
        category = "开源"
    elif any(k in text for k in ["gpt", "claude", "gemini", "llama", "deepseek", "qwen", "glm"]):
        category = "大模型"

    return {
        "score": score,
        "summary_zh": summary,
        "title_zh": title if lang == "zh" else f"[EN] {title}",
        "category": category,
        "need_translate": need_translate,
        "reasons": reasons,
    }


# ============================================================
# LLM 调用（豆包 / OpenAI / DeepSeek 通用）
# ============================================================

LLM_PROMPT_TEMPLATE = """你是一个 AI 资讯编辑，擅长快速提炼要点。

请基于以下资讯，生成中文摘要并评分。

【标题】{title}
【来源】{source}
【来源类型】{source_type_label}（可信度 {reliability_level} 级）
【原文摘要】{description}
【原文链接】{link}

请严格按 JSON 格式返回（不要 Markdown 代码块包装，不要其他文字）：
{{
  "title_zh": "<中文标题，≤25字>",
  "summary": "<一句话中文摘要，≤80字>",
  "why_important": "<为什么重要，≤120字，可选空>",
  "score": <0-10 的重要性评分，保留 1 位小数>,
  "category": "<大模型|开源|论文|产业|工具|观点|综合>"
}}

评分维度：
- 时效性：最近 24h 加分
- 影响力：是否头部厂商/机构/融资/新模型
- 话题热度：是否行业关注焦点
- 来源可信度：官方一手/权威媒体应给更高分，自媒体/个人应给较低分（你给的 score 需要已经考虑来源可信度）"""


def _build_prompt(item: dict) -> str:
    """构造 LLM 提示词（含来源可信度）"""
    rel = reliability_of(item.get("source_type", "selfmedia"))
    return LLM_PROMPT_TEMPLATE.format(
        title=item.get("title", ""),
        source=item.get("source_name", ""),
        source_type_label=f"{rel['emoji']} {rel['label']}",
        reliability_level=rel["level"],
        description=(item.get("description", "") or "")[:500],
        link=item.get("link", ""),
    )


def call_doubao(item: dict, api_key: str, model: str = "doubao-pro-32k") -> dict:
    """调用豆包 (火山方舟) API"""
    import json as _json
    prompt = _build_prompt(item)
    payload = _json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }).encode()
    req = Request(
        "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urlopen(req, timeout=30) as resp:
        result = _json.loads(resp.read().decode())
    text = result["choices"][0]["message"]["content"].strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return _json.loads(text)


def call_openai_compatible(item: dict, api_key: str, base_url: str, model: str) -> dict:
    """调用任意 OpenAI 兼容 API（DeepSeek / 通义千问 / OpenAI）"""
    import json as _json
    prompt = _build_prompt(item)
    payload = _json.dumps({
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
        result = _json.loads(resp.read().decode())
    text = result["choices"][0]["message"]["content"].strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return _json.loads(text)


def llm_score_batch(items: list[dict]) -> list[dict]:
    """批量调用 LLM"""
    api_key = os.environ.get("DOUBAO_API_KEY") or os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("未设置 API key（DOUBAO_API_KEY / OPENAI_API_KEY / DEEPSEEK_API_KEY）")

    use_doubao = bool(os.environ.get("DOUBAO_API_KEY"))
    use_deepseek = bool(os.environ.get("DEEPSEEK_API_KEY"))
    deepseek_model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

    out = []
    for i, item in enumerate(items, 1):
        print(f"  → LLM 评分 [{i}/{len(items)}] {item.get('title', '')[:40]}")
        try:
            if use_doubao:
                r = call_doubao(item, os.environ["DOUBAO_API_KEY"])
            elif use_deepseek:
                r = call_openai_compatible(item, os.environ["DEEPSEEK_API_KEY"],
                                          "https://api.deepseek.com", deepseek_model)
            else:
                r = call_openai_compatible(item, api_key, "https://api.openai.com", "gpt-4o-mini")
            out.append({
                "score": float(r.get("score", 5)),
                "summary_zh": r.get("summary", item.get("title", "")),
                "title_zh": r.get("title_zh", item.get("title", "")),
                "why_important": r.get("why_important", ""),
                "category": r.get("category", item.get("source_category", "综合")),
                "reasons": ["LLM 生成"],
            })
            time.sleep(0.3)
        except Exception as e:
            print(f"    ⚠ LLM 调用失败: {type(e).__name__}: {e}，回退到规则")
            out.append(rule_score(item))
    return out


# ============================================================
# 主流程
# ============================================================

def main(mode: str = "rule"):
    print("=" * 70)
    print(f"AI Frontier · 评分摘要 · mode={mode} · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    if not INPUT_FILE.exists():
        print(f"❌ 输入文件不存在：{INPUT_FILE}")
        print("请先运行：python fetch_ai_news.py")
        return

    with open(INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items", [])
    print(f"📥 加载 {len(items)} 条原始资讯")

    # 评分
    if mode == "llm":
        try:
            scored_meta = llm_score_batch(items)
        except Exception as e:
            print(f"⚠ LLM 模式失败：{e}")
            print("回退到规则模式")
            scored_meta = [rule_score(it) for it in items]
    else:
        print("📐 使用规则评分（无需 API key）")
        scored_meta = [rule_score(it) for it in items]

    # 合并
    enriched = []
    for item, meta in zip(items, scored_meta):
        e = dict(item)
        e.update(meta)
        enriched.append(e)

    # 按评分倒序
    enriched.sort(key=lambda x: x.get("score", 0), reverse=True)

    # 输出
    payload = {
        "generated_at": datetime.now().isoformat(),
        "mode": mode,
        "items_total": len(enriched),
        "items": enriched,
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已写入 {OUTPUT_FILE}")

    # 统计
    from collections import Counter
    cat_cnt = Counter(e.get("category", "?") for e in enriched)
    print("\n📊 分类分布：")
    for c, n in cat_cnt.most_common():
        print(f"    {c:<8} {n:>3} 条")

    top = enriched[:10]
    print(f"\n⭐ TOP 10 高分条目：")
    for i, e in enumerate(top, 1):
        print(f"    {i:>2}. [{e.get('score', 0):>4.1f}] {e.get('title_zh', e.get('title', ''))[:60]}")

    print("\n下一步：python render_brief.py 生成日报 HTML")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="rule", choices=["rule", "llm"],
                        help="rule=规则打分(无需API), llm=调用LLM(需API key)")
    args = parser.parse_args()
    main(args.mode)