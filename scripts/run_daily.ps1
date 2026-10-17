# Daily job: run all model forecasts, then publish to GitHub Pages.
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
New-Item -ItemType Directory -Force "$Root\logs" | Out-Null
$Log = "$Root\logs\run_$(Get-Date -Format yyyyMMdd_HHmm).log"
$Python = "C:\Users\takuy\AppData\Local\Programs\Python\Python313\python.exe"
$env:PYTHONIOENCODING = "utf-8"

function Write-Log([string]$Text) { $Text | Out-File $Log -Append -Encoding utf8 }
# cmd /c keeps native stdout/stderr as plain text (PowerShell 5.1 would otherwise log stderr as error records / UTF-16)
function Invoke-Logged([string]$CommandLine) {
    cmd /c "$CommandLine 2>&1" | Out-File $Log -Append -Encoding utf8
    return $LASTEXITCODE
}

Write-Log "=== $(Get-Date -Format o) start"
Invoke-Logged "git pull --rebase --quiet" | Out-Null
$rc = Invoke-Logged "`"$Python`" -u scripts\predict.py"
Write-Log "predict exit: $rc"

Invoke-Logged "git add data" | Out-Null
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    Invoke-Logged "git commit -m `"Daily forecast $(Get-Date -Format yyyy-MM-dd)`"" | Out-Null
    $rc = Invoke-Logged "git push"
    Write-Log "push exit: $rc"
} else {
    Write-Log "no changes"
}
Write-Log "=== $(Get-Date -Format o) end"
