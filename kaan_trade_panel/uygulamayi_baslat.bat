@echo off
REM Bu dosyaya cift tiklayarak paneli baslatabilirsiniz.
REM Tarayicida http://localhost:8501 adresi acilir.
cd /d "%~dp0"
echo Panel baslatiliyor, tarayici birazdan acilacak...
echo Kapatmak icin bu pencerede Ctrl+C yapin.
echo.
".venv\Scripts\python.exe" -m streamlit run uygulama.py
pause
