@echo off
setlocal
cd /d "%~dp0"
title Grid Trading Bot v1.3 Full

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
%PY% -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ gerekli'; print(sys.version)"
if %errorlevel% neq 0 (
    echo [HATA] Python 3.10 veya daha yeni bir surum gerekli.
    pause
    exit /b 1
)

echo [2/3] python-binance kontrol ediliyor...
%PY% -c "import binance" >nul 2>&1
if %errorlevel% neq 0 (
    echo python-binance bulunamadi. Kuruluyor...
    %PY% -m pip install --upgrade python-binance
    if %errorlevel% neq 0 (
        echo [HATA] python-binance kurulamadı.
        pause
        exit /b 1
    )
)

echo [3/3] Dahili guvenlik testleri calistiriliyor...
%PY% main.py --self-test
if %errorlevel% neq 0 (
    echo [HATA] Self-test basarisiz. Bot baslatilmadi.
    pause
    exit /b 1
)

echo.
echo Grid Bot baslatiliyor...
echo Cikmak icin Ctrl+C kullanin.
echo.
%PY% main.py

echo.
echo Bot kapandi. Log icin gridbot.log dosyasina bakin.
pause
endlocal
