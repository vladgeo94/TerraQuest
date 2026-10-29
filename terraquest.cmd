@echo off
rem TerraQuest launcher for Windows: double-click this file, or run it from a terminal.
where py >nul 2>nul && (py -3 "%~dp0terraquest.py" %*) || (python "%~dp0terraquest.py" %*)
if errorlevel 1 pause
