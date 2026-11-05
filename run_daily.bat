@echo off
REM ============================================================
REM  AI Frontier - Daily Auto Update Script
REM  Step 1: Fetch RSS -> LLM scoring -> Render brief/index/playground/tutorials
REM  Step 2: Commit and push to GitHub so the live site refreshes
REM  Called by Windows Task Scheduler (daily at 09:00)
REM  NOTE: Keep this file ASCII-only to avoid cmd.exe codepage issues.
REM ============================================================

setlocal
chcp 65001 >nul

REM ---------- CONFIG (adjust to your machine) ----------
set "WORK_DIR=E:\AI-Frontier"
REM Python path is built from %USERPROFILE% so this file stays portable and
REM contains no hard-coded user name.
set "PYTHON=%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe"
set "LOG_DIR=%WORK_DIR%\logs"
set "LOG=%LOG_DIR%\pipeline.log"

REM ---------- PREPARE LOG DIR ----------
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" 2>nul

REM ---------- WRITE START MARKER (proves the script was launched) ----------
echo ===========================================================>> "%LOG%"
echo  AI Frontier pipeline START >> "%LOG%"
>> "%LOG%" echo  Time: %time%
echo ===========================================================>> "%LOG%"

REM ---------- SANITY CHECKS ----------
cd /d "%WORK_DIR%"
if errorlevel 1 (
    echo [ERROR] Cannot cd to WORK_DIR: %WORK_DIR%>> "%LOG%"
    echo [ERROR] Cannot cd to WORK_DIR
    exit /b 2
)

if not exist "%PYTHON%" (
    echo [ERROR] Python not found: %PYTHON%>> "%LOG%"
    echo [ERROR] Python not found: %PYTHON%
    exit /b 3
)

if not exist "%WORK_DIR%\scripts\run_pipeline.py" (
    echo [ERROR] run_pipeline.py not found>> "%LOG%"
    echo [ERROR] run_pipeline.py not found
    exit /b 4
)

REM ---------- RUN PIPELINE ----------
echo [INFO] Python : %PYTHON%>> "%LOG%"
echo [INFO] WorkDir: %WORK_DIR%>> "%LOG%"
>> "%LOG%" echo.
>> "%LOG%" echo [STEP 1/2] Running content pipeline ...
"%PYTHON%" scripts\run_pipeline.py --mode llm >> "%LOG%" 2>&1
set "RC=%errorlevel%"

if %RC% neq 0 (
    >> "%LOG%" echo [FAILED] Pipeline exited with code %RC%
    echo [FAILED] Pipeline exited with code %RC%
    echo Log: %LOG%
    exit /b %RC%
)

REM ---------- PUBLISH TO GITHUB ----------
REM Commits the regenerated pages and pushes them so GitHub Pages goes live.
>> "%LOG%" echo.
>> "%LOG%" echo [STEP 2/2] Committing and pushing to GitHub ...
"%PYTHON%" scripts\publish_site.py >> "%LOG%" 2>&1
set "PRC=%errorlevel%"

REM ---------- WRITE END MARKER ----------
>> "%LOG%" echo.
>> "%LOG%" echo ===========================================================
>> "%LOG%" echo  AI Frontier pipeline END
>> "%LOG%" echo  Pipeline exit code = %RC%
>> "%LOG%" echo  Publish  exit code = %PRC%
>> "%LOG%" echo ===========================================================

if %PRC% neq 0 (
    echo [WARN] Site updated locally, but push to GitHub failed.
    echo [WARN] Log: %LOG%
    echo [HINT] Retry later: python scripts\publish_site.py
    exit /b 5
)

echo [SUCCESS] Content updated and published to GitHub.
echo Site: https://equinoxflower0.github.io/AI-Frontier/
echo Log : %LOG%
exit /b 0
