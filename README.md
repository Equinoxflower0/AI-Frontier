# AI Frontier · 全球 AI 前沿资讯聚合

> 每天 5 分钟，掌握全球 AI 核心动态 —— 自动采集、LLM 摘要、可信度分级、玩法教程一站到位。

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)]()
[![Tailwind](https://img.shields.io/badge/Tailwind_CSS-CDN-38BDF8?logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![LLM](https://img.shields.io/badge/LLM-DeepSeek-4D6BFE)](https://www.deepseek.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 为什么做这个

AI 大模型与开源项目迭代极快。想跟进的人常常没时间四处搜罗，只能接收到片面信息。

AI Frontier 把 **29 个信息源**的更新自动汇总、去重、评分、翻译成中文摘要，并按来源可信度分级，最终产出 4 套可直接浏览的静态页面。**零第三方依赖**，一台能开机的 Windows 电脑即可每天自动更新。

---

## 核心特性

- **多源聚合** — 25 个 RSS 源 + 4 类 GitHub 高星项目查询，24 小时时间窗，单源上限 15 条自动截断
- **来源可信度分级** — 每条资讯标注 S/A/B/C 四级并参与评分加权，一眼区分官方一手与自媒体观点
- **国内网络友好** — 25 个 RSS 源中含 12 个中文源（量子位、AI 科技评论、极客公园、钛媒体、智东西、爱范儿、InfoQ 中国、少数派、掘金、博客园、SegmentFault、速途网），海外源失败自动降级不阻塞
- **LLM 中文摘要** — DeepSeek 驱动，英文资讯自动翻译摘要，附带推荐理由
- **AI 玩法实验室** — 归集可复制的 AI 创新玩法，按玩法类型 / 难度 / 可复制度三维筛选
- **教程社区** — 每日 LLM 生成结构化教程（背景 → 工具准备 → 分步操作 → 效果 → FAQ → 进阶变体），支持站内搜索，增量缓存不重复烧 token
- **四套页面自动产出** — 首页 + 每日日报 + 玩法实验室 + 教程站，全部静态 HTML
- **全自动运行** — Windows 任务计划每天 08:00 自动跑完整流水线
- **零依赖** — 纯 Python 标准库（`urllib` / `xml.etree` / `json`），无需 `pip install`

---

## 页面一览

| 页面 | 文件 | 说明 |
|---|---|---|
| 首页 | `index.html` | 今日必看 TOP 3 + 7 大板块统计卡 + 完整资讯流 + 玩法入口 |
| 每日日报 | `daily-brief-YYYY-MM-DD.html` | 当日全量资讯，可按板块、可信度双维度筛选 |
| 玩法实验室 | `playground.html` | 57 条可复制玩法，按类型 / 难度 / 可信度筛选 |
| 教程站 | `tutorials/index.html` + `tutorials/<id>.html` | 20 篇结构化教程，含站内搜索与相关推荐 |

---

## 快速开始

### 环境要求

- **Python 3.10+**（实测 3.13.12）
- 无需安装任何第三方库
- 自动更新功能需要 Windows（任务计划程序）

### 1. 获取项目

```bash
git clone https://github.com/<your-name>/ai-frontier.git
cd ai-frontier
```

> 也可以直接下载 ZIP 解压。建议放在**纯英文、无空格**的路径下，避免 cmd 与编码问题。

### 2. 配置 API Key

```bash
cp .env.example .env
```

然后编辑 `.env`，填入真实值：

```ini
# DeepSeek API Key（推荐，玩法和教程生成必需）
DEEPSEEK_API_KEY=sk-你的真实key

# 模型选择
#   deepseek-chat      = DeepSeek-V3（快、便宜，推荐）
#   deepseek-reasoner  = DeepSeek-R1（推理强，慢、贵）
DEEPSEEK_MODEL=deepseek-chat
```

Key 从 [platform.deepseek.com](https://platform.deepseek.com/) 获取。

> ⚠️ `.env` 已被 `.gitignore` 排除，**切勿**手动强制提交或上传到 GitHub。

### 3. 运行完整流水线

```bash
python scripts/run_pipeline.py --mode llm
```

浏览器打开 `index.html` 即可查看。

---

## 工作原理

```
┌──────────────────────────────────────────────────────────────┐
│  29 个信息源                                                  │
│  25 RSS（S级8 / A级11 / B级4 / C级2） + 4 个 GitHub 查询      │
└───────────────────────────┬──────────────────────────────────┘
                            ↓ urllib + gzip 解压 + RSS/Atom 解析
                  24h 时间窗过滤 → 去重 → 单源截断(15条)
                            ↓
              scripts/data/raw_news.json          （148 条）
                            ↓ DeepSeek LLM 摘要 + 翻译 + 评分
              scripts/data/scored_news.json
                            ↓ Tailwind 模板渲染
        ┌───────────────────┴───────────────────┐
   daily-brief-*.html                     index.html
        （日报）                              （首页）
```

玩法与教程是并行的第二条链路：

```
GitHub awesome / HF Spaces / Product Hunt / Reddit / 国内 5 源
                            ↓
              scripts/data/raw_play.json         （57 条）
                            ↓ LLM 中文翻译 + 可玩性评分
              scripts/data/scored_play.json
                            ↓
        ┌───────────────────┴───────────────────┐
   playground.html                     generate_tutorials.py
        （玩法实验室）                          ↓ LLM 生成结构化教程
                                   tutorials_cache.json（20 篇，增量缓存）
                                                ↓
                                   tutorials/index.html + <id>.html
```

---

## 流水线 9 步

`run_pipeline.py` 按顺序调度以下步骤，任一步失败即中止：

| 步骤 | 脚本 | 作用 |
|---|---|---|
| 1 | `fetch_ai_news.py` | 抓取 25 个 RSS 源 + 4 类 GitHub 高星项目 |
| 2 | `score_and_summarize.py` | 资讯评分 + LLM 摘要翻译 |
| 3 | `fetch_ai_play.py` | 抓取玩法（GitHub / HF / PH / Reddit / 国内源） |
| 4 | `score_play.py` | 玩法中文翻译 + 可玩性评分 |
| 5 | `render_brief.py` | 渲染当日日报 HTML |
| 6 | `render_index.py` | 渲染首页 HTML |
| 7 | `render_playground.py` | 渲染玩法实验室 HTML |
| 8 | `generate_tutorials.py` | LLM 生成教程（每日最多 20 篇，带增量缓存） |
| 9 | `render_tutorials.py` | 渲染教程详情页 + 索引页 |

### 常用参数

```bash
python scripts/run_pipeline.py --mode llm          # LLM 评分（推荐）
python scripts/run_pipeline.py --mode rule         # 规则评分（无需 API）
python scripts/run_pipeline.py --skip-fetch        # 跳过抓取，用已有数据
python scripts/run_pipeline.py --skip-score        # 跳过评分
python scripts/run_pipeline.py --skip-tutorials    # 跳过教程生成（节省 token）
```

### 单步运行

每个脚本均可独立执行，便于调试：

```bash
python scripts/fetch_ai_news.py
python scripts/score_and_summarize.py --mode llm
python scripts/render_brief.py
```

---

## 来源可信度分级

`scripts/sources_config.py` 定义四级体系，分数会按权重参与排序：

| 级别 | 类型 | 含义 | 权重 |
|---|---|---|---|
| 🟢 **S** | `official` | 官方一手（公司官方博客 / 学术论文） | ×1.3 |
| 🔵 **A** | `media` | 权威媒体（有编辑审核的科技媒体） | ×1.1 |
| 🟡 **B** | `community` | 技术社区（GitHub 高星 / 社区讨论） | ×1.0 |
| ⚪ **C** | `selfmedia` | 自媒体 / 个人（需甄别） | ×0.8 |

页面上每条资讯都带对应徽章，首页与日报均支持按级别筛选。

---

## 数据结构

### 资讯条目 `scripts/data/scored_news.json`

```json
{
  "title": "原文标题",
  "title_zh": "中文标题",
  "link": "原文链接",
  "source_id": "openai",
  "source_name": "OpenAI 官方",
  "source_type": "official",
  "reliability_level": "S",
  "category": "大模型",
  "pubDate": "2026-09-12T10:30:00",
  "summary_zh": "中文摘要",
  "score": 8.5
}
```

### 玩法条目 `scripts/data/scored_play.json`

```json
{
  "title": "原始标题",
  "title_zh": "中文标题",
  "play_type": "tool_chain",
  "difficulty": 3,
  "copyable_score": 4,
  "time_estimate": "30min",
  "tools": ["LangChain", "ChatGPT"],
  "playability_score": 7.5,
  "source_tier": "B",
  "is_domestic": true
}
```

**玩法类型（5 种）**：`prompt`（Prompt 模板）· `tool_workflow`（工作流）· `tool_chain`（工具链）· `runnable_demo`（可立即试用）· `tutorial`（教程指引）

### 教程条目 `scripts/data/tutorials_cache.json`

| 字段 | 说明 |
|---|---|
| `intro` | 1-2 句话开场 |
| `background` | 3-5 句话背景故事 |
| `prerequisites[]` | 工具清单（name / desc / url） |
| `steps[]` | 步骤（title / content / tip），3-6 个 |
| `expected_result` | 预期效果描述 |
| `faq[]` | 常见问题（q / a） |
| `variants[]` | 进阶玩法变体 |
| `summary` | 一句话总结 |

缓存签名 = `title + link`，未变化则复用已有教程，不重复调用 LLM。

---

## 自动化（Windows 每日 08:00）

| 文件 | 用途 |
|---|---|
| `run_daily.bat` | 实际执行脚本，写日志到 `logs\pipeline.log` |
| `test_daily.bat` | **双击即可测试**，跑完显示 SUCCESS / FAILED |
| `setup_task.bat` | 注册/重建 Windows 定时任务（需**管理员身份运行**） |

任务名 `AI_Frontier_Daily_Brief`，每天 08:00 触发。

**使用流程：**

1. 右键 `setup_task.bat` → 以管理员身份运行
2. 双击 `test_daily.bat` 验证链路
3. 查看日志 `logs\pipeline.log`

> ⚠️ **电脑必须在 08:00 前开机**（锁屏可以，关机不行）。如需 24 小时在线，请改用 GitHub Actions。

详细配置见 [`docs/Windows任务计划配置教程.md`](docs/Windows任务计划配置教程.md)。

---

## 目录结构

```
ai-frontier/
├── index.html                          # 首页
├── daily-brief-2026-09-*.html          # 每日日报
├── playground.html                     # AI 玩法实验室
├── tutorials/                          # 教程站
│   ├── index.html                      #   教程索引（含站内搜索）
│   └── <source_id>-<hash>.html         #   教程详情页
├── AI网站路线图.html / .svg            # 项目规划图
├── README.md
├── LICENSE                             # MIT
├── .env.example                        # 环境变量模板（可提交）
├── .env                                # 真实 API Key（已被 .gitignore 排除）
├── .gitignore
├── run_daily.bat                       # 每日执行脚本
├── test_daily.bat                      # 双击测试
├── setup_task.bat                      # 注册定时任务（管理员）
├── docs/
│   └── Windows任务计划配置教程.md
├── logs/                               # 运行日志（已被 .gitignore 排除）
│   └── pipeline.log
└── scripts/
    ├── run_pipeline.py                 # 一键流水线（9 步）
    ├── _utf8.py                        # UTF-8 输出保险（防 GBK 崩溃）
    ├── floating_home.py                # 悬浮返回按钮组件
    ├── sources_config.py               # 资讯源 + 可信度分级
    ├── sources_play_config.py          # 玩法源 + 元数据推断规则
    ├── fetch_ai_news.py                # ① 抓资讯
    ├── score_and_summarize.py          # ② 资讯评分摘要
    ├── fetch_ai_play.py                # ③ 抓玩法
    ├── score_play.py                   # ④ 玩法翻译评分
    ├── render_brief.py                 # ⑤ 渲染日报
    ├── render_index.py                 # ⑥ 渲染首页
    ├── render_playground.py            # ⑦ 渲染玩法实验室
    ├── generate_tutorials.py           # ⑧ LLM 生成教程
    ├── render_tutorials.py             # ⑨ 渲染教程页
    ├── tutorials_schema.py             # 教程数据结构定义
    └── data/                           # 数据交换目录
        ├── raw_news.json
        ├── scored_news.json
        ├── raw_play.json
        ├── scored_play.json
        └── tutorials_cache.json
```

---

## 部署

### 方案 A：静态托管（最简单）

把 `index.html`、`daily-brief-*.html`、`playground.html`、`tutorials/` 上传到：

- GitHub Pages
- Vercel
- Netlify
- 腾讯云静态网站托管

### 方案 B：GitHub Actions 全自动（推荐）

```yaml
name: Daily AI Brief
on:
  schedule:
    - cron: '0 0 * * *'      # UTC 00:00 = 北京时间 08:00
  workflow_dispatch:

permissions:
  contents: write            # 提交产物并 git push 所需，缺失会导致推送被拒

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - name: Run pipeline
        env:
          DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
          DEEPSEEK_MODEL: deepseek-chat
        run: python scripts/run_pipeline.py --mode llm
      - name: Commit outputs
        run: |
          git config user.name "ai-frontier-bot"
          git config user.email "bot@users.noreply.github.com"
          git add index.html daily-brief-*.html playground.html tutorials/
          git commit -m "auto: update brief $(date +%F)" || exit 0
          git push
```

在仓库 Settings → Secrets 中添加 `DEEPSEEK_API_KEY` 即可。

---

## 常见问题

**Q：日报没有自动更新？**
检查三处：① 电脑 08:00 前是否开机；② `schtasks /Query /TN "AI_Frontier_Daily_Brief"` 任务是否存在；③ `logs\pipeline.log` 末尾是否有 `[ERROR]`。

**Q：没有配置 API Key 会怎样？**
流水线仍可运行，但降级为**规则模式**：英文资讯不做翻译、玩法与教程走 fallback 占位（仅展示原文链接）。建议至少配置 `DEEPSEEK_API_KEY`。

**Q：能用豆包 / OpenAI 吗？**
资讯评分（步骤 2）支持 `DOUBAO_API_KEY`、`OPENAI_API_KEY`、`DEEPSEEK_API_KEY` 三选一；但**玩法翻译与教程生成（步骤 3/4/8）目前仅支持 DeepSeek**。

**Q：为什么某些海外源抓不到？**
机器之心、36氪、虎嗅等被 WAF 拦截或已 404，配置中已注释保留 URL 待恢复。海外源失败不会阻塞整体抓取。

**Q：为什么 .bat 文件里全是英文？**
Windows cmd 默认按 GBK 读取批处理文件，含中文的 .bat 会被误解析甚至产生破坏性字符。故所有 .bat **强制纯 ASCII**，中文输出交给 Python 处理。

**Q：脚本在控制台报 `UnicodeEncodeError`？**
中文 Windows 下 stdout 重定向到文件时会退回 GBK 编码，遇 emoji 即崩溃。项目已内置 `scripts/_utf8.py` 强制 UTF-8。若手动运行报错，请设置环境变量 `PYTHONUTF8=1`。

---

## 已知限制

- **源成功率约 62%**（18/29），海外源受网络环境影响较大
- GitHub API 未认证时限速 60 次/小时，仅作补充源
- Reddit、Product Hunt 在国内访问不稳定
- 教程质量与生成数量依赖 DeepSeek API 配额
- 自动化依赖本机开机，无云端兜底

---

## 实测数据（2026-09-12 运行）

```
资讯：29 个源 → 成功 18 个 → 148 条（24h 窗口）
玩法：57 条，来自 12 个源
教程：20 篇（LLM 生成，全部非 fallback）

页面体积：
  index.html          272.6 KB
  playground.html     194.7 KB
  daily-brief-*.html  126 ~ 265 KB
  tutorials/          21 个文件
```

主要贡献源：钛媒体、AI 科技评论、InfoQ 中国、arXiv cs.AI/cs.CL、掘金、博客园、速途网、量子位、智东西、爱范儿、少数派、OpenAI 官方、MIT Tech Review。

---

## Roadmap

- [x] MVP 首页 + 日报页
- [x] 多源扩展至 25 个 RSS + GitHub 高星项目
- [x] 接入 LLM 自动摘要翻译
- [x] 来源可信度分级体系
- [x] AI 玩法实验室板块
- [x] 教程社区（结构化教程 + 站内搜索）
- [x] Windows 定时任务全自动更新
- [ ] 部署上线（Vercel / GitHub Pages）
- [ ] 邮件订阅（Buttondown / Substack）
- [ ] 更多玩法源（小红书 / 即刻 / 优设）
- [ ] GitHub Actions 云端定时，摆脱开机依赖

---

## 免责声明

本项目以**摘要 + 原文链接**方式聚合信息，不转载全文，版权归原作者所有。资讯可信度分级基于来源类型自动判定，仅供参考，请以原始来源为准。

---

## 许可证

本项目采用 [MIT License](LICENSE) 开源。

```
Copyright (c) 2026 Xiafancai
```

可自由使用、修改、分发本项目**代码与生成页面**，需保留版权声明。

> **注意**：MIT 许可仅覆盖本项目自身产出的代码与页面结构。聚合而来的资讯、文章标题、摘要与配图，版权仍归**原始作者 / 原始站点**所有（见上方免责声明）。若二次分发本项目生成的内容，请自行确认对原始内容的合规使用。
