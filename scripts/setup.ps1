$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$python313 = Get-Command py.exe -ErrorAction SilentlyContinue
if ($python313) {
    & py.exe -3.13 --version *> $null
    if ($LASTEXITCODE -ne 0) { $python313 = $null }
}
if (-not $python313) {
    Write-Host "Installing Python 3.13..."
    winget install --exact --id Python.Python.3.13 --accept-package-agreements --accept-source-agreements
}

& py.exe -3.13 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
& .\.venv\Scripts\python.exe -m pip install --quiet .
& .\.venv\Scripts\python.exe -m nflfantasy configure
& .\.venv\Scripts\python.exe -m nflfantasy refresh
& .\.venv\Scripts\python.exe -m nflfantasy doctor

Write-Host ""
Write-Host "Setup complete. Double-click RUN.cmd to use the assistant."
Read-Host "Press Enter to close"