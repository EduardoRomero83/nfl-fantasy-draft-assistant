@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run.ps1"
if errorlevel 1 (
	echo.
	echo NFL Fantasy Assistant failed to start. Run SETUP.cmd or review the log under %%LOCALAPPDATA%%\NFLFantasyDraftAssistant\logs.
	pause
)