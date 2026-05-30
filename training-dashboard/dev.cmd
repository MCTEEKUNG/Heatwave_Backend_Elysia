@echo off
REM One-command launcher for the Heatwave Training Dashboard (local dev).
REM Double-click this file, or run:  training-dashboard\dev.cmd
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1"
