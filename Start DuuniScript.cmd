@echo off
rem Double-click to start DuuniScript and open it in your browser.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_duuniscript.ps1"
if errorlevel 1 pause
