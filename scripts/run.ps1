$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)
$python = ".\.venv\Scripts\python.exe"

while ($true) {
    Write-Host ""
    Write-Host "NFL Fantasy Assistant"
    Write-Host "1. Refresh ESPN data"
    Write-Host "2. Show draft recommendations"
    Write-Host "3. Record a draft pick"
    Write-Host "4. Undo the latest pick"
    Write-Host "5. Build post-draft roster from my picks"
    Write-Host "6. Show expected-points lineup"
    Write-Host "7. Email current draft report"
    Write-Host "8. Exit"
    $choice = Read-Host "Choose 1-8"
    switch ($choice) {
        "1" { & $python -m nflfantasy refresh }
        "2" { & $python -m nflfantasy board --limit 20 }
        "3" {
            $player = Read-Host "Player name"
            $mine = Read-Host "Was this your pick? (y/n)"
            if ($mine -eq "y") { & $python -m nflfantasy pick $player --mine }
            else { & $python -m nflfantasy pick $player }
        }
        "4" { & $python -m nflfantasy undo }
        "5" { & $python -m nflfantasy roster --from-my-picks }
        "6" { & $python -m nflfantasy lineup }
        "7" { & $python -m nflfantasy email }
        "8" { exit 0 }
        default { Write-Host "Please choose a number from 1 to 8." }
    }
    if ($choice -ne "8") { Read-Host "Press Enter to continue" }
}