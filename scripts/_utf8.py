"""
_utf8.py
========
Windows 中文环境下的 UTF-8 保险丝。

问题背景：
  在中文 Windows 上，当 Python 的 stdout 被重定向到文件（例如 bat 里的
  `python xxx.py >> log.txt`）时，Python 不会使用控制台的 UTF-8 代码页，
  而是退回系统 ANSI 编码（GBK / cp936）。此时任何 emoji（如 🚀❌✅）都会
  触发 UnicodeEncodeError 并让整个脚本崩溃。

解决方案：
  在脚本最顶部 `import _utf8`，它会强制把 stdout / stderr 重新配置为
  UTF-8（errors="replace" 兜底）。这样无论控制台代码页是什么，都不会崩。

这个模块刻意保持极简、无依赖、无副作用（除重新配置编码外）。
"""

import sys


def _enable_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except Exception:
            # 极少数环境（无 reconfigure 的类文件对象）直接忽略即可
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


_enable_utf8()
