@echo off
set exePath=%~dp0PCHealthMonitor.exe

echo Running PCHealthMonitor.exe as Administrator...
powershell -Command "Start-Process '%exePath%' -Verb RunAs"
