"""
content_quality.py
==================
内容质量基础设施（资讯 / 玩法共用）

解决的问题：
  1. RSS 摘要把 <a href>、<img src> 原样带进标题/描述，页面上会漏出代码片段
  2. 外链带 utm_source=rss 等追踪参数，还有 http:// 明文
  3. 同一事件被多个源重复收录（文心 5.5 Flash Base 三份）
  4. 通用科技媒体的非 AI 新闻混进 AI 前沿（医美耗材、图库破产、菜谱、双 11）
  5. 付费墙文章（少数派 prime）照收，读者点进去看不到内容
  6. "AI" 作为子串会误匹配 email / air / detail 等英文单词

设计原则：
  - 纯标准库，无第三方依赖
  - 所有函数对 None / 非字符串安全
  - 只做「判定」，不改数据结构；由调用方决定丢弃还是降权
"""

import re
from difflib import SequenceMatcher
from html import unescape
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

# ============================================================
# 一、文本清洗
# ============================================================

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.I | re.S)
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_NL_RE = re.compile(r"\n{2,}")

# 微信/头条导流的尾巴，出现在摘要末尾毫无信息量
_BOILERPLATE = [
    "点击上方蓝字关注我们", "点击上方蓝字关注", "点击蓝字关注我们", "点击蓝字关注",
    "点击关注我们", "点击关注", "关注我们", "扫码关注",
    "阅读原文", "查看全文", "点击阅读原文", "原文链接", "转载请注明",
    "本文来自微信公众号", "微信公众号", "长按识别二维码", "更多精彩内容",
    "原标题：", "责任编辑：", "图片来源：", "题图来自",
]
_BOILERPLATE_RE = re.compile("|".join(re.escape(x) for x in _BOILERPLATE), re.I)


def strip_html(text, max_len=None) -> str:
    """清洗 HTML：去标签、反转义实体、压缩空白、剔除导流尾巴。"""
    if not text or not isinstance(text, str):
        return ""
    s = _SCRIPT_RE.sub(" ", text)
    s = _TAG_RE.sub(" ", s)
    s = unescape(s)
    # 二次清理：实体反转义后可能又冒出标签（&lt;a href=...&gt;）
    if "<" in s and ">" in s:
        s = _TAG_RE.sub(" ", s)
    s = s.replace("\u200b", "").replace("\xa0", " ").replace("\ufeff", "")
    s = _WS_RE.sub(" ", s)
    s = s.replace("\r", "")
    s = _NL_RE.sub("\n", s).strip()
    s = _BOILERPLATE_RE.sub("", s).strip(" |·-—，,。、:：")
    s = _WS_RE.sub(" ", s).strip()
    if max_len and len(s) > max_len:
        s = s[:max_len].rstrip("，,、；;：: ") + "…"
    return s


def pick_text(*values, max_len=None) -> str:
    """从多个候选里取第一个非空清洗结果。"""
    for v in values:
        cleaned = strip_html(v, max_len=max_len)
        if cleaned:
            return cleaned
    return ""


# ============================================================
# 二、链接清洗
# ============================================================

# 追踪参数（会污染统计、暴露来源，也让同一文章出现多个不同 URL）
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_name", "utm_cid", "utm_reader", "utm_social", "utm_brand",
    "spm", "scm", "from", "from_source", "share_source", "share_medium",
    "fbclid", "gclid", "yclid", "msclkid", "igshid", "ref", "referrer",
    "source", "src", "campaign", "ckey", "scene", "subscene",
}

# 这些域名可以安全升级到 https
_HTTPS_SAFE = {
    "geekpark.net", "www.geekpark.net", "zhidx.com", "www.zhidx.com",
    "ifanr.com", "www.ifanr.com", "sspai.com", "beta.sspai.com",
    "tmtpost.com", "www.tmtpost.com", "infoq.cn", "www.infoq.cn",
    "juejin.cn", "www.cnblogs.com", "sootoo.com", "www.sootoo.com",
}

# 付费墙特征
_PAYWALL_HOSTS = {"sspai.com", "beta.sspai.com"}
_PAYWALL_PATHS = ("/prime/", "/paid/", "/vip/", "/member/", "/premium/")


def clean_link(url) -> str:
    """去追踪参数、去 fragment、统一 https（仅对确认支持的域名）。"""
    if not url or not isinstance(url, str):
        return ""
    url = url.strip()
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    scheme = parts.scheme or "https"
    host = parts.netloc.lower()
    path = parts.path or "/"

    query = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS and not k.lower().startswith("utm_")
    ]
    # 只剩无意义参数时清空整个 query
    query = [(k, v) for k, v in query if k and (v or k.lower() in {"id", "p", "page"})]

    bare_host = host[4:] if host.startswith("www.") else host
    if scheme == "http" and (host in _HTTPS_SAFE or bare_host in _HTTPS_SAFE):
        scheme = "https"

    return urlunsplit((scheme, host, path, urlencode(query, doseq=True), ""))


def is_paywalled(url) -> bool:
    """识别付费墙文章（少数派 prime、会员专享等）。"""
    if not url:
        return False
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    host = parts.netloc.lower()
    path = parts.path.lower()
    bare = host[4:] if host.startswith("www.") else host
    if bare in _PAYWALL_HOSTS and any(p in path for p in _PAYWALL_PATHS):
        return True
    return any(p in path for p in _PAYWALL_PATHS) and ("premium" in path or "paid" in path)


# ============================================================
# 三、AI 相关性判定
# ============================================================

# 中文词直接子串匹配
AI_TERMS_ZH = [
    "人工智能", "大模型", "大语言模型", "语言模型", "机器学习", "深度学习",
    "神经网络", "智能体", "多模态", "生成式", "提示词", "微调", "预训练",
    "推理模型", "算力", "开源模型", "模型开源", "世界模型", "具身智能",
    "文生图", "文生视频", "图生视频", "语音合成", "语音识别", "计算机视觉",
    "知识图谱", "强化学习", "向量检索", "模型训练", "模型推理", "大模型应用",
    "通义", "文心", "豆包", "智谱", "月之暗面", "百川", "零一万物", "阶跃星辰",
    "英伟达", "算力芯片", "AI 芯片", "AI芯片",
]

# 英文/品牌词必须按词边界匹配，否则 "ai" 会命中 email / air / detail
AI_TERMS_EN = [
    "ai", "agi", "llm", "llms", "gpt", "chatgpt", "openai", "anthropic",
    "claude", "gemini", "bard", "llama", "mistral", "deepseek", "qwen",
    "moonshot", "kimi", "grok", "sora", "midjourney", "dall-e", "dalle",
    "stable diffusion", "comfyui", "huggingface", "hugging face",
    "transformer", "transformers", "rag", "mcp", "cursor", "copilot",
    "perplexity", "nvidia", "cuda", "pytorch", "tensorflow", "langchain",
    "llamaindex", "agent", "agents", "agentic", "multimodal", "aigc",
    "fine-tuning", "finetune", "inference", "embedding", "embeddings",
    "diffusion model", "foundation model", "text-to-image", "text-to-video",
]

_EN_BOUNDARY = {
    term: re.compile(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", re.I)
    for term in AI_TERMS_EN
}


def has_ai_signal(text) -> bool:
    """文本里是否出现明确的 AI 信号（区分大小写无关，但按词边界）。"""
    if not text:
        return False
    t = text.lower()
    if any(term.lower() in t for term in AI_TERMS_ZH):
        return True
    return any(pat.search(t) for pat in _EN_BOUNDARY.values())


# 明确的非 AI 内容（通用媒体的商业/生活/消费新闻）
NON_AI_ZH = [
    "医美", "玻尿酸", "肉毒素", "耗材集采", "集采", "药价",
    "图库", "版权图库", "getty images",
    "菜谱", "食谱", "蒸菜", "家常菜", "做法大全", "好吃",
    "双11", "双十一", "618", "购物节", "促销", "优惠券",
    "节假日", "放假安排", "调休", "春运", "天气预报",
    "奥运", "世界杯", "夺冠", "球赛",
    "进博会", "展销会", "车展", "新车上市", "销量榜",
    "楼盘", "房价", "土地拍卖", "房贷",
    "彩票", "星座", "运势", "减肥", "美白", "护肤",
    "明星", "恋情", "离婚", "综艺", "电视剧", "电影票房",
]
_NON_AI_RE = re.compile("|".join(re.escape(x) for x in NON_AI_ZH), re.I)


def is_obvious_non_ai(text) -> bool:
    """命中明确非 AI 主题词（菜谱 / 医美 / 双 11 / 车展 …）。"""
    if not text:
        return False
    return bool(_NON_AI_RE.search(text))


def ai_relevance(item: dict, require_title: bool = False) -> tuple[bool, str]:
    """判断一条记录是否真的与 AI 相关。

    返回 (是否通过, 原因)。
      - require_title=True 时，标题必须含 AI 信号（用于通用科技媒体，
        避免"正文顺带提了一句 AI"的消费/商业新闻混进来）
    """
    title = pick_text(item.get("title_zh"), item.get("title"))
    desc = pick_text(item.get("summary_zh"), item.get("description"))
    combined = f"{title} {desc}"

    if is_obvious_non_ai(title) or is_obvious_non_ai(desc[:160]):
        return False, "命中非 AI 主题词"

    if require_title:
        if not has_ai_signal(title):
            return False, "标题无 AI 信号"
        return True, "标题含 AI 信号"

    if not has_ai_signal(combined):
        return False, "全文无 AI 信号"
    return True, "含 AI 信号"


# ============================================================
# 四、去重
# ============================================================

_PUNCT_RE = re.compile(r"[\s\-_—–·•|/\\:：,，.。!！?？'\"“”‘’()（）\[\]【】<>《》+*#~`]+")


def normalize_title(title) -> str:
    """标题归一化：去 HTML、去标点、去空格、统一小写。"""
    t = strip_html(title)
    t = _PUNCT_RE.sub("", t)
    return t.lower()


def title_tokens(title) -> set:
    """标题特征词：中文 bigram + 英文/数字词（长度 ≥ 2）。"""
    t = normalize_title(title)
    zh = re.findall(r"[\u4e00-\u9fff]", t)
    bigrams = {"".join(zh[i:i + 2]) for i in range(len(zh) - 1)}
    latin = {w for w in re.findall(r"[a-z0-9][a-z0-9.\-]{1,}", t) if len(w) >= 2}
    return bigrams | latin


def title_similarity(a, b) -> float:
    """标题相似度：字符序列相似度、特征词 Jaccard、最长公共子串，取最大值。

    只看整句相似度会漏掉"同一事件、不同措辞"：
      「百度开源文心5.5 Flash Base，280B总参数14B激活」
      「百度开源文心5.5 Flash Base，同尺寸模型刷新SOTA」  整句只有 0.60，
    但共享 15 字以上的公共主干，实际就是同一件事，需要判为重复。
    """
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    seq = SequenceMatcher(None, na, nb).ratio()
    ta, tb = title_tokens(a), title_tokens(b)
    jac = len(ta & tb) / len(ta | tb) if (ta and tb) else 0.0
    # 短标题被长标题完整包含，视为高度重复
    contained = 0.9 if (len(na) >= 6 and na in nb) or (len(nb) >= 6 and nb in na) else 0.0
    # 长公共主干（≥10 字且覆盖较短标题 45% 以上）
    match = SequenceMatcher(None, na, nb).find_longest_match(0, len(na), 0, len(nb))
    common = 0.82 if (match.size >= 10 and match.size / min(len(na), len(nb)) >= 0.45) else 0.0
    return max(seq, jac, contained, common)


def is_duplicate_of_any(title, existing_titles, threshold: float = 0.76) -> bool:
    for prev in existing_titles:
        if title_similarity(title, prev) >= threshold:
            return True
    return False


def _numbers(text) -> set:
    return set(re.findall(r"\d+(?:\.\d+)?", normalize_title(text)))


def _version_conflict(a: set, b: set) -> bool:
    """两串数字是否构成「不同型号/版本」的冲突。

    只在小数字上判断：GPT-5 / GPT-6 的 {5} vs {6} 算冲突；
    而「280B 总参 14B 激活」vs「2800 亿参数」属于同一件事的不同写法，
    不能因为数字不同就当成两条独立新闻。
    """
    if not a or not b or a == b:
        return False
    diff = a ^ b
    try:
        return all(float(x) < 100 for x in diff)
    except ValueError:
        return False


def dedupe_items(items, title_key="title_zh", fallback_key="title",
                 link_key="link", weight_key="source_weight",
                 threshold: float = 0.76, guard_numbers: bool = False) -> list:
    """两级去重：链接完全一致 + 标题高度相似。

    重复时保留可信度权重更高的那条；权重相同时保留描述更长（信息更全）的。
    链接优先用「去参数后的规范链接」比较，避免同一文章多份 utm 变体。

    guard_numbers=True 时，两条标题里的数字集合不同就不判重复——
    否则「OpenAI 发布 GPT-5」「OpenAI 发布 GPT-6」会被字符相似度（0.92）误杀。
    """
    kept = []
    seen_links = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        link = clean_link(it.get(link_key) or "")
        title = pick_text(it.get(title_key), it.get(fallback_key))

        dup_index = None
        if link and link in seen_links:
            dup_index = seen_links[link]
        elif title:
            nums = _numbers(title) if guard_numbers else None
            for idx, prev in enumerate(kept):
                prev_title = pick_text(prev.get(title_key), prev.get(fallback_key))
                if title_similarity(title, prev_title) < threshold:
                    continue
                if guard_numbers:
                    prev_nums = _numbers(prev_title)
                    # 型号/版本号不同（GPT-5 vs GPT-6）→ 是两条不同新闻，不合并
                    if _version_conflict(nums, prev_nums):
                        continue
                dup_index = idx
                break

        if dup_index is None:
            if link:
                seen_links[link] = len(kept)
            kept.append(it)
            continue

        # 撞车：比较质量，决定是否替换
        prev = kept[dup_index]
        new_w = float(it.get(weight_key) or 1.0)
        old_w = float(prev.get(weight_key) or 1.0)
        new_len = len(pick_text(it.get("description"), it.get("summary_zh")))
        old_len = len(pick_text(prev.get("description"), prev.get("summary_zh")))
        if (new_w, new_len) > (old_w, old_len):
            kept[dup_index] = it
            if link:
                seen_links[link] = dup_index

    return kept
