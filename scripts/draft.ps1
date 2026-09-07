$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$python = ".\.venv\Scripts\python.exe"
$dataDirectory = Join-Path $env:LOCALAPPDATA "NFLFantasyDraftAssistant"
$logDirectory = Join-Path $dataDirectory "logs"
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$logFile = Join-Path $logDirectory ("draft-{0}.log" -f (Get-Date -Format "yyyyMMdd-HHmmss"))

if (-not (Test-Path $python -PathType Leaf)) {
    throw "The Python environment is missing. Run SETUP.cmd first."
}

Start-Transcript -Path $logFile -Force | Out-Null
try {
    & $python -m nflfantasy draft
    if ($LASTEXITCODE -ne 0) {
        throw "Draft room exited with code $LASTEXITCODE. Log: $logFile"
    }
}
finally {
    Stop-Transcript -ErrorAction SilentlyContinue | Out-Null
}
