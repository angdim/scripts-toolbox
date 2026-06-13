@echo off
REM scripts-toolbox: entrypoint
REM scripts-toolbox: command=split_by_speaker_bat
setlocal enabledelayedexpansion

REM Предназначение: изрязва видео сегменти по говорители според transcript timestamp-и.

REM ============================
REM КОНФИГУРАЦИЯ
REM ============================
set PAUSE_SECONDS=0

REM ============================
REM ВХОД
REM ============================
set TRANSCRIPT=%1
set VIDEO=%2

if "%TRANSCRIPT%"=="" (
    echo Употреба: split_by_speaker.bat transcript.txt video.mp4
    exit /b
)

if "%VIDEO%"=="" (
    echo Употреба: split_by_speaker.bat transcript.txt video.mp4
    exit /b
)

REM ============================
REM ВЗЕМАНЕ НА VIDEO РАЗШИРЕНИЕ
REM ============================
for %%F in ("%VIDEO%") do set VIDEO_EXT=%%~xF

REM ============================
REM ВЗЕМАНЕ НА VIDEO ПРОДЪЛЖИТЕЛНОСТ (секунди)
REM ============================
for /f "tokens=* usebackq" %%A in (`ffprobe -v error -show_entries format^=duration -of default^=nokey^=1:noprint_wrappers^=1 "%VIDEO%"`) do (
    set VIDEO_DURATION=%%A
)

REM ============================
REM ПАРСВАНЕ НА TRANSCRIPT
REM ============================
set COUNT=0

for /f "usebackq tokens=* delims=" %%L in ("%TRANSCRIPT%") do (
    set LINE=%%L

    REM Съвпадение: Име — HH:MM:SS
    for /f "tokens=1,2 delims=—" %%A in ("!LINE!") do (
        set LEFT=%%A
        set RIGHT=%%B
    )

    REM Премахване на водещи интервали
    for /f "tokens=* delims= " %%A in ("!LEFT!") do set SPEAKER=%%A
    for /f "tokens=* delims= " %%A in ("!RIGHT!") do set TIME=%%A

    REM Проверка дали TIME съвпада с H:MM:SS или HH:MM:SS
    echo !TIME! | findstr /r "^[0-9][0-9]*:[0-9][0-9]:[0-9][0-9]$" >nul
    if !errorlevel! == 0 (
        set SPEAKERS[!COUNT!]=!SPEAKER!
        set STARTS[!COUNT!]=!TIME!
        set /a COUNT+=1
    )
)

REM ============================
REM ОБРАБОТКА НА ВСЕКИ ГОВОРИТЕЛ
REM ============================
for /l %%I in (0,1,%COUNT%) do (
    set CURR_SPEAKER=!SPEAKERS[%%I]!
    if "!CURR_SPEAKER!"=="" (
        REM пропускане на празни стойности
    ) else (
        set SAFE=!CURR_SPEAKER: =_!
        set LIST=%SAFE%_concat.txt
        break > "%LIST%"

        REM Обхождане на всички реплики за този говорител
        for /l %%J in (0,1,%COUNT%) do (
            if "!SPEAKERS[%%J]!"=="!CURR_SPEAKER!" (
                set START=!STARTS[%%J]!

                REM Determine END
                set /a NEXT=%%J+1
                if !NEXT! LSS %COUNT% (
                    set END=!STARTS[!NEXT!]!
                    REM Compute duration
                    for /f "tokens=1-3 delims=:" %%h in ("!START!") do (
                        set /a S1=%%h*3600 + %%i*60 + %%j
                    )
                    for /f "tokens=1-3 delims=:" %%h in ("!END!") do (
                        set /a S2=%%h*3600 + %%i*60 + %%j
                    )
                    set /a DUR=S2-S1
                ) else (
                    REM Last segment → until end of video
                    for /f "tokens=1-3 delims=:" %%h in ("!START!") do (
                        set /a S1=%%h*3600 + %%i*60 + %%j
                    )
                    set /a DUR=%VIDEO_DURATION% - S1
                )

                set OUT=%SAFE%_%%J%VIDEO_EXT%

                ffmpeg -y -ss "!START!" -t !DUR! -i "%VIDEO%" -c copy "!OUT!"
                echo file '!OUT!' >> "%LIST%"

                if %PAUSE_SECONDS% GTR 0 (
                    set PAUSEFILE=%SAFE%_pause_%%J%VIDEO_EXT%
                    ffmpeg -y -f lavfi -i color=black:s=1920x1080:d=%PAUSE_SECONDS% -f lavfi -i anullsrc -shortest "!PAUSEFILE!"
                    echo file '!PAUSEFILE!' >> "%LIST%"
                )
            )
        )

        REM Final output
        set FINAL=%SAFE%_video%VIDEO_EXT%

        if %PAUSE_SECONDS%==0 (
            ffmpeg -y -f concat -safe 0 -i "%LIST%" -c copy "%FINAL%"
        ) else (
            ffmpeg -y -f concat -safe 0 -i "%LIST%" -c:v libx264 -c:a aac "%FINAL%"
        )

        echo Готово: %FINAL%
    )
)

echo Всички файлове са обработени.

