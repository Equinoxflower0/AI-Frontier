@echo off
REM ============================================================
REM  AI Frontier - Pipeline Test Runner
REM  Double-click this file to verify the pipeline works.
REM  It shows a window, prints the result, and waits for you.
REM  NOTE: Keep this file ASCII-only.
REM ============================================================

chcp 65001 >nul

echo ============================================================
echo   AI Frontier - Pipeline Test
echo ============================================================
echo.
echo   This runs the full pipeline, then pushes to GitHub.
echo.
echo   - It fetches latest AI news via RSS
echo   - Scores and summarizes them with LLM
echo   - Regenerates brief, homepage, playground, tutorials
echo   - Commits and pushes so the live site updates
echo.
echo   Duration: about 15-20 minutes. Keep the PC awake.
echo   Log file: logs\pipeline.log  (publish part: logs\publish.log)
echo.
echo ============================================================
echo.
pause

echo.
echo [Running... please wait, do not close this window]
echo.

call "%~dp0run_daily.bat"
set "RC=%errorlevel%"

echo.
echo ============================================================
if "%RC%"=="0" (
    echo   RESULT: SUCCESS - site updated and pushed
) else if "%RC%"=="5" (
    echo   RESULT: PARTIAL - site updated locally, push failed
    echo   The generated pages are fine; they just did not reach GitHub.
    echo   Run scripts\publish_site.py again later to retry the push.
    echo   Details: logs\publish.log
) else (
    echo   RESULT: FAILED - exit code %RC%
    echo   Please open logs\pipeline.log to see the error.
)
echo ============================================================
echo.
echo   Next steps:
echo   1. Check the log:   logs\pipeline.log
echo   2. Check the brief: daily-brief-YYYY-MM-DD.html
echo.
pause
