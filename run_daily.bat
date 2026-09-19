@echo off
REM ============================================================
REM  AI Frontier - Daily Auto Update Script
REM  Fetch RSS -> LLM scoring -> Render brief -> Render index
REM  Called by Windows Task Scheduler
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
echo.>> "%LOG%"

"%PYTHON%" scripts\run_pipeline.py --mode llm >> "%LOG%" 2>&1
set "RC=%errorlevel%"

REM ---------- WRITE END MARKER ----------
echo.>> "%LOG%"
echo ===========================================================>> "%LOG%"
echo  AI Frontier pipeline END >> "%LOG%"
>> "%LOG%" echo  Exit code = %RC%
echo ===========================================================>> "%LOG%"

if %RC% neq 0 (
    echo [FAILED] Pipeline exited with code %RC%
    echo Log: %LOG%
    exit /b %RC%
)

echo [SUCCESS] Pipeline completed.
echo Log: %LOG%
exit /b 0
