# scripts-toolbox: entrypoint
# ================================
# Търсач на дубликати за Windows 11
# Поддръжка на много дискове и папки
# ================================
<#
.SYNOPSIS
    Търси дублирани файлове в един или повече Windows пътища.

.DESCRIPTION
    Скриптът събира файлове от зададени дискове/директории, групира ги по размер,
    изчислява хешове за потенциалните съвпадения и генерира CSV/HTML отчет.
#>


# Как да се стартира скрипта
# 1. Стартирай PowerShell като Administrator.
# 2. Разреши изпълнение на локални скриптове (само веднъж):
#     Set-ExecutionPolicy RemoteSigned
# 3. Стартирай скрипта:
#     .\Find-Duplicates.ps1


Write-Host "=== Сканиране за дублирани файлове ==="
Write-Host "Въведи пътищата (дялове или директории), разделени със запетая:"
Write-Host "Пример: C:\, D:\Movies, E:\Backup"
$inputPaths = Read-Host "Пътища"

$paths = $inputPaths.Split(",") | ForEach-Object { $_.Trim() }

if ($paths.Count -lt 1) {
    Write-Host "Не са въведени валидни пътища. Прекратяване."
    exit
}

$log = "scan.log"
$csv = "duplicates_report.csv"
$html = "duplicates_report.html"

"=== Сканирането за дубликати започна ===" | Out-File $log
(Get-Date) | Out-File $log -Append

# Събиране на всички файлове
Write-Host "Събирам списък с файлове..."
$allFiles = foreach ($p in $paths) {
    if (Test-Path $p) {
        Get-ChildItem -Path $p -Recurse -File -ErrorAction SilentlyContinue
    }
}

$total = $allFiles.Count
Write-Host "Намерени файлове: $total"

# Групиране по размер
Write-Host "Групиране по размер..."
$sizeGroups = $allFiles | Group-Object Length | Where-Object { $_.Count -gt 1 }

# Функция за хеширане
function Get-FileHashSafe {
    param($file)
    try {
        return (Get-FileHash -Path $file.FullName -Algorithm SHA256).Hash
    } catch {
        return $null
    }
}

# Хеширане само на файлове със съвпадащи размери
Write-Host "Хеширане на файлове със съвпадащи размери..."
$hashMap = @{}

foreach ($group in $sizeGroups) {
    foreach ($file in $group.Group) {
        $hash = Get-FileHashSafe $file
        if ($hash) {
            if (-not $hashMap.ContainsKey($hash)) {
                $hashMap[$hash] = @()
            }
            $hashMap[$hash] += $file.FullName
        }
    }
}

# Търсене на дубликати
Write-Host "Откриване на дубликати..."
$duplicates = $hashMap.GetEnumerator() | Where-Object { $_.Value.Count -gt 1 }

# Запис на CSV
"hash,location" | Out-File $csv
foreach ($entry in $duplicates) {
    foreach ($file in $entry.Value) {
        "$($entry.Key),$file" | Out-File $csv -Append
    }
}

# Save HTML
$htmlHeader = @"
<html><body>
<h1>Отчет за дубликати</h1>
<table border='1'>
<tr><th>Hash</th><th>Location</th></tr>
"@
$htmlHeader | Out-File $html

foreach ($entry in $duplicates) {
    foreach ($file in $entry.Value) {
        "<tr><td>$($entry.Key)</td><td>$file</td></tr>" | Out-File $html -Append
    }
}

"</table></body></html>" | Out-File $html -Append

Write-Host "Готово!"
Write-Host "Отчетите са създадени:"
Write-Host " - $csv"
Write-Host " - $html"
Write-Host " - $log"
