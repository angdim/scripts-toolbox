BeforeAll {
    $RepoRoot = (Resolve-Path "$PSScriptRoot/../..").Path
    $ScriptPath = Join-Path $RepoRoot "tools/text/transcript/powershell/split_by_speaker.ps1"
}

Describe "PowerShell split_by_speaker" {
    It "parses without interpolation errors" {
        { [scriptblock]::Create((Get-Content -Raw $ScriptPath)) } | Should -Not -Throw
    }

    It "splits a transcript into speaker files" {
        $TempDir = Join-Path ([System.IO.Path]::GetTempPath()) ([System.Guid]::NewGuid().ToString())
        New-Item -ItemType Directory -Path $TempDir | Out-Null
        try {
            $InputFile = Join-Path $TempDir "transcript.txt"
            @"
[00:00:01] SPK_01: First line
[00:00:03] SPK_01: second line
[00:00:05] SPK_02: Other speaker
"@ | Set-Content -Path $InputFile -Encoding UTF8

            & $ScriptPath -InputFile $InputFile -split -output_dir $TempDir -normalize
            Test-Path (Join-Path $TempDir "SPK_1.txt") | Should -BeTrue
            Test-Path (Join-Path $TempDir "SPK_2.txt") | Should -BeTrue
            (Get-Content -Raw (Join-Path $TempDir "SPK_1.txt")) | Should -Match "SPK_1: First line second line"
        }
        finally {
            Remove-Item -Recurse -Force $TempDir -ErrorAction SilentlyContinue
        }
    }
}
