@echo off
REM Trade Ajani panelini baslatir ve tarayicida acar.
REM Bu dosyaya cift tiklayarak (veya masaustundeki kisayoldan) calistirabilirsiniz.

cd /d "%~dp0\.."
echo Trade Ajani paneli baslatiliyor...
echo Tarayicida otomatik acilmazsa: http://localhost:8501
"C:\Users\Kaan\.venvs\trade-ajani\Scripts\streamlit.exe" run dashboard\Home.py
pause
