@echo off
REM ============================================================
REM  AI Frontier - Register Daily Task
REM  Creates a Windows scheduled task that runs run_daily.bat
REM  every day at 09:00 (pipeline + git push).
REM
REM  Method 1: schtasks  (classic)
REM  Method 2: Register-ScheduledTask (fallback, used when a
REM            security policy blocks schtasks with Access denied)
REM
REM  HOW TO USE:
REM    Right-click this file -> "Run as administrator"
REM    (The PowerShell fallback usually works even without admin.)
REM
REM  NOTE: Keep this file ASCII-only.
REM ============================================================

chcp 65001 >nul

set "TASK_NAME=AI_Frontier_Daily_Brief"
set "BAT_PATH=E:\AI-Frontier\run_daily.bat"
set "WORK_DIR=E:\AI-Frontier"

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

REM --- Create the task (method 1: schtasks) ---
schtasks /Create /TN "%TASK_NAME%" /TR "%BAT_PATH%" /SC DAILY /ST 09:00 /RL HIGHEST /F >nul 2>&1
if not errorlevel 1 goto :verify

echo [WARN] schtasks was denied by policy. Trying PowerShell method ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$a = New-ScheduledTaskAction -Execute '%BAT_PATH%' -WorkingDirectory '%WORK_DIR%'; $t = New-ScheduledTaskTrigger -Daily -At 09:00; $s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable; Register-ScheduledTask -TaskName '%TASK_NAME%' -Action $a -Trigger $t -Settings $s -Force | Out-Null"
if errorlevel 1 goto :failed

:verify
powershell -NoProfile -ExecutionPolicy Bypass -Command "$t = Get-ScheduledTask -TaskName '%TASK_NAME%' -ErrorAction SilentlyContinue; if ($t) { Write-Host ('[OK] Task registered. State: ' + $t.State); $i = Get-ScheduledTaskInfo -TaskName '%TASK_NAME%'; Write-Host ('[OK] Next run: ' + $i.NextRunTime); exit 0 } else { Write-Host '[FAILED] Task not found.'; exit 1 }"
if errorlevel 1 goto :failed

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
exit /b 0

:failed
echo.
echo [FAILED] Could not create the task with either method.
echo   1. Make sure you right-clicked and chose "Run as administrator"
echo   2. Or open "Task Scheduler" GUI and create it manually
echo      (see README, section: automation, GUI path, step by step)
echo.
pause
exit /b 1
