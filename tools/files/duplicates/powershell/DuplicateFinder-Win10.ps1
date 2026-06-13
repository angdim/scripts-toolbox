# scripts-toolbox: entrypoint
# ============================================
# Пълен търсач на дубликати за Windows 10
# Много дискове/папки, филтри и изключения
# ============================================
<#
.SYNOPSIS
    Търси дублирани файлове в един или повече Windows пътища.

.DESCRIPTION
    Скриптът събира файлове от зададени дискове/директории, групира ги по размер,
    изчислява хешове за потенциалните съвпадения и генерира CSV/HTML отчет.
#>


Clear-Host
Write-Host "=== Пълен търсач на дубликати (Windows 10) ==="
Write-Host ""

# -------------------------------
# ПОТРЕБИТЕЛСКИ ВХОД
# -------------------------------
Write-Host "Въведи пътищата (дялове/директории), разделени със запетая:"
$inputPaths = Read-Host "Пример: C:\, D:\Movies, E:\Backup"
$paths = $inputPaths.Split(",") | ForEach-Object { $_.Trim() }

Write-Host ""
Write-Host "Филтър по разширения (пример: jpg, mp4, pdf)."
$extInput = Read-Host "Остави празно за всички"
$extensions = @()
if ($extInput -ne "") {
    $extensions = $extInput.Split(",") | ForEach-Object { $_.Trim().ToLower() }
}

Write-Host ""
Write-Host "Изключване на папки (пример: C:\Windows, D:\Temp)"
$excludeInput = Read-Host "Остави празно за никакви изключения"
$exclusions = @()
if ($excludeInput -ne "") {
    $exclusions = $excludeInput.Split(",") | ForEach-Object { $_.Trim() }
}

Write-Host ""
Write-Host "=== Стартиране на сканирането... ==="
Write-Host ""

# -------------------------------
# ИЗХОДНИ ФАЙЛОВЕ
# -------------------------------
$log = "scan.log"
$csv = "duplicates_report.csv"
$html = "duplicates_report.html"
$deleteList = "duplicates_to_delete.txt"

"=== Сканирането за дубликати започна ===" | Out-File $log
(Get-Date) | Out-File $log -Append

# -------------------------------
# СЪБИРАНЕ НА ФАЙЛОВЕ
# -------------------------------
Write-Host "Събирам файлове..."

$allFiles = @()

foreach ($p in $paths) {
    if (Test-Path $p) {
        $files = Get-ChildItem -Path $p -Recurse -File -ErrorAction SilentlyContinue

        # Филтър по разширение
        if ($extensions.Count -gt 0) {
            $files = $files | Where-Object { $extensions -contains $_.Extension.TrimStart(".").ToLower() }
        }

        # Изключения
        if ($exclusions.Count -gt 0) {
            foreach ($ex in $exclusions) {
                $files = $files | Where-Object { $_.FullName -notlike "$ex*" }
            }
        }

        $allFiles += $files
    }
}

$total = $allFiles.Count
Write-Host "Намерени файлове: $total"

# -------------------------------
# ГРУПИРАНЕ ПО РАЗМЕР
# -------------------------------
Write-Host "Групиране по размер..."
$sizeGroups = $allFiles | Group-Object Length | Where-Object { $_.Count -gt 1 }

# -------------------------------
# HASH FUNCTION (Win10 compatible)
# -------------------------------
function Get-FileHashSafe {
    param($file)
    try {
        $hash = Get-FileHash -Path $file.FullName -Algorithm SHA256
        return $hash.Hash
    } catch {
        return $null
    }
}

# -------------------------------
# HASH MATCHING SIZES
# -------------------------------
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

# -------------------------------
# FIND DUPLICATES
# -------------------------------
Write-Host "Откриване на дубликати..."
$duplicates = $hashMap.GetEnumerator() | Where-Object { $_.Value.Count -gt 1 }

# -------------------------------
# SAVE CSV
# -------------------------------
"hash,location" | Out-File $csv
foreach ($entry in $duplicates) {
    foreach ($file in $entry.Value) {
        "$($entry.Key),$file" | Out-File $csv -Append
    }
}

# -------------------------------
# SAVE HTML
# -------------------------------
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

# -------------------------------
# DELETE LIST (SAFE MODE)
# -------------------------------
Write-Host "Генерирам списък за изтриване..."
> $deleteList

foreach ($entry in $duplicates) {
    $files = $entry.Value
    $keep = $files[0]
    $delete = $files[1..($files.Count-1)]

    foreach ($d in $delete) {
        $d | Out-File $deleteList -Append
    }
}

Write-Host ""
Write-Host "=== Готово! ==="
Write-Host "Отчетите са създадени:"
Write-Host " - $csv"
Write-Host " - $html"
Write-Host " - $log"
Write-Host " - $deleteList (само списък, не трие)"
