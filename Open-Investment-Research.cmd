@echo off
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
  echo Repository Python environment is missing. Ask Codex to check the setup.
  pause
  exit /b 1
)
start "" /b "%~dp0.venv\Scripts\pythonw.exe" "%~dp0scripts\research_workbench.py" --open
