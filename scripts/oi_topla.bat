@echo off
REM Acik pozisyon (OI) + long/short oranini gunceller ve data/oi/ altinda
REM kalici olarak biriktirir. panel_ac.bat ile ayni klasorde, cift tikla
REM calistirilabilir.
REM
REM NEDEN OTOMATIK DEGIL: Binance'in bu veriyi verdigi uc
REM (fapi.binance.com/futures/data/...), GitHub Actions'in ABD merkezli
REM sunucularindan HTTP 451 (cografi engel) ile reddediliyor - normal mum
REM verisinden (klines) FARKLI, daha kisitli bir uc. Bu yuzden bulutta
REM (GitHub Actions) OTOMATIK calisamiyor, sadece SENIN bilgisayarindan
REM (engelli olmayan bir IP'den) calisiyor. Duzenli calistirmak istersen
REM Windows Gorev Zamanlayicisi'na bu .bat dosyasini ekleyebilirsin.
cd /d "%~dp0.."
"C:\Users\Kaan\.venvs\trade-ajani\Scripts\python.exe" scripts\fetch_oi.py
if %errorlevel% equ 0 (
    git add data\oi\
    git diff --staged --quiet || (git commit -m "OI/long-short verisi guncellendi (yerel)" && git push)
)
pause
