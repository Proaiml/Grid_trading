@echo off
title Grid Trading Bot - Live Binance Bot
cls
echo ======================================================================
echo                Grid Trading Bot - Live Execution
echo                    Written by Ilhan Kocaslan
echo ======================================================================
echo.
echo [!] UYARI: Canli emir gondermeden once main.py dosyasina Binance API
echo     anahtarlarinizi (privatekey, secretkey) girdiginizden emin olun.
echo.

py -3.11 main.py
if %errorlevel% neq 0 (
    python main.py
)

pause
