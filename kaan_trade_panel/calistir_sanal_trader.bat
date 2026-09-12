@echo off
REM Bu dosyaya cift tiklayarak sanal trader'i baslatabilirsiniz.
REM Bilgisayar acikken 7/24 arka planda calisir; kapatmak icin bu
REM pencerede bir tusa basin ya da pencereyi kapatin.
cd /d "%~dp0"
".venv\Scripts\python.exe" sanal_trader.py
echo.
echo Sanal trader durdu. Kapatmak icin bir tusa basin.
pause >nul
