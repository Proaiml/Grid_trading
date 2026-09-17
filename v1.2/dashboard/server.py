from __future__ import annotations

import json
import math
import os
import random
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
V12_DIR = BASE_DIR.parent
CONFIG_PATH = V12_DIR / "config.json"
MAIN_PY_PATH = V12_DIR / "main.py"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="Grid Trading Bot v1.2 Pro Dashboard",
    description="Tek ekranlı kontrol paneli, kazanç simülatörü ve .BAT başlatıcı üreticisi",
    version="1.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Modeller ---

class ConfigUpdateRequest(BaseModel):
    bot_name: Optional[str] = "GridBot_v1_3_Full"
    mode: str = Field(..., description="paper, testnet veya live")
    api_key: Optional[str] = ""
    api_secret: Optional[str] = ""
    live_trading_confirmation: Optional[str] = ""
    symbol: str
    price_low: str
    price_high: str
    grid_number: int
    total_quote_budget: str
    poll_interval_seconds: Optional[float] = 0.5
    restart_recovery_policy: Optional[str] = "sell_stale_only"
    log_file: Optional[str] = "gridbot.log"
    instance_lock_port: Optional[int] = 47821


class SimulationRequest(BaseModel):
    symbol: Optional[str] = "MATICUSDT"
    price_low: float = Field(..., gt=0)
    price_high: float = Field(..., gt=0)
    grid_number: int = Field(..., ge=1)
    total_quote_budget: float = Field(..., gt=0)
    scenario: str = Field(default="sideways", description="sideways, bullish, bearish, volatile")
    steps: int = Field(default=150, ge=30, le=500)
    volatility: Optional[float] = Field(default=1.0, ge=0.2, le=3.0)


class BatGenerateRequest(BaseModel):
    custom_name: Optional[str] = "start_custom_bot.bat"
    python_cmd: Optional[str] = "python"
    save_to_disk: Optional[bool] = True


# --- Yardımcı Fonksiyonlar ---

def read_config_dict() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise HTTPException(status_code=404, detail="config.json bulunamadı.")
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"config.json okunamadı: {exc}")


def write_config_atomic(data: Dict[str, Any]) -> None:
    tmp = CONFIG_PATH.with_name(CONFIG_PATH.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, CONFIG_PATH)


# --- Endpoint'ler ---

@app.get("/")
async def get_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="index.html bulunamadı.")
    return FileResponse(index_file)


@app.get("/api/config")
async def get_config():
    """Mevcut config.json dosyasını okur."""
    cfg = read_config_dict()
    return JSONResponse(cfg)


@app.post("/api/config")
async def update_config(req: ConfigUpdateRequest):
    """Arayüzden gelen yeni yapılandırmayı doğrular ve kaydeder."""
    cfg = read_config_dict()

    mode = req.mode.lower().strip()
    if mode not in {"paper", "testnet", "live"}:
        raise HTTPException(status_code=400, detail="Mod yalnızca 'paper', 'testnet' veya 'live' olabilir.")

    symbol = req.symbol.strip().upper()
    if not symbol or not symbol.isalnum():
        raise HTTPException(status_code=400, detail="Geçersiz sembol formatı.")

    try:
        low = float(req.price_low)
        high = float(req.price_high)
        budget = float(req.total_quote_budget)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fiyat ve bakiye alanları sayısal olmalıdır.")

    if low <= 0:
        raise HTTPException(status_code=400, detail="Alt fiyat (price_low) 0'dan büyük olmalıdır.")
    if high <= low:
        raise HTTPException(status_code=400, detail="Üst fiyat (price_high), alt fiyattan büyük olmalıdır.")
    if req.grid_number < 1:
        raise HTTPException(status_code=400, detail="Grid sayısı en az 1 olmalıdır.")
    if budget <= 0:
        raise HTTPException(status_code=400, detail="Toplam bütçe 0'dan büyük olmalıdır.")

    cfg["mode"] = mode
    cfg["symbol"] = symbol
    cfg["price_low"] = str(req.price_low)
    cfg["price_high"] = str(req.price_high)
    cfg["grid_number"] = int(req.grid_number)
    cfg["total_quote_budget"] = str(req.total_quote_budget)

    if req.api_key is not None:
        cfg["api_key"] = req.api_key
    if req.api_secret is not None:
        cfg["api_secret"] = req.api_secret
    if req.live_trading_confirmation is not None:
        cfg["live_trading_confirmation"] = req.live_trading_confirmation

    if req.poll_interval_seconds:
        cfg["poll_interval_seconds"] = float(req.poll_interval_seconds)
    if req.restart_recovery_policy:
        cfg["restart_recovery_policy"] = req.restart_recovery_policy

    write_config_atomic(cfg)
    return JSONResponse({"status": "success", "message": "config.json başarıyla güncellendi.", "config": cfg})


@app.post("/api/simulate")
async def run_simulation(sim: SimulationRequest):
    """
    Kullanıcının belirlediği parametrelerle v1.2 durum makinesini birebir simüle eder.
    Sektör sayısı = Grid_Number + 1
    Adım = (High - Low) / Sektör Sayısı
    Düşüşte $ -> A (Alış), Yükselişte A -> $ (Satış)
    """
    low = sim.price_low
    high = sim.price_high
    if high <= low:
        raise HTTPException(status_code=400, detail="Üst fiyat alt fiyattan büyük olmalıdır.")

    grid_number = sim.grid_number
    sector_count = grid_number + 1
    step_size = (high - low) / sector_count
    total_budget = sim.total_quote_budget
    sector_budget = total_budget / sector_count

    # Sektör sınırları
    sectors_info = []
    for rank in range(1, sector_count + 1):
        s_low = low + step_size * (rank - 1)
        s_high = high if rank == sector_count else s_low + step_size
        sectors_info.append({
            "rank": rank,
            "name": f"sector{rank}",
            "low": round(s_low, 4),
            "high": round(s_high, 4),
            "mid": round((s_low + s_high) / 2, 4)
        })

    def get_rank(price: float) -> int:
        if price < low:
            return 0  # dead_zone
        if price >= high:
            return sector_count + 1  # higher_zone
        idx = int((price - low) // step_size) + 1
        return max(1, min(idx, sector_count))

    # Fiyat patikası üretimi (Senaryoya göre)
    random.seed(42)  # Tekrarlanabilir simülasyon başlangıcı
    prices: List[float] = []
    mid_price = (low + high) / 2
    base_vol = (step_size * 0.45) * sim.volatility

    for i in range(sim.steps):
        t = i / float(sim.steps)
        if sim.scenario == "sideways":
            drift = math.sin(t * 8 * math.pi) * (step_size * (sector_count * 0.35))
            noise = random.gauss(0, base_vol)
            p = mid_price + drift + noise
        elif sim.scenario == "bullish":
            drift = (t * (high - low) * 0.7) - ((high - low) * 0.25)
            wave = math.sin(t * 6 * math.pi) * (step_size * 0.9)
            noise = random.gauss(0, base_vol)
            p = low + (step_size * 1.5) + drift + wave + noise
        elif sim.scenario == "bearish":
            drift = - (t * (high - low) * 0.7) + ((high - low) * 0.25)
            wave = math.sin(t * 6 * math.pi) * (step_size * 0.9)
            noise = random.gauss(0, base_vol)
            p = high - (step_size * 1.5) + drift + wave + noise
        elif sim.scenario == "volatile":
            wave = math.sin(t * 12 * math.pi) * (step_size * (sector_count * 0.42))
            noise = random.gauss(0, base_vol * 1.6)
            p = mid_price + wave + noise
        else:
            p = mid_price + random.gauss(0, base_vol)

        p = max(low * 0.96, min(high * 1.04, p))
        prices.append(round(p, 4))

    # Durum makinesi simülasyonu
    states = {r: "$" for r in range(1, sector_count + 1)}
    open_positions: Dict[int, Dict[str, float]] = {}  # rank -> {qty, cost, buy_price}
    trades: List[Dict[str, Any]] = []

    cash_balance = total_budget
    realized_pnl = 0.0
    equity_curve: List[float] = []
    profit_curve: List[float] = []

    prev_rank = get_rank(prices[0])

    for step_idx, price in enumerate(prices):
        cur_rank = get_rank(price)

        if cur_rank != prev_rank:
            if prev_rank not in {0, sector_count + 1}:
                if cur_rank < prev_rank:
                    for r in range(prev_rank, cur_rank, -1):
                        if 1 <= r <= sector_count:
                            if states[r] == "$":
                                buy_cost = min(sector_budget, cash_balance)
                                if buy_cost > 0.5:
                                    qty = buy_cost / price
                                    cash_balance -= buy_cost
                                    states[r] = "A"
                                    open_positions[r] = {"qty": qty, "cost": buy_cost, "buy_price": price}
                                    trades.append({
                                        "step": step_idx,
                                        "type": "BUY",
                                        "sector": f"sector{r}",
                                        "price": price,
                                        "qty": round(qty, 6),
                                        "cost": round(buy_cost, 2),
                                        "profit": 0.0,
                                        "pnl_pct": 0.0,
                                        "cash_left": round(cash_balance, 2)
                                    })
                elif cur_rank > prev_rank:
                    for r in range(prev_rank, cur_rank):
                        if 1 <= r <= sector_count:
                            if states[r] == "A" and r in open_positions:
                                pos = open_positions.pop(r)
                                revenue = pos["qty"] * price
                                profit = revenue - pos["cost"]
                                pnl_pct = (profit / pos["cost"]) * 100 if pos["cost"] > 0 else 0
                                cash_balance += revenue
                                realized_pnl += profit
                                states[r] = "$"
                                trades.append({
                                    "step": step_idx,
                                    "type": "SELL",
                                    "sector": f"sector{r}",
                                    "price": price,
                                    "qty": round(pos["qty"], 6),
                                    "cost": round(pos["cost"], 2),
                                    "profit": round(profit, 3),
                                    "pnl_pct": round(pnl_pct, 2),
                                    "cash_left": round(cash_balance, 2)
                                })

            prev_rank = cur_rank

        open_asset_value = sum(pos["qty"] * price for pos in open_positions.values())
        total_equity = cash_balance + open_asset_value
        equity_curve.append(round(total_equity, 2))
        profit_curve.append(round(realized_pnl, 3))

    buy_trades = [t for t in trades if t["type"] == "BUY"]
    sell_trades = [t for t in trades if t["type"] == "SELL"]
    final_equity = equity_curve[-1] if equity_curve else total_budget
    open_asset_value = sum(pos["qty"] * prices[-1] for pos in open_positions.values())
    unrealized_pnl = final_equity - total_budget - realized_pnl

    peak = total_budget
    max_dd = 0.0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = ((peak - eq) / peak) * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    roi_pct = ((final_equity - total_budget) / total_budget) * 100

    return JSONResponse({
        "symbol": sim.symbol,
        "scenario": sim.scenario,
        "step_size": round(step_size, 4),
        "sector_count": sector_count,
        "sector_budget": round(sector_budget, 2),
        "prices": prices,
        "sectors_info": sectors_info,
        "trades": trades,
        "equity_curve": equity_curve,
        "profit_curve": profit_curve,
        "stats": {
            "total_trades": len(trades),
            "buy_count": len(buy_trades),
            "sell_count": len(sell_trades),
            "total_realized_profit": round(realized_pnl, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "final_equity": round(final_equity, 2),
            "roi_pct": round(roi_pct, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "win_rate": 100.0 if sell_trades else 0.0,
            "open_positions_count": len(open_positions),
            "open_positions_value": round(open_asset_value, 2),
            "cash_left": round(cash_balance, 2)
        }
    })


@app.post("/api/generate-bat")
async def generate_bat(req: BatGenerateRequest):
    """
    Kullanıcının yapılandırmasına uygun tek tıkla çalıştırılabilir .bat dosyasını üretir.
    İsteğe göre hem v1.2 dizinine kaydeder hem de içeriğini döndürür.
    """
    cfg = read_config_dict()
    bot_name = cfg.get("bot_name", "GridBot_v1_2")
    mode = cfg.get("mode", "paper").upper()
    symbol = cfg.get("symbol", "MATICUSDT")

    bat_content = f"""@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title {bot_name} [{mode}] - {symbol}

echo =======================================================
echo    Binance Grid Trading Bot - {bot_name}
echo    Mod: {mode}  ^|  Sembol: {symbol}
echo =======================================================
echo.

where py >nul 2>&1
if %errorlevel%==0 (
    set "PY=py -3"
) else (
    where python >nul 2>&1
    if %errorlevel% neq 0 (
        echo [HATA] Python bulunamadi. Lutfen Python 3.10+ kurun ve PATH'e ekleyin.
        pause
        exit /b 1
    )
    set "PY=python"
)

echo [1/3] Python versiyonu dogrulaniyor...
%PY% -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ gerekli'; print('Python surumu:', sys.version.split()[0])"
if %errorlevel% neq 0 (
    echo [HATA] Python 3.10 veya uzeri bir surum gereklidir.
    pause
    exit /b 1
)

echo [2/3] python-binance kutuphanesi kontrol ediliyor...
%PY% -c "import binance" >nul 2>&1
if %errorlevel% neq 0 (
    echo python-binance paketi eksik. Otomatik kuruluyor...
    %PY% -m pip install --upgrade python-binance
    if %errorlevel% neq 0 (
        echo [HATA] python-binance paketi yuklenemedi.
        pause
        exit /b 1
    )
)

echo [3/3] Botun dahili guvenlik testleri calistiriliyor...
%PY% main.py --self-test
if %errorlevel% neq 0 (
    echo [HATA] Guvenlik testleri (self-test) basarisiz oldu. Bot baslatilmadi.
    pause
    exit /b 1
)

echo.
echo =======================================================
echo    GRID BOT BASLATILIYOR [{mode}]...
echo    Durdurmak icin: CTRL+C
echo =======================================================
echo.
%PY% main.py

echo.
echo Bot sonlandi. Ayrintilar icin gridbot.log dosyasini inceleyin.
pause
endlocal
"""

    if req.save_to_disk:
        target_path = V12_DIR / req.custom_name
        with open(target_path, "w", encoding="utf-8") as fh:
            fh.write(bat_content)

    return JSONResponse({
        "status": "success",
        "filename": req.custom_name,
        "saved_to_disk": req.save_to_disk,
        "bat_content": bat_content,
        "message": f"'{req.custom_name}' basariyla hazirlandi."
    })


@app.post("/api/self-test")
async def run_bot_self_test():
    """Botun 20.480 durum patikalı dahili testini (main.py --self-test) çalıştırır."""
    try:
        proc = subprocess.run(
            [sys.executable, str(MAIN_PY_PATH), "--self-test"],
            cwd=str(V12_DIR),
            capture_output=True,
            text=True,
            timeout=30
        )
        output = proc.stdout.strip() if proc.stdout else proc.stderr.strip()
        success = (proc.returncode == 0)
        return JSONResponse({
            "success": success,
            "exit_code": proc.returncode,
            "output": output
        })
    except Exception as exc:
        return JSONResponse({
            "success": False,
            "exit_code": -1,
            "output": str(exc)
        }, status_code=500)


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def main():
    print("Grid Trading Bot v1.2 Web Dashboard Baslatiliyor...")
    print("Tarayicinizda acin: http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
