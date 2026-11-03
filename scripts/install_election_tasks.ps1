# Run once on the same Windows account/PC that already runs run_daily.ps1.
$ErrorActionPreference = "Stop"
$Runner = Join-Path $PSScriptRoot "run_daily.ps1"
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`"" -WorkingDirectory (Split-Path $PSScriptRoot -Parent)
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 4) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 10)
# Explicit offsets make the instants independent of the Windows display timezone.
$Final = ([DateTimeOffset]::Parse("2026-11-04T06:00:00+09:00")).LocalDateTime
$Interim = ([DateTimeOffset]::Parse("2026-11-04T18:00:00+09:00")).LocalDateTime
$Review = ([DateTimeOffset]::Parse("2026-11-07T06:00:00+09:00")).LocalDateTime
$Triggers = @((New-ScheduledTaskTrigger -Once -At $Final), (New-ScheduledTaskTrigger -Once -At $Interim),
              (New-ScheduledTaskTrigger -Once -At $Review))
Register-ScheduledTask -TaskName "AI-Sages-Midterms-Election" -Action $Action -Trigger $Triggers -Settings $Settings -Description "Final forecast Nov 4 06:00 JST; interim retrospective Nov 4 18:00 JST; final retrospective Nov 7 06:00 JST" -Force | Out-Null
Write-Host "Registered election tasks. Keep this Windows account signed in and the PC available."
