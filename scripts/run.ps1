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
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $python -m nflfantasy @Arguments 2>&1 |
            ForEach-Object { $_.ToString() } |
            Tee-Object -FilePath $logFile -Append |
            Out-Host
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($exitCode -ne 0) {
        Write-Host "Command failed with exit code $exitCode. Log: $logFile" -ForegroundColor Red
        return $false
    }
    return $true
}

while ($true) {
    Write-Host ""
    Write-Host "NFL Fantasy Assistant"
    Write-Host "1. Refresh ESPN data"
    Write-Host "2. Show draft recommendations"
    Write-Host "3. Open continuous draft room"
    Write-Host "4. Undo the latest pick"
    Write-Host "5. Build post-draft roster from my picks"
    Write-Host "6. Show expected-points lineup"
    Write-Host "7. Preview Thursday alert"
    Write-Host "8. Email current draft report"
    Write-Host "9. Show Thursday schedule status"
    Write-Host "10. Reconfigure settings and email"
    Write-Host "11. Exit"
    Write-Host "12. Delete/reset the current draft"
    $choice = Read-Host "Choose 1-12"
    switch ($choice) {
        "1" { [void](Invoke-Assistant @("refresh")) }
        "2" { [void](Invoke-Assistant @("board", "--limit", "20")) }
        "3" { [void](Invoke-Assistant @("draft")) }
        "4" { [void](Invoke-Assistant @("undo")) }
        "5" { [void](Invoke-Assistant @("roster", "--from-my-picks")) }
        "6" { [void](Invoke-Assistant @("lineup")) }
        "7" { [void](Invoke-Assistant @("alert")) }
        "8" { [void](Invoke-Assistant @("email")) }
        "9" { [void](Invoke-Assistant @("schedule-status")) }
        "10" { [void](Invoke-Assistant @("configure")) }
        "11" { exit 0 }
        "12" {
            $confirmation = Read-Host "Type RESET to delete all draft picks and derived roster state"
            if ($confirmation -ceq "RESET") {
                [void](Invoke-Assistant @("reset", "--yes"))
            }
            else {
                Write-Host "Draft reset canceled."
            }
        }
        default { Write-Host "Please choose a number from 1 to 12." }
    }
    if ($choice -ne "11") { Read-Host "Press Enter to continue" }
}