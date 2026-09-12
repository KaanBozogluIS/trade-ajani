@echo off
REM Bu dosyaya cift tiklayarak botu baslatabilirsiniz.
cd /d "%~dp0"
".venv\Scripts\python.exe" bot.py
echo.
echo Bot durdu. Kapatmak icin bir tusa basin.
pause >nul
