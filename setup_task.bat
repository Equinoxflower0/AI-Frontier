@echo off
REM ============================================================
REM  AI Frontier - Register Daily Task
REM  Creates a Windows scheduled task that runs run_daily.bat
REM  every day at 09:00 (pipeline + git push).
REM
REM  HOW TO USE:
REM    Right-click this file -> "Run as administrator"
REM
REM  NOTE: Keep this file ASCII-only.
REM ============================================================

chcp 65001 >nul

set "TASK_NAME=AI_Frontier_Daily_Brief"
set "BAT_PATH=E:\AI-Frontier\run_daily.bat"

echo ============================================================
echo   AI Frontier - Register Daily Task
echo ============================================================
echo.
echo   Task name : %TASK_NAME%
echo   Script    : %BAT_PATH%
echo   Schedule  : Every day at 09:00
echo   Actions   : run pipeline  +  commit and push to GitHub
echo.
echo ============================================================
echo.

REM --- Check admin rights (net session fails without elevation) ---
net session >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Administrator rights required.
    echo.
    echo   Please close this window, then
    echo   RIGHT-CLICK this file and choose "Run as administrator".
    echo.
    pause
    exit /b 1
)

REM --- Remove existing task with same name (ignore errors) ---
schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>&1

REM --- Create the task ---
schtasks /Create /TN "%TASK_NAME%" /TR "%BAT_PATH%" /SC DAILY /ST 09:00 /RL HIGHEST /F

if errorlevel 1 (
    echo.
    echo [FAILED] Could not create the task.
    echo.
    pause
    exit /b 1
)

echo.
echo === Verify ===
schtasks /Query /TN "%TASK_NAME%"

echo.
echo ============================================================
echo   DONE. The task will run every day at 09:00.
echo.
echo   What it does:
echo     1. Fetch and score latest AI news
echo     2. Regenerate brief / index / playground / tutorials
echo     3. Commit and push to GitHub (site goes live in ~2 min)
echo.
echo   Exit code 5 means the site was updated locally but the
echo   push failed (network). Just run publish_site.py later.
echo.
echo   To test it now:
echo     Task Scheduler -^> find "%TASK_NAME%" -^> Right-click -^> Run
echo ============================================================
echo.
pause
