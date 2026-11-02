# Daily/election runner: Python chooses the phase using Asia/Tokyo.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
New-Item -ItemType Directory -Force "$Root\logs" | Out-Null
$Log = "$Root\logs\run_$(Get-Date -Format yyyyMMdd_HHmm).log"
$Python = "C:\Users\takuy\AppData\Local\Programs\Python\Python313\python.exe"
$env:PYTHONIOENCODING = "utf-8"
function Write-Log([string]$Text) { $Text | Out-File $Log -Append -Encoding utf8 }
function Invoke-Logged([string]$CommandLine) {
    cmd /c "$CommandLine 2>&1" | Out-File $Log -Append -Encoding utf8
    return $LASTEXITCODE
}
# Coordinate existing daily tasks and the additional election triggers.
try { $Lock = [System.IO.File]::Open("$Root\logs\runner.lock", 'OpenOrCreate', 'ReadWrite', 'None') }
catch { Write-Log "Another runner is active; skipping."; exit 0 }
$Result = 0
try {
    Write-Log "=== $(Get-Date -Format o) start"
    # Sync first: pushing while behind origin (e.g. after a commit made elsewhere) is rejected even with nothing
    # to publish. Then retry any previous failed push. A conflicting rebase is aborted so later runs start clean.
    if ((Invoke-Logged "git pull --rebase --quiet") -ne 0) {
        Invoke-Logged "git rebase --abort" | Out-Null
        throw "git pull failed"
    }
    if ((Invoke-Logged "git push") -ne 0) { throw "Could not publish previous commits" }
    $Result = Invoke-Logged "`"$Python`" -u scripts\predict.py"
    Write-Log "predict exit: $Result"
    # Publish partial successes too; successful retrospectives are never regenerated.
    if ((Invoke-Logged "git add data") -ne 0) { throw "git add failed" }
    git diff --cached --quiet
    if ($LASTEXITCODE -eq 1) {
        if ((Invoke-Logged "git commit -m `"Election update $(Get-Date -Format yyyy-MM-dd)`"") -ne 0) { throw "git commit failed" }
        if ((Invoke-Logged "git push") -ne 0) { throw "git push failed" }
    } elseif ($LASTEXITCODE -ne 0) { throw "git diff failed" }
    Write-Log "=== $(Get-Date -Format o) end"
} catch {
    Write-Log "FAILED: $_"
    $Result = 1
} finally { $Lock.Dispose() }
exit $Result
