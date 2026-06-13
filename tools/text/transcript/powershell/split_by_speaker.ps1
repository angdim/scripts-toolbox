#!/usr/bin/env pwsh
# scripts-toolbox: entrypoint
# scripts-toolbox: command=split_by_speaker_ps1
<#
.SYNOPSIS
    Разделя transcript по говорители с обединяване на последователни блокове.

.DESCRIPTION
    Скриптът обработва транскрипт във формат:
        [HH:MM:SS] Име на говорител: текст...

    Основна логика:
      • Обединява последователни реплики на един и същ говорител в един абзац.
      • Абзаците се разделят с точно 1 празен ред.
      • combined.txt се генерира в хронологичен ред.
      • split файловете се генерират по говорители.

    Опции:
      --split            Само отделни файлове
      --both             Общ файл + отделни файлове
      --output-dir DIR   Директория за резултатите
      --json             JSON метаданни
      --normalize        Нормализира имена (SPK_01 → SPK_1)
      --video            FFmpeg timestamp списъци
      --log FILE         Лог файл
#>

param(
    [string]$InputFile,

    [switch]$Help,
    [switch]$split,
    [switch]$both,
    [string]$output_dir = ".",
    [switch]$json,
    [switch]$normalize,
    [switch]$video,
    [string]$log
)

if ($Help) {
    Get-Help $PSCommandPath -Detailed
    exit 0
}

if (-not $InputFile) {
    Write-Error "Липсва входен transcript файл. Използвай -Help за помощ."
    exit 1
}

# Подготовка на изходната директория
$outputPath = Resolve-Path $output_dir
if (-not (Test-Path $outputPath)) {
    New-Item -ItemType Directory -Path $outputPath | Out-Null
}

# Логване
if ($log) {
    $logFile = Join-Path $outputPath $log
    function Write-Log($msg) { Add-Content -Path $logFile -Value $msg }
} else {
    function Write-Log($msg) { }
}

# Регулярен израз
$regex = '^\[([0-9]{2}:[0-9]{2}:[0-9]{2})\]\s+([^:]+):\s*(.*)$'

# Структури от данни
$speakers = @{}
$times = @{}
$counts = @{}
$combined_blocks = @()

$currentSpeaker = $null
$currentBlock = ""
$currentTime = $null

function Flush-Block {
    param($speaker, $block, $time)

    if ($speaker -and $block.Trim() -ne "") {
        # Добавяне към общия списък
        $combined_blocks += [PSCustomObject]@{
            Time = $time
            Speaker = $speaker
            Block = $block.TrimEnd()
        }

        # Добавяне към структурата за разделяне
        $speakers[$speaker] += ($block.TrimEnd() + "`n")
    }
}

# Read file
Get-Content -Path $InputFile -Encoding UTF8 | ForEach-Object {
    $line = $_
    if ($line -match $regex) {
        $time = $Matches[1]
        $spk  = $Matches[2].Trim()
        $text = $Matches[3].Trim()

        if ($normalize) {
            $spk = $spk -replace '_0+([0-9])','_$1'
        }

        if (-not $speakers.ContainsKey($spk)) {
            $speakers[$spk] = @()
            $times[$spk] = @()
            $counts[$spk] = 0
        }

        if ($spk -ne $currentSpeaker) {
            Flush-Block -speaker $currentSpeaker -block $currentBlock -time $currentTime
            $currentBlock = "[$time] ${spk}: $text"
            $currentTime = $time
            $times[$spk] += $time
            $counts[$spk]++
        } else {
            $currentBlock += " $text"
        }

        $currentSpeaker = $spk
    }
}

Flush-Block -speaker $currentSpeaker -block $currentBlock -time $currentTime

# ------------------------------------------------------------
# COMBINED FILE
# ------------------------------------------------------------
if (-not $split -or $both) {
    $combinedFile = Join-Path $outputPath "combined.txt"
    "" | Set-Content $combinedFile -Encoding UTF8

    foreach ($entry in $combined_blocks) {
        Add-Content -Path $combinedFile -Value ($entry.Block + "`n") -Encoding UTF8
    }

    Write-Log "Combined file: $combinedFile"
}

# ------------------------------------------------------------
# SPLIT FILES
# ------------------------------------------------------------
if ($split -or $both) {
    foreach ($spk in $speakers.Keys) {
        $safe = ($spk -replace ' ','_') -replace '[^a-zA-Z0-9_]', ''
        $outfile = Join-Path $outputPath "$safe.txt"

        "" | Set-Content $outfile -Encoding UTF8
        foreach ($block in $speakers[$spk]) {
            Add-Content -Path $outfile -Value ($block + "`n") -Encoding UTF8
        }

        Write-Log "Speaker file: $outfile"

        if ($video) {
            $vfile = Join-Path $outputPath "${safe}_video_list.txt"
            "" | Set-Content $vfile -Encoding UTF8
            foreach ($t in $times[$spk]) {
                Add-Content -Path $vfile -Value $t -Encoding UTF8
            }
            Write-Log "Video list: $vfile"
        }
    }
}

# ------------------------------------------------------------
# JSON
# ------------------------------------------------------------
if ($json) {
    $meta = @{}
    foreach ($spk in $speakers.Keys) {
        $safe = ($spk -replace ' ','_') -replace '[^a-zA-Z0-9_]', ''
        $meta[$spk] = @{
            file = "$safe.txt"
            count = $counts[$spk]
        }
    }
    $meta | ConvertTo-Json -Depth 5 -Compress:$false
}

Write-Output "Готово."
