"""
run_pipeline.py
===============
一键运行完整流水线：抓取 → 评分 → 渲染（v5 新增教程生成+渲染）

使用：
  python run_pipeline.py                   # 完整跑（规则评分）
  python run_pipeline.py --mode llm        # 完整跑（LLM 评分，需 API key）
  python run_pipeline.py --skip-fetch      # 跳过抓取（用已有数据）
  python run_pipeline.py --skip-score      # 跳过评分
  python run_pipeline.py --skip-tutorials  # 跳过教程生成（节省 token）
"""

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _utf8  # noqa: F401  —— 强制 UTF-8 输出，防止 GBK 控制台崩溃

SCRIPT_DIR = Path(__file__).parent


def run_step(label: str, args: list):
    print()
    print("=" * 70)
    print(f"▶ {label}")
    print("=" * 70)
    cmd = [sys.executable] + args
    r = subprocess.run(cmd, cwd=str(SCRIPT_DIR.parent))
    if r.returncode != 0:
        print(f"❌ {label} 失败（exit={r.returncode}）")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="rule", choices=["rule", "llm"],
                        help="rule=规则评分, llm=LLM 评分")
    parser.add_argument("--skip-fetch", action="store_true", help="跳过抓取（用已有数据）")
    parser.add_argument("--skip-score", action="store_true", help="跳过评分")
    parser.add_argument("--skip-tutorials", action="store_true", help="跳过教程生成（节省 token）")
    args = parser.parse_args()

    print("\n🚀 AI Frontier · 完整流水线")
    print(f"   mode = {args.mode}")
    print(f"   skip_fetch = {args.skip_fetch}")
    print(f"   skip_score = {args.skip_score}")

    if not args.skip_fetch:
        run_step("步骤 1/9 · 抓取资讯", ["scripts/fetch_ai_news.py"])

    if not args.skip_score:
        run_step(f"步骤 2/9 · 资讯评分+摘要（{args.mode} 模式）",
                 ["scripts/score_and_summarize.py", "--mode", args.mode])

    if not args.skip_fetch:
        run_step("步骤 3/9 · 抓取 AI玩法", ["scripts/fetch_ai_play.py"])

    if not args.skip_score:
        run_step(f"步骤 4/9 · 玩法 LLM 翻译+评分（{args.mode} 模式）",
                 ["scripts/score_play.py"])

    run_step("步骤 5/9 · 渲染日报", ["scripts/render_brief.py"])
    run_step("步骤 6/9 · 渲染首页", ["scripts/render_index.py"])
    run_step("步骤 7/9 · 渲染玩法实验室", ["scripts/render_playground.py"])

    # v5 新增：教程社区（LLM 生成 + 渲染详情页）
    if not args.skip_tutorials:
        run_step("步骤 8/9 · LLM 生成教程（每日最多 20 篇）",
                 ["scripts/generate_tutorials.py"])
        run_step("步骤 9/9 · 渲染教程详情页 + 索引页",
                 ["scripts/render_tutorials.py"])
    else:
        print()
        print("=" * 70)
        print("⏭ 跳过教程生成（--skip-tutorials）")
        print("=" * 70)

    print("\n" + "=" * 70)
    print("✅ 流水线完成！首页 + 日报 + 玩法实验室 + 教程 四件套均已更新")
    if not args.skip_tutorials:
        print("   📚 教程页：tutorials/index.html + 详情页")
    print("=" * 70)


if __name__ == "__main__":
    main()