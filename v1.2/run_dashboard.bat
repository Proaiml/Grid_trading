@echo off
setlocal
cd /d "%~dp0"
title Binance Grid Trading Bot v1.2 Pro - Web Dashboard

echo ========================================================
echo    BINANCE GRID TRADING BOT v1.2 PRO - WEB DASHBOARD
echo    Gelismis Tek Ekran Yonetim, Simulasyon ve .BAT Uretici
echo ========================================================
echo.

where py >nul 2>&1
if %errorlevel%==0 (
    set "PY=py -3"
) else (
    where python >nul 2>&1
    if %errorlevel% neq 0 (
        echo [HATA] Python bulunamadi. Python 3.10+ kurup PATH'e ekleyin.
        pause
        exit /b 1
    )
    set "PY=python"
)

echo [1/3] Python kontrol ediliyor...
%PY% -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ gerekli'; print('Python:', sys.version.split()[0])"
if %errorlevel% neq 0 (
    echo [HATA] Python 3.10 veya daha yeni bir surum gerekli.
    pause
    exit /b 1
)

echo [2/3] Web dashboard gereksinimleri kontrol ediliyor...
%PY% -c "import fastapi, uvicorn, pydantic" >nul 2>&1
if %errorlevel% neq 0 (
    echo Gerekli paketler (fastapi, uvicorn, pydantic) yukleniyor...
    %PY% -m pip install fastapi uvicorn pydantic python-binance
    if %errorlevel% neq 0 (
        echo [HATA] Paketler yuklenemedi.
        pause
        exit /b 1
    )
)

echo [3/3] Web Arayuzu baslatiliyor...
echo.
echo Tarayiciniz otomatik acilacaktir: http://127.0.0.1:8000
echo Paneli kapatmak icin bu pencereyi kapatin veya CTRL+C yapin.
echo.

start "" "http://127.0.0.1:8000"

%PY% dashboard\server.py

pause
endlocal
