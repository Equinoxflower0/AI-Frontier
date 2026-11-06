"""
score_and_summarize.py
======================
全球 AI 前沿资讯网站 - LLM 评分 + 摘要 (v2)

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

# 内容质量：清洗 LLM 输出里的 HTML / 链接
from content_quality import strip_html, clean_link, dedupe_items

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
        "ai_related": True,
        "score": score,
        "summary_zh": summary,
        "title_zh": title if lang == "zh" else f"[EN] {title}",
        "category": _normalize_category(category),
        "need_translate": need_translate,
        "reasons": reasons,
    }


# ============================================================
# LLM 调用（豆包 / OpenAI / DeepSeek 通用）
# ============================================================

LLM_PROMPT_TEMPLATE = """你是一个 AI 行业编辑，只做三件事：判断这条值不值得看、用一句话说清是什么、指出它为什么重要。

【标题】{title}
【来源】{source}
【来源类型】{source_type_label}（可信度 {reliability_level} 级）
【原文摘要】{description}
【原文链接】{link}

请严格按 JSON 格式返回（不要 Markdown 代码块包装，不要其他文字）：
{{
  "ai_related": <true|false; 这条新闻的核心是否与 AI / 大模型 / 智能体 / AI 芯片 / AI 应用直接相关>,
  "title_zh": "<中文标题，≤25字，保留关键主体与数字，不要夸张>",
  "summary": "<一句话说清发生了什么，≤80字，只陈述事实，不加评价>",
  "why_important": "<为什么重要，≤120字>",
  "score": <0-10 的重要性评分，保留 1 位小数>,
  "category": "<大模型|开源|论文|产业|工具|观点|综合>"
}}

【分类口径，必须严格遵守】
- 大模型：新模型发布、能力升级、模型能力评测
- 开源：开源项目、开源权重、开发者工具链
- 论文：论文、技术报告、研究成果
- 产业：AI 公司的融资/并购/财报/合作/人事变动。**非 AI 公司的商业新闻（消费、医美、地产、汽车销量、图库版权）不属于此类**，应判 ai_related=false
- 工具：面向用户的 AI 产品与应用
- 观点：评论、访谈、行业分析
- 综合：以上都不属于

【why_important 写法，这是全站最值钱的部分】
不要写"反映了……标志着……意味着……将对……产生影响"这类套话。必须给出具体判断，回答下面至少两点：
- 谁需要关注（哪类从业者/公司/开发者）
- 具体改变了什么（成本、能力边界、可用性、竞争格局）
- 下一步该看什么
示例（好）："推理成本降到每百万 token 0.5 元后，原先跑不起的长文档客服场景变得可行，做垂直 SaaS 的团队可以直接把上下文从 8K 拉到 128K。"
示例（差）："这标志着大模型成本进一步下降，将对行业产生深远影响。"

【评分】
- 时效性、影响力、话题热度、来源可信度综合判断；自媒体/个人来源应给较低分
- 与 AI 无关的条目：ai_related=false，score 给 0-2 分"""


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
            ai_related = r.get("ai_related", True)
            if isinstance(ai_related, str):
                ai_related = ai_related.strip().lower() not in ("false", "0", "no", "否")
            out.append({
                "ai_related": bool(ai_related),
                "score": float(r.get("score", 5)),
                "summary_zh": strip_html(r.get("summary", ""), max_len=200) or item.get("title", ""),
                "title_zh": strip_html(r.get("title_zh", ""), max_len=80) or item.get("title", ""),
                "why_important": strip_html(r.get("why_important", ""), max_len=300),
                "category": _normalize_category(r.get("category")),
                "reasons": ["LLM 生成"],
            })
            time.sleep(0.3)
        except Exception as e:
            print(f"    ⚠ LLM 调用失败: {type(e).__name__}: {e}，回退到规则")
            out.append(rule_score(item))
    return out


# ============================================================
# 分类归一化 + 板块配比控制
# ============================================================

VALID_CATEGORIES = ("大模型", "开源", "论文", "产业", "工具", "观点", "综合")

# 单个板块最多占当日条目的比例（超出部分沉到列表末尾，不删除）
CATEGORY_CAP_RATIO = {"产业": 0.30, "综合": 0.15}


def _normalize_category(raw) -> str:
    """把 LLM 返回的分类收敛到 7 个合法值。"""
    if not raw:
        return "综合"
    raw = str(raw).strip()
    if raw in VALID_CATEGORIES:
        return raw
    for c in VALID_CATEGORIES:
        if c in raw:
            return c
    aliases = {
        "模型": "大模型", "开源项目": "开源", "研究": "论文", "学术": "论文",
        "商业": "产业", "融资": "产业", "产品": "工具", "应用": "工具",
        "技术": "工具", "社区": "开源",
        "评论": "观点", "分析": "观点",
    }
    return aliases.get(raw, "综合")


def balance_categories(items: list[dict], caps: dict = None) -> list[dict]:
    """控制板块配比：产业板块不超过 30%，超出的沉到末尾。

    列表本身已按分数倒序，这里只做「同分段的位次调整」，
    避免一天 50% 版面都是融资/股价/人事这类产业新闻。
    """
    caps = caps or CATEGORY_CAP_RATIO
    total = len(items)
    limits = {c: max(1, int(total * r)) for c, r in caps.items()}
    used = {}
    head, overflow = [], []
    for it in items:
        cat = it.get("category", "综合")
        limit = limits.get(cat)
        if limit is not None and used.get(cat, 0) >= limit:
            overflow.append(it)
            continue
        used[cat] = used.get(cat, 0) + 1
        head.append(it)
    if overflow:
        print(f"  ↳ 板块配比：{len(overflow)} 条超出比例限额，已排到列表末尾 "
              f"({', '.join(f'{c}≤{int(r*100)}%' for c, r in caps.items())})")
    return head + overflow


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

    # LLM 判定与 AI 无关的条目直接剔除（规则模式无该字段，全部保留）
    if mode == "llm":
        before = len(enriched)
        enriched = [e for e in enriched if e.get("ai_related", True)]
        if before != len(enriched):
            print(f"  ↳ AI 相关性判定剔除 {before - len(enriched)} 条")

    # LLM 会重写标题，重复要在打分后再判一次（用重写后的中文标题）。
    # 之前只按原始标题去重，「智象梅涛提出智能体化全模态世界模型」和
    # 「智象梅涛提出智能体化世界模型」这种改写后高度相似的会漏掉。
    before = len(enriched)
    enriched = dedupe_items(enriched, title_key="title_zh", link_key="link",
                            weight_key="score", threshold=0.80,
                            guard_numbers=True)
    if before != len(enriched):
        print(f"  ↳ 标题去重删除 {before - len(enriched)} 条重复")

    # 板块配比：产业 ≤30%、综合 ≤15%，超出部分沉到末尾
    enriched = balance_categories(enriched)

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