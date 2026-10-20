@echo off
cd /d "%~dp0"
if exist "C:\Python314\python.exe" (
  "C:\Python314\python.exe" push.py
) else (
  python push.py
)
pause
