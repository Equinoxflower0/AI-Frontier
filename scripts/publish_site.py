"""
publish_site.py
===============
把流水线生成 / 更新的页面提交并推送到 GitHub。

为什么单独抽出来：
  run_daily.bat 只能做顺序调度，无法给单条 git 命令设置超时。
  国内直连 GitHub 会间歇性被重置，如果 push 卡住，定时任务会挂几个小时。
  用 Python 可以：设置超时、失败重试、非交互模式、敏感文件拦截。

使用：
  python scripts/publish_site.py              # 提交 + 推送（默认，带重试）
  python scripts/publish_site.py --check      # 只看有没有改动，不提交不推送
  python scripts/publish_site.py --no-push    # 只本地提交，不推送
  python scripts/publish_site.py --force      # 即使无改动也建一个空提交

退出码：
  0 = 推送成功 / 本来就没有改动
  5 = 本地提交成功，但推送失败（网络问题，可稍后单独重跑本脚本）
  1 = 仓库状态异常 / 提交失败 / 检测到敏感文件
"""

import argparse
import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _utf8  # noqa: F401  —— 强制 UTF-8 输出，防止 GBK 控制台崩溃

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "publish.log"

BRANCH = "main"
RETRY_TIMES = 6
RETRY_WAIT = 20
PUSH_TIMEOUT = 180
CONNECT_TIMEOUT = 20
SSH_HOST = "ssh.github.com"
SSH_PORT = 443

GIT_CANDIDATES = (
    r"D:\Git\cmd\git.exe",
    r"C:\Program Files\Git\cmd\git.exe",
    r"C:\Program Files (x86)\Git\cmd\git.exe",
)

FORBIDDEN_EXACT = {".env"}
FORBIDDEN_PREFIX = (".env.",)
FORBIDDEN_ALLOWED = {".env.example"}
FORBIDDEN_CONTAINS = (".workbuddy/", "logs/", "node_modules/", "__pycache__/")


def build_env():
    """清掉代理变量，并强制 git 走非交互模式。

    代理必须清掉：WorkBuddy 的沙箱代理对 git 的 CONNECT 隧道返回 502，
    而定时任务本身也不该依赖任何代理。
    """
    env = os.environ.copy()
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        env.pop(key, None)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    # SSH 通道也必须非交互：BatchMode 保证没配好密钥时立刻失败而不是卡住等输入
    env["GIT_SSH_COMMAND"] = (
        "ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10"
    )
    return env


ENV = build_env()


def log(message=""):
    print(message, flush=True)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(message + "\n")
    except Exception:
        pass


def find_git():
    """优先用用户自己安装的 Git（D:\\Git），比随应用打包的 PortableGit 稳定。"""
    for candidate in GIT_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return shutil.which("git")


def run_git(git, args, timeout=None):
    """返回 (returncode, output)。超时返回 (-1, 提示)。"""
    try:
        proc = subprocess.run(
            [git, *args],
            cwd=str(ROOT),
            env=ENV,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, output.strip()
    except subprocess.TimeoutExpired:
        return -1, "命令超时（%ss）" % timeout
    except Exception as exc:
        return -1, "命令异常：%s" % exc


def staged_files(git):
    rc, out = run_git(git, ["diff", "--cached", "--name-only"], timeout=60)
    if rc != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def find_forbidden(files):
    hits = []
    for name in files:
        base = name.replace("\\", "/")
        if base in FORBIDDEN_ALLOWED:
            continue
        if base in FORBIDDEN_EXACT or base.startswith(FORBIDDEN_PREFIX):
            hits.append(name)
            continue
        if any(token in base for token in FORBIDDEN_CONTAINS):
            hits.append(name)
    return hits


def has_unpushed_commits(git):
    """本地是否领先远端。

    定时任务最容易踩的坑：某天网络抖动，提交成功但推送失败；
    第二天工作区是干净的，如果不检查这个，就会被判成"无需操作"，
    导致内容永远上不了线。
    """
    rc, out = run_git(git, ["rev-parse", "--verify", "origin/%s" % BRANCH], timeout=30)
    if rc != 0:
        return True
    rc, out = run_git(git, ["rev-list", "--count", "origin/%s..HEAD" % BRANCH], timeout=60)
    if rc != 0:
        return True
    try:
        return int(out.strip()) > 0
    except ValueError:
        return True


def ssh_url_from(https_url):
    """把 HTTPS 地址换成 SSH-over-443 地址。

    GitHub 的 443 端口 SSH 入口是 ssh.github.com。实测在 HTTPS 被重置的网络里，
    SSH 22 / 443 仍然可用，所以把它作为首选推送通道，HTTPS 退为备用。
    """
    url = (https_url or "").strip().rstrip("/")
    if not url or url.startswith("git@"):
        return None
    for scheme in ("https://", "http://"):
        if url.startswith(scheme):
            url = url[len(scheme):]
            break
    else:
        return None
    if url.endswith(".git"):
        url = url[:-4]
    parts = [p for p in url.split("/") if p]
    if len(parts) < 3:
        return None
    owner, repo = parts[-2], parts[-1]
    return "ssh://git@%s:%d/%s/%s.git" % (SSH_HOST, SSH_PORT, owner, repo)


def main():
    parser = argparse.ArgumentParser(description="提交并推送 AI Frontier 静态站点")
    parser.add_argument("--check", action="store_true", help="只检查是否有改动")
    parser.add_argument("--no-push", action="store_true", help="只本地提交，不推送")
    parser.add_argument("--force", action="store_true", help="无改动也创建提交")
    args = parser.parse_args()

    log("")
    log("=" * 60)
    log(" publish_site.py  START")
    log("=" * 60)

    git = find_git()
    if not git:
        log("[ERROR] 找不到 git 可执行文件，请确认 Git 已安装")
        return 1
    log("[INFO] git : %s" % git)

    rc, out = run_git(git, ["rev-parse", "--is-inside-work-tree"], timeout=30)
    if rc != 0:
        log("[ERROR] 当前目录不是 git 仓库：%s" % ROOT)
        return 1

    rc, out = run_git(git, ["remote", "get-url", "origin"], timeout=30)
    if rc != 0:
        log("[ERROR] 未配置 origin 远端，请先执行 git remote add origin <url>")
        return 1
    remote_url = out.strip()
    log("[INFO] origin: %s" % remote_url)

    rc, out = run_git(git, ["add", "-A"], timeout=120)
    if rc != 0:
        log("[ERROR] git add 失败：%s" % out)
        return 1

    files = staged_files(git)

    if not files and not args.force:
        if has_unpushed_commits(git):
            log("[INFO] 本次没有新改动，但检测到本地有未推送的提交，继续执行推送")
            if args.check:
                log("[CHECK] 存在未推送提交（--check 模式，未做任何写入）")
                return 0
        else:
            log("[INFO] 没有检测到任何改动，本地与远端一致，无需操作")
            log(" publish_site.py  END (nothing to do)")
            return 0

    if files:
        log("[INFO] 待提交文件 %d 个：" % len(files))
        for name in files[:15]:
            log("        + %s" % name)
        if len(files) > 15:
            log("        ... 其余 %d 个" % (len(files) - 15))

        hits = find_forbidden(files)
        if hits:
            log("")
            log("[ABORT] 检测到不该提交的敏感文件，已中止：")
            for name in hits:
                log("        ! %s" % name)
            run_git(git, ["reset"], timeout=60)
            log("        已执行 git reset 撤销暂存，请检查 .gitignore")
            return 1

    if args.check:
        log("[CHECK] 有 %d 个文件待提交（--check 模式，未做任何写入）" % len(files))
        return 0

    message = "chore: daily auto update %s" % date.today().isoformat()
    rc, out = run_git(git, ["commit", "-m", message], timeout=120)
    if rc != 0:
        if "nothing to commit" in out.lower():
            log("[INFO] 工作区干净，无需提交")
        else:
            log("[ERROR] git commit 失败：%s" % out)
            return 1
    else:
        log("[OK] 已本地提交：%s" % message)

    if args.no_push:
        log("[INFO] --no-push 模式，跳过推送")
        log(" publish_site.py  END (local only)")
        return 0

    targets = []
    ssh_url = ssh_url_from(remote_url)
    if ssh_url:
        targets.append(("ssh-443", ssh_url))
    targets.append(("https", "origin"))

    skip_channels = set()
    for attempt in range(1, RETRY_TIMES + 1):
        for label, target in targets:
            if label in skip_channels:
                continue
            log("")
            log("[PUSH] 第 %d/%d 次 · 通道 %s" % (attempt, RETRY_TIMES, label))
            rc, out = run_git(
                git,
                ["-c", "http.connectTimeout=%d" % CONNECT_TIMEOUT, "push", target, BRANCH],
                timeout=PUSH_TIMEOUT,
            )
            if out:
                for line in out.splitlines()[-6:]:
                    log("        %s" % line)

            if rc == 0:
                log("")
                log("[OK] 推送成功（通道 %s），GitHub Pages 将在 1-3 分钟内更新" % label)
                if target != "origin":
                    # 走显式 URL 推送时 git 不会自动更新 origin/main，这里手动对齐
                    run_git(git, ["update-ref", "refs/remotes/origin/%s" % BRANCH, "HEAD"], timeout=30)
                rc_hash, head = run_git(git, ["rev-parse", "--short", "HEAD"], timeout=30)
                if rc_hash == 0:
                    log("[INFO] 当前提交：%s" % head)
                log(" publish_site.py  END (pushed)")
                return 0

            lowered = out.lower()

            if "permission denied" in lowered or "publickey" in lowered:
                log("[INFO] 该通道未授权（SSH 公钥还没加到 GitHub），后续跳过它")
                skip_channels.add(label)
                continue

            if "non-fast-forward" in lowered or "rejected" in lowered or "fetch first" in lowered:
                log("[WARN] 远端有新提交，尝试 pull --rebase 后再推")
                rc_pull, out_pull = run_git(
                    git,
                    ["-c", "http.connectTimeout=%d" % CONNECT_TIMEOUT, "pull", "--rebase", "--autostash", "origin", BRANCH],
                    timeout=PUSH_TIMEOUT,
                )
                if rc_pull != 0:
                    log("[ERROR] pull --rebase 失败：%s" % out_pull)
                    run_git(git, ["rebase", "--abort"], timeout=60)
                    log("[HINT] 已中止 rebase，请手动检查冲突后重跑")
                    return 1

        if len(skip_channels) >= len(targets):
            log("")
            log("[FAILED] 所有推送通道都不可用")
            break
        if attempt < RETRY_TIMES:
            log("[RETRY] %d 秒后重试..." % RETRY_WAIT)
            time_sleep(RETRY_WAIT)

    log("")
    log("[FAILED] 推送未成功")
    log("[HINT] 本地内容已更新并提交，只是没传上去。")
    log("[HINT] 网络恢复后单独运行：python scripts\\publish_site.py")
    log(" publish_site.py  END (push failed)")
    return 5


def time_sleep(seconds):
    import time

    time.sleep(seconds)


if __name__ == "__main__":
    sys.exit(main())
