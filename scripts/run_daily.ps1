# Daily job: run all model forecasts, then publish to GitHub Pages.
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
New-Item -ItemType Directory -Force "$Root\logs" | Out-Null
$Log = "$Root\logs\run_$(Get-Date -Format yyyyMMdd_HHmm).log"
$Python = "C:\Users\takuy\AppData\Local\Programs\Python\Python313\python.exe"

"=== $(Get-Date -Format o) start" | Out-File $Log -Encoding utf8
git pull --rebase --quiet *>> $Log
& $Python -u scripts\predict.py *>> $Log
"predict exit: $LASTEXITCODE" | Out-File $Log -Append -Encoding utf8

git add data *>> $Log
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m "Daily forecast $(Get-Date -Format yyyy-MM-dd)" *>> $Log
    git push *>> $Log
    "push exit: $LASTEXITCODE" | Out-File $Log -Append -Encoding utf8
} else {
    "no changes" | Out-File $Log -Append -Encoding utf8
}
"=== $(Get-Date -Format o) end" | Out-File $Log -Append -Encoding utf8
