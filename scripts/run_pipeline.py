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


def build_css():
    """重新编译 Tailwind CSS。

    必须在所有页面渲染之后执行：Tailwind 按页面里实际出现的 class 生成样式，
    新渲染出来的页面若带来新 class，不重编译就会缺样式。
    找不到本地构建工具时只告警、不中断——旧 CSS 仍可用，其余产物不受影响。
    """
    print()
    print("=" * 70)
    print("▶ 步骤 10/10 · 编译 Tailwind CSS")
    print("=" * 70)

    root = SCRIPT_DIR.parent
    bin_name = "tailwindcss.cmd" if sys.platform == "win32" else "tailwindcss"
    local_bin = root / "node_modules" / ".bin" / bin_name

    if not local_bin.exists():
        print("⚠ 未找到 node_modules/.bin/tailwindcss，跳过 CSS 编译")
        print("  首次部署请先执行：npm install")
        print("  现有 assets/tailwind.css 继续可用，但新页面的新增 class 会缺样式")
        return

    cmd = [
        str(local_bin), "-c", "tailwind.config.js",
        "-i", "assets/tailwind.input.css",
        "-o", "assets/tailwind.css", "--minify",
    ]
    r = subprocess.run(cmd, cwd=str(root))
    if r.returncode != 0:
        print(f"⚠ CSS 编译失败（exit={r.returncode}），沿用旧 CSS")
        print("  若本次渲染引入了新 class，页面会缺对应样式")
    else:
        print("✅ CSS 已重新编译")


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
        run_step("步骤 1/10 · 抓取资讯", ["scripts/fetch_ai_news.py"])

    if not args.skip_score:
        run_step(f"步骤 2/10 · 资讯评分+摘要（{args.mode} 模式）",
                 ["scripts/score_and_summarize.py", "--mode", args.mode])

    if not args.skip_fetch:
        run_step("步骤 3/10 · 抓取 AI玩法", ["scripts/fetch_ai_play.py"])

    if not args.skip_score:
        run_step(f"步骤 4/10 · 玩法 LLM 翻译+评分（{args.mode} 模式）",
                 ["scripts/score_play.py"])

    run_step("步骤 5/10 · 渲染日报", ["scripts/render_brief.py"])
    run_step("步骤 6/10 · 渲染首页", ["scripts/render_index.py"])
    run_step("步骤 7/10 · 渲染玩法实验室", ["scripts/render_playground.py"])

    # v5 新增：教程社区（LLM 生成 + 渲染详情页）
    if not args.skip_tutorials:
        run_step("步骤 8/10 · LLM 生成教程（每日最多 20 篇）",
                 ["scripts/generate_tutorials.py"])
        run_step("步骤 9/10 · 渲染教程详情页 + 索引页",
                 ["scripts/render_tutorials.py"])
    else:
        print()
        print("=" * 70)
        print("⏭ 跳过教程生成（--skip-tutorials）")
        print("=" * 70)

    # 必须在全部渲染之后：按最终页面的 class 生成样式
    build_css()

    print("\n" + "=" * 70)
    print("✅ 流水线完成！首页 + 日报 + 玩法实验室 + 教程 四件套均已更新")
    if not args.skip_tutorials:
        print("   📚 教程页：tutorials/index.html + 详情页")
    print("=" * 70)


if __name__ == "__main__":
    main()