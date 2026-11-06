"""
sources_config.py
=================
信息源清单 + 来源可信度分级体系（所有脚本共用）

来源可信度 4 级：
  official  = 官方一手（公司官方博客/发布会/论文） → S 级，最可靠
  media     = 权威媒体（有编辑审核的科技媒体）      → A 级
  community = 技术社区（GitHub 高 star / 社区讨论）  → B 级
  selfmedia = 自媒体/个人（个人博客/公众号/微博）    → C 级，需甄别

v4 更新（2026-09-12）：
- 国内网络环境：补充 10 个国内可稳定访问的信息源
- 移除/标注 5 个 WAF 拦截或失效的海外源（保留 URL 注释）
- GitHub 高星项目保留作为补充源（部分话题国内访问不稳）
"""

# ============================================================
# 可信度分级定义
# ============================================================

RELIABILITY_LEVELS = {
    "official": {
        "level": "S", "label": "官方一手", "emoji": "🟢",
        "color": "green", "weight": 1.3,
        "desc": "公司官方 / 论文，最可靠",
    },
    "media": {
        "level": "A", "label": "权威媒体", "emoji": "🔵",
        "color": "blue", "weight": 1.1,
        "desc": "有编辑审核的科技媒体",
    },
    "community": {
        "level": "B", "label": "技术社区", "emoji": "🟡",
        "color": "yellow", "weight": 1.0,
        "desc": "GitHub / 社区，技术可信",
    },
    "selfmedia": {
        "level": "C", "label": "自媒体", "emoji": "⚪",
        "color": "gray", "weight": 0.8,
        "desc": "个人观点，需甄别",
    },
}


def reliability_of(source_type: str) -> dict:
    """根据 source_type 返回可信度信息"""
    return RELIABILITY_LEVELS.get(source_type, RELIABILITY_LEVELS["selfmedia"])


# ============================================================
# 信息源清单（v4 扩展国内源）
# ============================================================

RSS_SOURCES = [
    # ===== 🟢 官方一手（S 级） =====
    {"id": "openai",        "name": "OpenAI 官方",       "url": "https://openai.com/news/rss.xml",                "category": "大模型", "lang": "en", "source_type": "official"},
    {"id": "anthropic",     "name": "Anthropic 官方",    "url": "https://www.anthropic.com/news/feed.xml",        "category": "大模型", "lang": "en", "source_type": "official"},
    {"id": "google-deepmind","name": "Google DeepMind",  "url": "https://deepmind.google/blog/rss.xml",           "category": "大模型", "lang": "en", "source_type": "official"},
    {"id": "meta-ai",       "name": "Meta AI",           "url": "https://ai.meta.com/blog/rss/",                  "category": "大模型", "lang": "en", "source_type": "official"},
    {"id": "huggingface",   "name": "Hugging Face 官方", "url": "https://huggingface.co/blog/feed.xml",           "category": "开源",   "lang": "en", "source_type": "official"},
    {"id": "arxiv-ai",      "name": "arXiv cs.AI",       "url": "http://export.arxiv.org/rss/cs.AI",              "category": "论文",   "lang": "en", "source_type": "official"},
    {"id": "arxiv-cl",      "name": "arXiv cs.CL",       "url": "http://export.arxiv.org/rss/cs.CL",              "category": "论文",   "lang": "en", "source_type": "official"},
    {"id": "google-blog",   "name": "Google Research",   "url": "https://research.google/blog/rss/",              "category": "论文",   "lang": "en", "source_type": "official"},

    # ===== 🔵 权威媒体（A 级）· 国内网络环境友好 =====
    {"id": "qbitai",        "name": "量子位",            "url": "https://www.qbitai.com/feed",                     "category": "综合",   "lang": "zh", "source_type": "media"},
    {"id": "leiphone",      "name": "AI 科技评论",       "url": "https://www.leiphone.com/feed",                  "category": "综合",   "lang": "zh", "source_type": "media"},
    {"id": "geekpark",      "name": "极客公园",          "url": "https://geekpark.net/rss",                       "category": "产业",   "lang": "zh", "source_type": "media"},
    {"id": "tmtpost",       "name": "钛媒体",            "url": "https://www.tmtpost.com/rss",                    "category": "产业",   "lang": "zh", "source_type": "media"},
    {"id": "zhidx",         "name": "智东西",            "url": "https://zhidx.com/rss/",                         "category": "产业",   "lang": "zh", "source_type": "media"},
    {"id": "ifanr",         "name": "爱范儿",            "url": "https://www.ifanr.com/feed",                     "category": "综合",   "lang": "zh", "source_type": "media"},
    {"id": "infoq-cn",      "name": "InfoQ 中国",        "url": "https://www.infoq.cn/feed.xml",                  "category": "技术",   "lang": "zh", "source_type": "media"},
    {"id": "sspai",         "name": "少数派",            "url": "https://sspai.com/feed",                         "category": "工具",   "lang": "zh", "source_type": "media"},
    {"id": "unite-ai",      "name": "Unite.AI",          "url": "https://www.unite.ai/feed/",                     "category": "综合",   "lang": "en", "source_type": "media"},
    {"id": "mit-techreview","name": "MIT Tech Review",   "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed", "category": "观点", "lang": "en", "source_type": "media"},
    {"id": "venturebeat-ai","name": "VentureBeat",       "url": "https://venturebeat.com/category/ai/feed/",      "category": "产业",   "lang": "en", "source_type": "media"},
    # 以下源已知失效/被 WAF 拦截（保留注释，待恢复后重新启用）
    # {"id": "jiqizhixin",  "name": "机器之心",          "url": "https://www.jiqizhixin.com/rss",                 "category": "综合",   "lang": "zh", "source_type": "media"},  # WAF 拦截，返回 HTML
    # {"id": "36kr-ai",     "name": "36氪",              "url": "https://36kr.com/feed",                          "category": "产业",   "lang": "zh", "source_type": "media"},  # 已 404
    # {"id": "huxiu",       "name": "虎嗅",              "url": "https://www.huxiu.com/rss/",                     "category": "产业",   "lang": "zh", "source_type": "media"},  # aliyun_waf
    # {"id": "the-gradient","name": "The Gradient",      "url": "https://thegradient.pub/rss/",                   "category": "观点",   "lang": "en", "source_type": "media"},  # 长期超时

    # ===== 🟡 技术社区（B 级）· 国内网络环境友好 =====
    {"id": "juejin",        "name": "掘金技术社区",      "url": "https://juejin.cn/rss",                          "category": "社区",   "lang": "zh", "source_type": "community"},
    {"id": "segmentfault",  "name": "SegmentFault",      "url": "https://segmentfault.com/feeds",                 "category": "社区",   "lang": "zh", "source_type": "community"},
    {"id": "cnblogs",       "name": "博客园",            "url": "https://www.cnblogs.com/rss",                    "category": "社区",   "lang": "zh", "source_type": "community"},
    {"id": "hackernews",    "name": "Hacker News",       "url": "https://hnrss.org/newest?q=AI+OR+LLM+OR+GPT",    "category": "社区",   "lang": "en", "source_type": "community"},
    # GitHub 高 star 项目（用 API 抓取，见 fetch_github_trending）—— 国内访问不稳，作为补充源

    # ===== ⚪ 自媒体/产业（C 级）· 补充视角 =====
    {"id": "sootoo",        "name": "速途网",            "url": "https://www.sootoo.com/feed",                    "category": "产业",   "lang": "zh", "source_type": "selfmedia"},
    {"id": "marktechpost",  "name": "MarkTechPost",      "url": "https://www.marktechpost.com/feed",              "category": "工具",   "lang": "en", "source_type": "selfmedia"},
    # {"id": "baoyu",       "name": "宝玉的分享",        "url": "https://baoyu.io/feed.xml",                      "category": "观点",   "lang": "zh", "source_type": "selfmedia"},  # 404
]

# ============================================================
# GitHub 高 star 项目抓取配置（国内访问不稳，作为补充）
# ============================================================

GITHUB_CONFIG = {
    "api_url": "https://api.github.com/search/repositories",
    "queries": [
        {"topic": "llm",       "label": "LLM",     "min_stars": 500},
        {"topic": "ai-agent",  "label": "AI Agent", "min_stars": 300},
        {"topic": "generative-ai", "label": "生成式AI", "min_stars": 300},
        {"topic": "machine-learning", "label": "机器学习", "min_stars": 500},
    ],
    "days_back": 5,
    "max_per_topic": 3,
    # v4 新增：失败时降级而非阻塞整体
    "skip_on_failure": True,
}