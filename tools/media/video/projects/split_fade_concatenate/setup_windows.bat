@echo off
REM Предназначение: проверява Windows зависимостите за split/fade/concat project workflow.
echo Проверка на Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ГРЕШКА: Python не е инсталиран.
    echo Свали от https://www.python.org/downloads/
    echo Важно: Постави отметка на "Add Python to PATH" при инсталация!
    pause
    exit /b 1
)

echo Инсталиране на зависимости...
pip install jsonschema

echo.
echo Проверка на ffmpeg...
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo ГРЕШКА: ffmpeg не е намерен в PATH.
    echo.
    echo Инструкции:
    echo 1. Свали ffmpeg от https://www.gyan.dev/ffmpeg/builds/
    echo    ^(ffmpeg-release-essentials.zip^)
    echo 2. Разархивирай и копирай ffmpeg.exe, ffplay.exe, ffprobe.exe
    echo    в C:\Windows\System32\ или в папката на проекта
    pause
    exit /b 1
)

echo.
echo Всичко е готово! Стартирай с: python main.py
pause
