param(
    [string]$ProjectRoot = "",
    [switch]$HealthCheckOnly
)

$ErrorActionPreference = "Stop"
$dataDirectory = Join-Path $env:LOCALAPPDATA "NFLFantasyDraftAssistant"
$logDirectory = Join-Path $dataDirectory "logs"
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$logFile = Join-Path $logDirectory ("scheduler-{0}.log" -f (Get-Date -Format "yyyy-MM"))
if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
$python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

function Write-SchedulerLog {
    param([string]$Message)
    Add-Content -LiteralPath $logFile -Encoding UTF8 -Value ("{0} [{1}] {2}" -f (Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"), $env:COMPUTERNAME, $Message)
}

try {
    if (-not (Test-Path $python -PathType Leaf)) {
        throw "Persistent Python environment does not exist: $python"
    }
    $env:PYTHONPATH = Join-Path $ProjectRoot "src"
    if ($HealthCheckOnly) {
        $health = & $python -c "import sys, nflfantasy; print(sys.executable)" 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "Python health check failed: $($health | Out-String)"
        }
        Write-SchedulerLog "Health check passed: $($health | Out-String)"
        Write-Output "Scheduler watchdog health check passed."
        exit 0
    }

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $python
    $startInfo.Arguments = "-m nflfantasy scheduled-alert"
    $startInfo.WorkingDirectory = $ProjectRoot
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    if (-not $process.Start()) {
        throw "Windows could not start the scheduled alert."
    }
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    if (-not $process.WaitForExit([int][TimeSpan]::FromMinutes(30).TotalMilliseconds)) {
        $process.Kill()
        throw "Scheduled alert exceeded the 30-minute timeout."
    }
    $process.WaitForExit()
    $stdout = $stdoutTask.Result
    $stderr = $stderrTask.Result
    if ($process.ExitCode -ne 0) {
        throw "Scheduled alert exited with code $($process.ExitCode).`n$stderr`n$stdout"
    }
    Write-SchedulerLog "Scheduled alert succeeded: $($stdout.Trim())"
    Write-Output $stdout.Trim()
}
catch {
    $failure = $_.Exception.Message.Trim()
    Write-SchedulerLog "FAILED: $failure"
    Write-Error "$failure`nLog: $logFile"
    exit 1
}