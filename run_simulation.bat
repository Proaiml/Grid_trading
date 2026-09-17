@echo off
title Grid Trading Bot - Strategy Simulator
cls
echo ======================================================================
echo                Grid Trading Bot - Strategy Simulator
echo                    Strategy by Ilhan Kocaslan
echo ======================================================================
echo.

py -3.11 simulation.py
if %errorlevel% neq 0 (
    python simulation.py
)

pause
