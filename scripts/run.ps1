$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$python = ".\.venv\Scripts\python.exe"
$dataDirectory = Join-Path $env:LOCALAPPDATA "NFLFantasyDraftAssistant"
$logDirectory = Join-Path $dataDirectory "logs"
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$logFile = Join-Path $logDirectory ("menu-{0}.log" -f (Get-Date -Format "yyyy-MM"))

if (-not (Test-Path $python -PathType Leaf)) {
    throw "The Python environment is missing. Run SETUP.cmd first."
}

function Invoke-Assistant {
    param([string[]]$Arguments)
    & $python -m nflfantasy @Arguments 2>&1 | Tee-Object -FilePath $logFile -Append
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Command failed with exit code $LASTEXITCODE. Log: $logFile" -ForegroundColor Red
        return $false
    }
    return $true
}

while ($true) {
    Write-Host ""
    Write-Host "NFL Fantasy Assistant"
    Write-Host "1. Refresh ESPN data"
    Write-Host "2. Show draft recommendations"
    Write-Host "3. Record a draft pick"
    Write-Host "4. Undo the latest pick"
    Write-Host "5. Build post-draft roster from my picks"
    Write-Host "6. Show expected-points lineup"
    Write-Host "7. Preview Thursday alert"
    Write-Host "8. Email current draft report"
    Write-Host "9. Show Thursday schedule status"
    Write-Host "10. Reconfigure settings and email"
    Write-Host "11. Exit"
    $choice = Read-Host "Choose 1-11"
    switch ($choice) {
        "1" { [void](Invoke-Assistant @("refresh")) }
        "2" { [void](Invoke-Assistant @("board", "--limit", "20")) }
        "3" {
            $player = Read-Host "Player name"
            $mine = Read-Host "Was this your pick? (y/n)"
            if ($mine -eq "y") { [void](Invoke-Assistant @("pick", $player, "--mine")) }
            else { [void](Invoke-Assistant @("pick", $player)) }
        }
        "4" { [void](Invoke-Assistant @("undo")) }
        "5" { [void](Invoke-Assistant @("roster", "--from-my-picks")) }
        "6" { [void](Invoke-Assistant @("lineup")) }
        "7" { [void](Invoke-Assistant @("alert")) }
        "8" { [void](Invoke-Assistant @("email")) }
        "9" { [void](Invoke-Assistant @("schedule-status")) }
        "10" { [void](Invoke-Assistant @("configure")) }
        "11" { exit 0 }
        default { Write-Host "Please choose a number from 1 to 11." }
    }
    if ($choice -ne "11") { Read-Host "Press Enter to continue" }
}