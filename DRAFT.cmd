@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\draft.ps1"
if errorlevel 1 (
	echo.
	echo Draft room failed. Run SETUP.cmd or review the log under %%LOCALAPPDATA%%\NFLFantasyDraftAssistant\logs.
)
pause
