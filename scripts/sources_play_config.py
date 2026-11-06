"""
sources_play_config.py
=======================
AI玩法实验室 - 信息源配置（与 sources_config.py 风格一致）

v4 更新（2026-09-12）：
- 新增国内玩法源（少数派/智东西/爱范儿/掘金/博客园），不依赖 GitHub
- 保留 GitHub awesome-* 作为补充源（国内访问不稳时降权）

来源类型：
  - awesome_repo   : GitHub 上 awesome-* 主题精选仓库（B级，国内访问不稳）
  - hf_space       : HuggingFace Spaces（A级，官方审核）
  - product_hunt   : Product Hunt AI 分类（B级，社区投票）
  - github_project : GitHub 高 star AI 项目（B级，可运行）
  - reddit_post    : Reddit r/ChatGPT / r/LocalLLaMA 精华帖（C级，自媒体）
  - domestic_rss   : 国内权威媒体玩法专栏（A/B级，国内稳）

玩法类型 play_type：
  - prompt         : Prompt 模板（对话型）
  - tool_chain     : 工具工作流（多个工具组合）
  - runnable_demo  : 可一键运行（HF Spaces / GitHub Demo）
  - tutorial       : 教程指引（步骤化）
"""

# ============================================================
# 1. 玩法专属 GitHub awesome 系列（国内访问不稳，作为补充）
# ============================================================
AWESOME_REPOS = [
    # 主题关键词搜索 GitHub awesome-* 仓库
    {"query": "awesome-chatgpt-prompts",
     "name": "Awesome ChatGPT Prompts",
     "play_type": "prompt",
     "min_stars": 5000,
     "source_type": "community"},
    {"query": "awesome-ai-agents",
     "name": "Awesome AI Agents",
     "play_type": "tool_chain",
     "min_stars": 1000,
     "source_type": "community"},
    {"query": "awesome-llm",
     "name": "Awesome LLM",
     "play_type": "runnable_demo",
     "min_stars": 5000,
     "source_type": "community"},
    {"query": "awesome-rag",
     "name": "Awesome RAG",
     "play_type": "tool_chain",
     "min_stars": 500,
     "source_type": "community"},
    {"query": "awesome-stable-diffusion",
     "name": "Awesome Stable Diffusion",
     "play_type": "tool_workflow",
     "min_stars": 1000,
     "source_type": "community"},
    {"query": "awesome-comfyui",
     "name": "Awesome ComfyUI",
     "play_type": "tool_workflow",
     "min_stars": 500,
     "source_type": "community"},
    {"query": "langchain",
     "name": "LangChain",
     "play_type": "tool_chain",
     "min_stars": 8000,
     "source_type": "official"},   # LangChain 团队自己维护
    {"query": "autogen",
     "name": "AutoGen",
     "play_type": "tool_chain",
     "min_stars": 5000,
     "source_type": "official"},
]

# ============================================================
# 2. HuggingFace Spaces（用 trending API）
# ============================================================
HF_CONFIG = {
    "api_url": "https://huggingface.co/api/spaces",
    "params": "?sort=likes&direction=-1&limit=30",
    "filter_keywords": [
        "llm", "agent", "rag", "stable-diffusion", "comfy",
        "chat", "image", "video", "audio", "tts", "tutorial",
    ],
    "max_results": 25,
}

# ============================================================
# 3. Product Hunt（通过 RSS）
# ============================================================
PRODUCT_HUNT_RSS = [
    {"id": "ph-ai",
     "name": "Product Hunt - AI 频道",
     "url": "https://www.producthunt.com/feed?category=ai",
     "source_type": "community"},
]

# ============================================================
# 4. Reddit（精华贴，按月榜）
# ============================================================
REDDIT_RSS = [
    {"id": "reddit-chatgpt",
     "name": "Reddit r/ChatGPT 精华",
     "url": "https://www.reddit.com/r/ChatGPT/top/?sort=top&t=month.rss",
     "lang": "en",
     "source_type": "community"},
    {"id": "reddit-local-llama",
     "name": "Reddit r/LocalLLaMA 精华",
     "url": "https://www.reddit.com/r/LocalLLaMA/top/?sort=top&t=month.rss",
     "lang": "en",
     "source_type": "community"},
]

# ============================================================
# 5. 国内玩法源（v4 新增，国内网络环境稳）
# ============================================================
# 与新闻源分开：玩法源更聚焦"工具/教程/可复制"
# 关键词统一收紧：用具体 AI 工具/玩法名词，避免通用媒体混入非 AI 内容
DOMESTIC_PLAY_SOURCES = [
    {"id": "sspai-play",
     "name": "少数派 AI 工具",
     "url": "https://sspai.com/feed",
     "play_type": "tool_chain",
     "source_type": "media",   # A 级
     "lang": "zh",
     # AI 关键词：宽 + 具体工具（标题必须有 AI 字眼；标题不含 AI 但描述含也行）
     "filter_keywords": ["ai", "gpt", "claude", "gemini", "llm", "stable diffusion", "comfyui", "cursor",
                         "copilot", "rag", "prompt", "提示词", "deepseek", "sora", "midjourney", "dall-e",
                         "llama", "qwen", "通义", "豆包", "kimi", "文心", "智谱", "月之暗面",
                         "大模型", "智能体", "agent", "微调", "训练", "推理"],
     # 排除栏目（派早报、App+1 等非玩法内容；iPhone 等科技资讯）
     "exclude_keywords": ["派早报", "App+1", "本周看什么", "一图流", "新玩意", "新 iPhone", "iPhone ", "Apple",
                            "AirPods", "iPad", "MacBook", "电影", "新能源", "汽车"],
     "max_results": 6},
    {"id": "zhidx-play",
     "name": "智东西 AI 工具评测",
     "url": "https://zhidx.com/rss/",
     "play_type": "tool_workflow",
     "source_type": "media",   # A 级
     "lang": "zh",
     "filter_keywords": ["ai", "gpt", "claude", "gemini", "llm", "stable diffusion", "comfyui", "cursor",
                         "rag", "prompt", "deepseek", "sora", "midjourney",
                         "大模型", "智能体", "agent", "训练", "微调", "推理", "工具评测"],
     "max_results": 8},
    {"id": "ifanr-play",
     "name": "爱范儿 AI 应用",
     "url": "https://www.ifanr.com/feed",
     "play_type": "tool_chain",
     "source_type": "media",   # A 级
     "lang": "zh",
     "filter_keywords": ["ai", "gpt", "claude", "gemini", "llm", "stable diffusion", "comfyui", "cursor",
                         "copilot", "rag", "prompt", "deepseek", "sora", "midjourney",
                         "大模型", "智能体", "ai 应用", "ai 工具"],
     "exclude_keywords": ["苹果", "iPhone", "iPad", "Mac", "Apple", "AirPods"],
     "max_results": 6},
    {"id": "juejin-play",
     "name": "掘金 AI 实战教程",
     "url": "https://juejin.cn/rss",
     "play_type": "tutorial",
     "source_type": "community",  # B 级
     "lang": "zh",
     "filter_keywords": ["ai", "gpt", "claude", "gemini", "llm", "stable diffusion", "comfyui", "cursor",
                         "copilot", "rag", "prompt", "提示词", "deepseek", "sora", "midjourney",
                         "langchain", "llamaindex", "大模型", "智能体", "agent", "微调", "fine-tune"],
     "max_results": 8},
    {"id": "cnblogs-play",
     "name": "博客园 AI 教程",
     "url": "https://www.cnblogs.com/rss",
     "play_type": "tutorial",
     "source_type": "community",  # B 级
     "lang": "zh",
     "filter_keywords": ["ai", "gpt", "claude", "gemini", "llm", "stable diffusion", "comfyui", "cursor",
                         "copilot", "rag", "prompt", "提示词", "deepseek", "sora", "midjourney",
                         "大模型", "智能体", "agent"],
     "max_results": 8},
]

# ============================================================
# 玩法元数据推断规则（根据关键字标识）
# ============================================================

# 难度推断（1-5 星，5 极简上手）
DIFFICULTY_RULES = {
    "5 ⭐ (1分钟复制 prompt)": ["prompt", "chatgpt", "claude", "gemini"],
    "4 ⭐ (零代码可跑)":       ["huggingface", "spaces", "colab", "demo"],
    "3 ⭐ (跑通本地 30 分钟)": ["docker", "docker-compose", "npm", "pip install"],
    "2 ⭐ (需配置开发环境)":   ["linux", "compile", "build", "vscode", "configure"],
    "1 ⭐ (需要工程基础)":      ["kubernetes", "k8s", "fine-tuning", "transformers"],
}

# 工具推断（按关键字）
TOOL_KEYWORDS = {
    "ChatGPT":     ["chatgpt", "gpt-4", "gpt-3.5", "openai"],
    "Claude":      ["claude", "anthropic"],
    "Gemini":      ["gemini", "bard"],
    "DeepSeek":    ["deepseek"],
    "Stable Diffusion": ["stable diffusion", "sdxl", "comfyui"],
    "LangChain":   ["langchain", "langgraph"],
    "LlamaIndex":  ["llamaindex", "llama-index", "rag"],
    "HF":          ["huggingface", "transformers", "spaces"],
    "DALL-E":      ["dall-e", "dalle"],
    "Midjourney":  ["midjourney"],
    "Sora":        ["sora"],
}

# 时间估算（按 play_type 默认）
TIME_ESTIMATE_DEFAULT = {
    "prompt":         "5min",
    "tool_chain":     "30min",
    "tool_workflow":  "30min",
    "runnable_demo":  "10min",
    "tutorial":       "1h",
}


def infer_play_type(item: dict) -> str:
    """根据标题/描述推断玩法类型"""
    text = (item.get("title", "") + " " + item.get("description", "")).lower()
    if any(k in text for k in ["workflow", "工作流", "pipeline", "节点"]):
        return "tool_workflow"
    if any(k in text for k in ["prompt", "提示词", "提示", "template"]):
        return "prompt"
    if any(k in text for k in ["space", "demo", "在线", "huggingface"]):
        return "runnable_demo"
    if any(k in text for k in ["教程", "tutorial", "guide", "how to", "how-to"]):
        return "tutorial"
    return "tool_chain"


def infer_tools(item: dict) -> list[str]:
    """从文本中识别用到的工具"""
    text = (item.get("title", "") + " " + item.get("description", "")).lower()
    found = []
    for tool, keywords in TOOL_KEYWORDS.items():
        if any(k in text for k in keywords):
            found.append(tool)
    return found or ["未标注"]


def infer_difficulty(item: dict) -> int:
    """难度评分 1-5（5 最易上手）"""
    text = (item.get("title", "") + " " + item.get("description", "")).lower()
    play_type = item.get("play_type", "tool_chain")
    if play_type == "prompt":
        return 5
    if play_type == "runnable_demo":
        return 4
    # 根据关键字判断
    for kw in ["kubernetes", "k8s", "fine-tuning", "fine tune", "微调", "训练"]:
        if kw in text:
            return 1
    for kw in ["build", "compile", "compile from source", "源代码编译"]:
        if kw in text:
            return 2
    for kw in ["docker", "docker-compose", "docker compose"]:
        return 3
    if play_type == "tool_chain":
        return 3
    return 3


def infer_copyable_score(item: dict) -> int:
    """可复制度 1-5（5 最容易照搬）"""
    text = (item.get("title", "") + " " + item.get("description", "")).lower()
    has_prompt = any(k in text for k in ["prompt", "template", "提示"])
    has_workflow = any(k in text for k in ["workflow", "json", "工作流"])
    has_steps = any(k in text for k in ["step 1", "第一步", "step1", "tutorial", "how to"])

    score = 3  # 默认
    if has_prompt: score = min(5, score + 1)
    if has_workflow: score = min(5, score + 1)
    if has_steps: score = min(5, score + 1)
    return score
