"""
tutorials_schema.py
====================
AI 玩法实验室 · 教程数据模型与 LLM Prompt 定义

教程页结构（每篇 = 一篇站内独立 HTML 页面）：
  1. Hero：标题 + 难度★ + 时间⏱ + 工具 + 标签 + 来源徽章
  2. 目录（自动从步骤生成）
  3. 背景故事：这个玩法是什么 / 为什么值得关注
  4. 准备清单：你需要用到的工具 + 链接
  5. 步骤（核心）：3-6 步独立卡片，每步含「操作 / 小贴士」
  6. 效果预览：按步骤完成后应该看到什么
  7. 常见问题：3-5 条 FAQ（Q / A）
  8. 进阶玩法：2-3 个变体（让玩法有深度）
  9. 相关推荐：同类型玩法 3 条（增加站内阅读）

LLM 输出严格 JSON，字段：
{
  "intro": "string",           # 1-2 句话开场（教程开头）
  "background": "string",      # 3-5 句话背景故事
  "prerequisites": [           # 工具清单
    {"name": "...", "desc": "...", "url": "..."}
  ],
  "steps": [                   # 步骤（3-6 个）
    {
      "title": "第N步：xxx",
      "content": "具体操作描述（3-5 句话）",
      "tip": "小贴士（可选，1-2 句话）"
    }
  ],
  "expected_result": "string", # 预期效果描述
  "faq": [
    {"q": "...", "a": "..."}
  ],
  "variants": ["..."],         # 进阶玩法（2-3 个简短描述）
  "summary": "string"          # 一句话总结
}
"""

# ============================================================
# LLM Prompt 模板
# ============================================================

TUTORIAL_PROMPT_ZH = """你是一位 AI 玩法专家，请根据下面的玩法资料，**用中文**写一篇结构化的「AI 玩法教程」。

## 玩法原始资料
- 标题：{title}
- 来源：{source} ({source_url})
- 玩法类型：{play_type}（prompt=提示词模板 / tool_chain=工具链 / tool_workflow=工作流 / runnable_demo=一键试用 / tutorial=教程）
- 难度：{difficulty}/5（5=最简单）
- 工具：{tools}
- 原始描述：{description}

## 教程要求
1. **必须按以下 JSON 结构输出**（严格用双引号，不要用 Markdown 代码块包裹）
2. 内容要像零度博客那种实战教程：**直接可用、有具体操作、有小贴士**
3. 步骤数量：3-6 步（视复杂度自定）
4. FAQ：3-5 条常见疑问
5. 进阶玩法：2-3 个变体（让用户能举一反三）
6. 链接可以保留 {source_url} 作为参考
7. 工具准备清单尽量具体（带产品名/官网）

## 输出 JSON 模板（严格按字段输出，不要漏字段）
{{
  "intro": "（1-2 句话开场）",
  "background": "（3-5 句话背景故事，说明这个玩法的价值和适用场景）",
  "prerequisites": [
    {{"name": "工具名", "desc": "用途说明", "url": "官网或获取链接"}}
  ],
  "steps": [
    {{"title": "第1步：xxx", "content": "（3-5 句话具体操作）", "tip": "（可选，1-2 句话小贴士）"}}
  ],
  "expected_result": "（按步骤完成后应该看到什么效果）",
  "faq": [
    {{"q": "常见问题1", "a": "简要解答"}}
  ],
  "variants": ["变体1：xxx", "变体2：xxx"],
  "summary": "一句话总结这个玩法的精髓"
}}

只输出 JSON，不要有任何其他文字。
"""


# ============================================================
# 教程页字段定义（用于渲染时校验）
# ============================================================

TUTORIAL_FIELDS = {
    "intro": str,
    "background": str,
    "prerequisites": list,
    "steps": list,
    "expected_result": str,
    "faq": list,
    "variants": list,
    "summary": str,
}


# ============================================================
# 教程页模板（HTML 渲染时复用）
# ============================================================

TUTORIAL_HTML_STRUCTURE = {
    "hero": {
        "fields": ["title", "category", "difficulty", "time_estimate", "tools", "source_name", "source_tier"],
        "bg_gradient": "from-indigo-500 via-purple-500 to-pink-500",
    },
    "breadcrumb": [
        {"label": "首页", "href": "../index.html"},
        {"label": "玩法实验室", "href": "../playground.html"},
        {"label": "教程", "href": ""},  # 当前
    ],
    "sections": [
        {"id": "intro", "title": "📌 这是什么", "type": "intro"},
        {"id": "background", "title": "🎯 为什么值得玩", "type": "background"},
        {"id": "prerequisites", "title": "🧰 你需要准备", "type": "list"},
        {"id": "steps", "title": "📝 一步步教你做", "type": "steps"},
        {"id": "expected_result", "title": "✨ 完成后你会得到", "type": "text"},
        {"id": "faq", "title": "❓ 常见问题", "type": "faq"},
        {"id": "variants", "title": "🚀 进阶玩法", "type": "variants"},
        {"id": "summary", "title": "💡 一句话总结", "type": "highlight"},
        {"id": "related", "title": "📚 相关教程", "type": "related"},
    ],
}