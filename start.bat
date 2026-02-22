@echo off
REM Quick start script for ARI Milestone 1-2 vertical slice (Windows)
REM Usage: start.bat [backend|frontend|both]

setlocal enabledelayedexpansion

set MODE=%1
if "%MODE%"=="" set MODE=both

echo.
echo 🚀 ARI Vertical Slice Starter (Windows)
echo ═════════════════════════════════════════════════════════════
echo.

if /i "%MODE%"=="backend" goto start_backend
if /i "%MODE%"=="frontend" goto start_frontend
if /i "%MODE%"=="both" goto start_both
goto usage

:start_backend
echo Starting Backend API (Quart)...
echo Directory: %CD%\apps\api
echo.
cd /d "%CD%\apps\api"

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

python -c "import quart" 2>nul
if errorlevel 1 (
    echo Installing requirements...
    pip install -q -r requirements.txt
)

if not exist .env (
    echo Creating .env from template...
    copy .env.example .env >nul
)

echo.
echo ✅ Backend ready!
echo 🌐 Starting server on http://localhost:8000
echo.
python app.py
goto end

:start_frontend
echo Starting Frontend (Next.js)...
echo Directory: %CD%\apps\web
echo.
cd /d "%CD%\apps\web"

if not exist node_modules (
    echo Installing dependencies...
    call pnpm install
)

if not exist .env.local (
    echo Creating .env.local...
    (
        echo NEXT_PUBLIC_API_URL=http://localhost:8000
    ) > .env.local
) else (
    findstr /m "NEXT_PUBLIC_API_URL" .env.local >nul
    if errorlevel 1 (
        echo Adding NEXT_PUBLIC_API_URL to .env.local...
        echo NEXT_PUBLIC_API_URL=http://localhost:8000 >> .env.local
    )
)

echo.
echo ✅ Frontend ready!
echo 🌐 Starting dev server on http://localhost:3000
echo.
call pnpm dev
goto end

:start_both
echo.
echo ⚠️  To run both, open two Command Prompts and run:
echo    Command Prompt 1: start.bat backend
echo    Command Prompt 2: start.bat frontend
echo.
echo Starting backend in this terminal...
echo.
goto start_backend

:usage
echo Usage: start.bat [backend|frontend|both]
echo.
echo Examples:
echo   start.bat backend    - Start just the backend API
echo   start.bat frontend   - Start just the frontend
echo   start.bat both       - Show instructions for running both
goto end

:end
endlocal
