$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$dataDirectory = Join-Path $env:LOCALAPPDATA "NFLFantasyDraftAssistant"
$logDirectory = Join-Path $dataDirectory "logs"
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$logFile = Join-Path $logDirectory ("setup-{0}.log" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
Start-Transcript -Path $logFile -Force | Out-Null

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments
    )
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Executable exited with code $LASTEXITCODE while running: $($Arguments -join ' ')"
    }
}

function Find-Python313 {
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher -ne $null) {
        & $launcher.Source -3.13 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 13) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            return @($launcher.Source, "-3.13")
        }
    }
    $candidates = @(
        Get-ChildItem (Join-Path $env:LOCALAPPDATA "Programs\Python\Python3*\python.exe"), "C:\Program Files\Python3*\python.exe" -ErrorAction SilentlyContinue
    ) | Sort-Object FullName -Descending
    foreach ($candidate in $candidates) {
        & $candidate.FullName -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 13) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            return @($candidate.FullName)
        }
    }
    return @()
}

try {
    $venvPython = Join-Path $PWD ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython -PathType Leaf)) {
        $python = @(Find-Python313)
        if ($python.Count -eq 0) {
            Write-Host "Python 3.13 is not installed. Installing it now..."
            $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
            if ($winget -ne $null) {
                Invoke-Checked $winget.Source install --exact --id Python.Python.3.13 --scope user --accept-package-agreements --accept-source-agreements
            }
            else {
                $installer = Join-Path $env:TEMP "python-3.13.7-amd64.exe"
                Invoke-WebRequest "https://www.python.org/ftp/python/3.13.7/python-3.13.7-amd64.exe" -OutFile $installer
                Invoke-Checked $installer /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0
                Remove-Item $installer -Force -ErrorAction SilentlyContinue
            }
            $python = @(Find-Python313)
        }
        if ($python.Count -eq 0) {
            throw "Python 3.13 installation completed but Python could not be found. Restart Windows and run SETUP.cmd again."
        }
        $pythonExecutable = $python[0]
        $pythonArguments = @($python | Select-Object -Skip 1)
        Invoke-Checked $pythonExecutable @pythonArguments -m venv .venv
    }

    Invoke-Checked $venvPython -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 13) else 1)"
    Invoke-Checked $venvPython -m pip install --disable-pip-version-check --quiet --upgrade pip
    Invoke-Checked $venvPython -m pip install --disable-pip-version-check --quiet --editable .
    Invoke-Checked $venvPython -m nflfantasy configure
    Invoke-Checked $venvPython -m nflfantasy refresh
    Invoke-Checked $venvPython -m nflfantasy doctor
    Invoke-Checked $venvPython -m nflfantasy schedule-install

    Write-Host ""
    Write-Host "Setup complete. Double-click RUN.cmd to use the assistant."
    Write-Host "Thursday alerts are scheduled for 2:00 PM local time."
    Write-Host "Setup log: $logFile"
}
catch {
    Write-Host ""
    Write-Host "SETUP FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Details were saved to: $logFile" -ForegroundColor Yellow
    throw
}
finally {
    Stop-Transcript -ErrorAction SilentlyContinue | Out-Null
}
Read-Host "Press Enter to close"