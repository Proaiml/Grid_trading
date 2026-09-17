from __future__ import annotations

"""
Grid Trading Bot v1.3 Full / Safety Edition

Original grid strategy concept: İlhan Koçaslan

Goals of this version
---------------------
1) Preserve the original per-sector "$ / A" hysteresis idea.
2) Fix sector-state lookup.
3) Persist state atomically so restart does not forget open sector positions.
4) Use deterministic clientOrderId values for pending orders and recover them
   after uncertain network failures instead of blindly duplicating orders.
5) Handle multi-grid jumps during normal runtime.
6) Normalize quantities with Decimal and Binance filters.
7) Start safely from dead_zone / higher_zone without crashing or trading.
8) Reconcile bot-held quantity with wallet balance before live/testnet trading.
9) Prevent two copies of the bot from running simultaneously.
10) Keep live trading disabled unless the config explicitly unlocks it.

Important safety property
-------------------------
The bot writes a pending order record to disk BEFORE sending a real order.
If the process dies after Binance accepts the order but before local state is
updated, the next start queries Binance by that clientOrderId and resolves the
same order before any new trading is allowed.

This code cannot guarantee profit and cannot eliminate exchange/network risk.
Always validate configuration in paper/testnet first.
"""

import argparse
import hashlib
import json
import logging
import os
import socket
import sys
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, InvalidOperation, getcontext
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

getcontext().prec = 40

VERSION = "1.3.0-full"
BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
LIVE_CONFIRMATION = "I_UNDERSTAND_LIVE_ORDERS"
TERMINAL_ORDER_STATUSES = {
    "FILLED",
    "CANCELED",
    "REJECTED",
    "EXPIRED",
    "EXPIRED_IN_MATCH",
}


class SafetyHalt(RuntimeError):
    """Raised when continuing could cause an unsafe or inconsistent trade."""


class ConfigError(ValueError):
    """Raised for invalid user configuration."""


def D(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ConfigError(f"Geçersiz Decimal değer: {value!r}") from exc


def decstr(value: Decimal) -> str:
    """Stable non-scientific Decimal string."""
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def now_ms() -> int:
    return int(time.time() * 1000)


def atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        value = json.load(fh)
    if not isinstance(value, dict):
        raise ConfigError(f"{path.name} JSON object olmalı.")
    return value


def resolve_relative(path_value: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


def setup_logging(config: Dict[str, Any]) -> logging.Logger:
    logger = logging.getLogger("gridbot")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(getattr(logging, str(config.get("console_log_level", "INFO")).upper(), logging.INFO))
    console.setFormatter(formatter)
    logger.addHandler(console)

    log_path = resolve_relative(str(config.get("log_file", "gridbot.log")))
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(getattr(logging, str(config.get("file_log_level", "INFO")).upper(), logging.INFO))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise ConfigError(f"config.json bulunamadı: {CONFIG_PATH}")
    cfg = load_json(CONFIG_PATH)

    required = [
        "mode",
        "symbol",
        "price_low",
        "price_high",
        "grid_number",
        "total_quote_budget",
    ]
    missing = [key for key in required if key not in cfg]
    if missing:
        raise ConfigError(f"Eksik config alanları: {', '.join(missing)}")

    mode = str(cfg["mode"]).lower().strip()
    if mode not in {"paper", "testnet", "live"}:
        raise ConfigError("mode yalnızca paper, testnet veya live olabilir.")
    cfg["mode"] = mode

    symbol = str(cfg["symbol"]).strip().upper()
    if not symbol or not symbol.isalnum():
        raise ConfigError("symbol geçersiz.")
    cfg["symbol"] = symbol

    low = D(cfg["price_low"])
    high = D(cfg["price_high"])
    budget = D(cfg["total_quote_budget"])
    grid_number = int(cfg["grid_number"])

    if low <= 0:
        raise ConfigError("price_low > 0 olmalı.")
    if high <= low:
        raise ConfigError("price_high, price_low değerinden büyük olmalı.")
    if grid_number < 1:
        raise ConfigError("grid_number en az 1 olmalı.")
    if budget <= 0:
        raise ConfigError("total_quote_budget > 0 olmalı.")

    poll = float(cfg.get("poll_interval_seconds", 0.5))
    if poll < 0.1:
        raise ConfigError("poll_interval_seconds en az 0.1 olmalı.")

    max_orders = int(cfg.get("max_orders_per_transition", 10))
    if max_orders < 1:
        raise ConfigError("max_orders_per_transition en az 1 olmalı.")

    recovery_policy = str(cfg.get("restart_recovery_policy", "sell_stale_only")).lower().strip()
    if recovery_policy not in {"sell_stale_only", "anchor_only"}:
        raise ConfigError("restart_recovery_policy: sell_stale_only veya anchor_only olmalı.")
    cfg["restart_recovery_policy"] = recovery_policy

    if mode == "live" and str(cfg.get("live_trading_confirmation", "")) != LIVE_CONFIRMATION:
        raise ConfigError(
            "LIVE mod kilitli. Gerçek emir için config içindeki "
            f"live_trading_confirmation alanı tam olarak {LIVE_CONFIRMATION} olmalı."
        )

    return cfg


def config_fingerprint(config: Dict[str, Any]) -> str:
    critical = {
        "mode": str(config.get("mode", "paper")).lower(),
        "symbol": config["symbol"],
        "price_low": decstr(D(config["price_low"])),
        "price_high": decstr(D(config["price_high"])),
        "grid_number": int(config["grid_number"]),
        "total_quote_budget": decstr(D(config["total_quote_budget"])),
    }
    raw = json.dumps(critical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


@dataclass(frozen=True)
class GridSpec:
    low: Decimal
    high: Decimal
    sector_count: int
    step: Decimal

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "GridSpec":
        # Original code semantics: Grid_Area = Grid_Number + 1
        count = int(config["grid_number"]) + 1
        low = D(config["price_low"])
        high = D(config["price_high"])
        return cls(low=low, high=high, sector_count=count, step=(high - low) / D(count))

    def sector_name(self, rank: int) -> str:
        if rank == 0:
            return "dead_zone"
        if rank == self.sector_count + 1:
            return "higher_zone"
        if 1 <= rank <= self.sector_count:
            return f"sector{rank}"
        raise ValueError(f"Geçersiz rank: {rank}")

    def rank(self, sector: str) -> int:
        if sector == "dead_zone":
            return 0
        if sector == "higher_zone":
            return self.sector_count + 1
        if sector.startswith("sector"):
            idx = int(sector[6:])
            if 1 <= idx <= self.sector_count:
                return idx
        raise ValueError(f"Geçersiz sektör: {sector}")

    def bounds(self, rank: int) -> Tuple[Decimal, Decimal]:
        if not (1 <= rank <= self.sector_count):
            raise ValueError("Sadece normal sektörlerin bounds değeri vardır.")
        lo = self.low + self.step * D(rank - 1)
        hi = self.high if rank == self.sector_count else lo + self.step
        return lo, hi

    def find_sector(self, price: Decimal) -> str:
        if price < self.low:
            return "dead_zone"
        if price >= self.high:
            return "higher_zone"
        # Decimal floor division gives the zero-based sector index.
        idx = int((price - self.low) // self.step) + 1
        if idx < 1:
            idx = 1
        if idx > self.sector_count:
            idx = self.sector_count
        return f"sector{idx}"

    def crossed_action_sectors(self, old_sector: str, new_sector: str) -> List[str]:
        """
        Return sectors whose hysteresis boundary was crossed from old -> new.

        Examples for 5 sectors:
          sector5 -> sector2   => [sector5, sector4, sector3]  (BUY candidates)
          sector2 -> sector5   => [sector2, sector3, sector4]  (SELL candidates)
          sector1 -> dead_zone => [sector1]
          sector5 -> higher    => [sector5]

        If the previous observed point is already outside the configured grid,
        we anchor on re-entry and do not infer missed trades.
        """
        old_rank = self.rank(old_sector)
        new_rank = self.rank(new_sector)

        if old_rank in {0, self.sector_count + 1}:
            return []
        if old_rank == new_rank:
            return []

        result: List[str] = []
        if new_rank < old_rank:
            for rank in range(old_rank, new_rank, -1):
                if 1 <= rank <= self.sector_count:
                    result.append(self.sector_name(rank))
        else:
            for rank in range(old_rank, new_rank):
                if 1 <= rank <= self.sector_count:
                    result.append(self.sector_name(rank))
        return result


def floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        return value
    if value <= 0:
        return Decimal("0")
    units = (value / step).to_integral_value(rounding=ROUND_DOWN)
    return units * step


def floor_to_decimal_places(value: Decimal, places: int) -> Decimal:
    if places < 0:
        return value
    quantum = Decimal(1).scaleb(-places)
    return value.quantize(quantum, rounding=ROUND_DOWN)


def make_initial_state(config: Dict[str, Any], grid: GridSpec) -> Dict[str, Any]:
    sectors: Dict[str, Any] = {}
    for rank in range(1, grid.sector_count + 1):
        lo, hi = grid.bounds(rank)
        sectors[f"sector{rank}"] = {
            "low": decstr(lo),
            "high": decstr(hi),
            "state": "$",
            "qty": "0",
            "cost_quote": "0",
            "avg_entry_price": "0",
            "last_buy_client_order_id": None,
            "last_sell_client_order_id": None,
        }

    return {
        "schema_version": 1,
        "bot_version": VERSION,
        "config_fingerprint": config_fingerprint(config),
        "symbol": config["symbol"],
        "previous_sector": None,
        "sectors": sectors,
        "pending_order": None,
        "counters": {
            "buy_orders": 0,
            "sell_orders": 0,
            "completed_round_trips": 0,
            "realized_quote_pnl_before_external_fees": "0",
        },
        "external_commissions": {},
        "created_at_ms": now_ms(),
        "updated_at_ms": now_ms(),
    }


def validate_state(state: Dict[str, Any], config: Dict[str, Any], grid: GridSpec) -> None:
    if state.get("config_fingerprint") != config_fingerprint(config):
        raise SafetyHalt(
            "runtime_state.json mevcut fakat grid/symbol/bütçe config'i değişmiş. "
            "Aktif state varken otomatik reset güvenli değildir. Bot durduruldu."
        )
    if state.get("symbol") != config["symbol"]:
        raise SafetyHalt("State symbol ile config symbol uyuşmuyor.")

    sectors = state.get("sectors")
    if not isinstance(sectors, dict):
        raise SafetyHalt("State sectors alanı bozuk.")

    expected_names = {f"sector{i}" for i in range(1, grid.sector_count + 1)}
    if set(sectors) != expected_names:
        raise SafetyHalt("State sektör yapısı config ile uyuşmuyor.")

    for name, rec in sectors.items():
        if rec.get("state") not in {"$", "A"}:
            raise SafetyHalt(f"{name} state geçersiz: {rec.get('state')}")
        qty = D(rec.get("qty", "0"))
        cost = D(rec.get("cost_quote", "0"))
        if qty < 0 or cost < 0:
            raise SafetyHalt(f"{name} negatif qty/cost içeriyor.")
        if rec.get("state") == "A" and qty <= 0:
            raise SafetyHalt(f"{name}=A fakat qty <= 0.")


def save_state(path: Path, state: Dict[str, Any]) -> None:
    state["updated_at_ms"] = now_ms()
    atomic_write_json(path, state)


class SingleInstanceLock:
    """Hold a localhost TCP port for process lifetime to block duplicate bot instances."""

    def __init__(self, port: int):
        self.port = int(port)
        self.sock: Optional[socket.socket] = None

    def acquire(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        try:
            sock.bind(("127.0.0.1", self.port))
            sock.listen(1)
        except OSError as exc:
            sock.close()
            raise SafetyHalt(
                f"Başka bir bot kopyası çalışıyor olabilir (lock port {self.port} kullanılamıyor)."
            ) from exc
        self.sock = sock

    def close(self) -> None:
        if self.sock is not None:
            self.sock.close()
            self.sock = None


class GridBot:
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.grid = GridSpec.from_config(config)
        self.state_path = resolve_relative(str(config.get("state_file", "runtime_state.json")))
        self.mode = config["mode"]
        self.symbol = config["symbol"]
        self.total_quote_budget = D(config["total_quote_budget"])
        self.sector_quote_amount = self.total_quote_budget / D(self.grid.sector_count)
        self.client = None
        self.symbol_info: Dict[str, Any] = {}
        self.base_asset = ""
        self.quote_asset = ""
        self.quote_asset_precision = 8
        self.filters: Dict[str, Dict[str, Any]] = {}
        self.state = self._load_or_create_state()

    def _load_or_create_state(self) -> Dict[str, Any]:
        if self.state_path.exists():
            state = load_json(self.state_path)
            validate_state(state, self.config, self.grid)
            return state
        state = make_initial_state(self.config, self.grid)
        save_state(self.state_path, state)
        return state

    # ---------- Binance connection / metadata ----------

    def connect(self) -> None:
        try:
            from binance.client import Client
        except ImportError as exc:
            raise ConfigError("python-binance kurulu değil. start_bot.bat ile başlatın.") from exc

        api_key = os.environ.get("BINANCE_API_KEY", str(self.config.get("api_key", ""))).strip()
        api_secret = os.environ.get("BINANCE_API_SECRET", str(self.config.get("api_secret", ""))).strip()

        if self.mode in {"testnet", "live"}:
            bad_values = {"", "PUT_API_KEY_HERE", "PUT_API_SECRET_HERE"}
            if api_key in bad_values or api_secret in bad_values:
                raise ConfigError(f"{self.mode} modu için API key/secret gerekli.")

        # Paper mode uses public mainnet market data only.
        use_testnet = self.mode == "testnet"
        self.client = Client(api_key or None, api_secret or None, testnet=use_testnet)

        self._load_symbol_info()
        self._validate_order_budget_against_filters()

        if self.mode in {"testnet", "live"}:
            # Harmless authenticated read verifies API credentials and account access.
            self.client.get_account(recvWindow=int(self.config.get("recv_window_ms", 10000)))

    def _retry_read(self, func, description: str):
        delay = float(self.config.get("request_retry_delay_seconds", 1.0))
        last_exc: Optional[BaseException] = None
        for attempt in range(1, 6):
            try:
                return func()
            except KeyboardInterrupt:
                raise
            except Exception as exc:  # read-only operation; safe to retry
                last_exc = exc
                self.logger.warning("%s başarısız (%s/5): %s", description, attempt, exc)
                time.sleep(delay)
        raise SafetyHalt(f"{description} 5 denemede başarısız: {last_exc}")

    def _load_symbol_info(self) -> None:
        assert self.client is not None
        info = self._retry_read(lambda: self.client.get_symbol_info(self.symbol), "Symbol info")
        if not info:
            raise ConfigError(f"Binance symbol bulunamadı: {self.symbol}")
        if str(info.get("status", "")).upper() != "TRADING":
            raise SafetyHalt(f"{self.symbol} status=TRADING değil: {info.get('status')}")

        self.symbol_info = info
        self.base_asset = str(info.get("baseAsset", ""))
        self.quote_asset = str(info.get("quoteAsset", ""))
        self.quote_asset_precision = int(info.get("quoteAssetPrecision", 8))
        self.filters = {f.get("filterType"): f for f in info.get("filters", []) if f.get("filterType")}

        if "LOT_SIZE" not in self.filters:
            raise SafetyHalt("LOT_SIZE filtresi bulunamadı.")

        self.logger.info(
            "Symbol hazır: %s | base=%s | quote=%s | mode=%s",
            self.symbol,
            self.base_asset,
            self.quote_asset,
            self.mode,
        )

    def _min_notional(self) -> Decimal:
        values: List[Decimal] = []
        min_notional = self.filters.get("MIN_NOTIONAL")
        if min_notional and bool(min_notional.get("applyToMarket", True)):
            values.append(D(min_notional.get("minNotional", "0")))
        notional = self.filters.get("NOTIONAL")
        if notional and bool(notional.get("applyMinToMarket", True)):
            values.append(D(notional.get("minNotional", "0")))
        return max(values) if values else Decimal("0")

    def _max_notional(self) -> Optional[Decimal]:
        notional = self.filters.get("NOTIONAL")
        if notional and bool(notional.get("applyMaxToMarket", False)):
            value = D(notional.get("maxNotional", "0"))
            if value > 0:
                return value
        return None

    def _validate_order_budget_against_filters(self) -> None:
        quote_amount = floor_to_decimal_places(self.sector_quote_amount, self.quote_asset_precision)
        minimum = self._min_notional()
        maximum = self._max_notional()
        if minimum > 0 and quote_amount < minimum:
            raise ConfigError(
                f"Sector bütçesi {quote_amount} {self.quote_asset}, Binance minNotional {minimum} altında."
            )
        if maximum is not None and quote_amount > maximum:
            raise ConfigError(
                f"Sector bütçesi {quote_amount} {self.quote_asset}, Binance maxNotional {maximum} üstünde."
            )

    # ---------- Market / filter helpers ----------

    def current_price(self) -> Decimal:
        assert self.client is not None
        data = self._retry_read(
            lambda: self.client.get_symbol_ticker(symbol=self.symbol),
            "Anlık fiyat",
        )
        return D(data["price"])

    def current_sector(self) -> Tuple[Decimal, str]:
        price = self.current_price()
        return price, self.grid.find_sector(price)

    def normalize_market_sell_qty(self, qty: Decimal) -> Decimal:
        if qty <= 0:
            return Decimal("0")

        lot = self.filters["LOT_SIZE"]
        result = floor_to_step(qty, D(lot.get("stepSize", "0")))

        market_lot = self.filters.get("MARKET_LOT_SIZE")
        if market_lot:
            market_step = D(market_lot.get("stepSize", "0"))
            if market_step > 0:
                result = floor_to_step(result, market_step)

        if result <= 0:
            return Decimal("0")

        min_qty = D(lot.get("minQty", "0"))
        max_qty = D(lot.get("maxQty", "0"))
        if min_qty > 0 and result < min_qty:
            return Decimal("0")
        if max_qty > 0 and result > max_qty:
            result = floor_to_step(max_qty, D(lot.get("stepSize", "0")))

        if market_lot:
            market_min = D(market_lot.get("minQty", "0"))
            market_max = D(market_lot.get("maxQty", "0"))
            if market_min > 0 and result < market_min:
                return Decimal("0")
            if market_max > 0 and result > market_max:
                result = floor_to_step(market_max, D(market_lot.get("stepSize", "0")))

        return result

    def _wallet_balance(self, asset: str) -> Tuple[Decimal, Decimal]:
        assert self.client is not None
        data = self._retry_read(
            lambda: self.client.get_asset_balance(asset=asset),
            f"{asset} balance",
        )
        if not data:
            return Decimal("0"), Decimal("0")
        return D(data.get("free", "0")), D(data.get("locked", "0"))

    def reconcile_wallet(self) -> None:
        if self.mode == "paper":
            return
        expected = sum(
            D(rec.get("qty", "0"))
            for rec in self.state["sectors"].values()
            if rec.get("state") == "A"
        )
        free, locked = self._wallet_balance(self.base_asset)
        actual = free + locked
        lot_step = D(self.filters["LOT_SIZE"].get("stepSize", "0"))
        tolerance = max(lot_step, Decimal("0.000000000001"))

        if actual + tolerance < expected:
            raise SafetyHalt(
                f"Wallet reconciliation FAILED: bot {expected} {self.base_asset} bekliyor, "
                f"hesapta {actual} var. Otomatik satış güvenli değil."
            )
        if actual > expected + tolerance:
            self.logger.warning(
                "Wallet'ta bot state'inden fazla %s var: actual=%s, bot_expected=%s. "
                "Fazlalık bot tarafından satılmayacak.",
                self.base_asset,
                actual,
                expected,
            )
        else:
            self.logger.info("Wallet reconciliation OK: expected=%s actual=%s", expected, actual)

    # ---------- Order identity / recovery ----------

    def _new_client_order_id(self, side: str, sector: str) -> str:
        rank = self.grid.rank(sector)
        side_char = "B" if side == "BUY" else "S"
        return f"GB13{side_char}{rank:02d}{uuid.uuid4().hex[:22]}"[:36]

    def _prepare_pending(
        self,
        side: str,
        sector: str,
        client_order_id: str,
        requested_quote: Optional[Decimal] = None,
        requested_qty: Optional[Decimal] = None,
        paper_price: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        if self.state.get("pending_order") is not None:
            raise SafetyHalt("Yeni emir hazırlanırken çözülmemiş pending_order bulundu.")

        pending = {
            "side": side,
            "sector": sector,
            "client_order_id": client_order_id,
            "requested_quote": decstr(requested_quote) if requested_quote is not None else None,
            "requested_qty": decstr(requested_qty) if requested_qty is not None else None,
            "paper_price": decstr(paper_price) if paper_price is not None else None,
            "created_at_ms": now_ms(),
        }
        self.state["pending_order"] = pending
        save_state(self.state_path, self.state)
        return pending

    def _query_order_by_client_id_once(self, client_order_id: str) -> Optional[Dict[str, Any]]:
        assert self.client is not None
        try:
            return self.client.get_order(
                symbol=self.symbol,
                origClientOrderId=client_order_id,
                recvWindow=int(self.config.get("recv_window_ms", 10000)),
            )
        except Exception as exc:
            # Binance uses an error for unknown order. We intentionally do not
            # infer acceptance from the exception; caller decides whether to retry.
            self.logger.debug("Order query %s bulunamadı/başarısız: %s", client_order_id, exc)
            return None

    def _wait_for_terminal(self, order: Dict[str, Any], client_order_id: str) -> Dict[str, Any]:
        attempts = int(self.config.get("order_query_attempts", 8))
        delay = float(self.config.get("order_query_delay_seconds", 1.0))

        current = order
        for _ in range(attempts):
            status = str(current.get("status", "")).upper()
            if status in TERMINAL_ORDER_STATUSES:
                return current
            time.sleep(delay)
            queried = self._query_order_by_client_id_once(client_order_id)
            if queried is not None:
                current = queried

        raise SafetyHalt(
            f"Emir terminal duruma gelmedi: clientOrderId={client_order_id}, status={current.get('status')}"
        )

    def _submit_real_pending(self, pending: Dict[str, Any]) -> Dict[str, Any]:
        assert self.client is not None
        side = pending["side"]
        client_id = pending["client_order_id"]
        attempts = int(self.config.get("order_submit_attempts", 3))
        delay = float(self.config.get("request_retry_delay_seconds", 1.0))
        last_exc: Optional[BaseException] = None

        # First query is essential for restart recovery: perhaps this exact order
        # was accepted before the previous process died.
        existing = self._query_order_by_client_id_once(client_id)
        if existing is not None:
            self.logger.warning("Pending emir Binance'te bulundu, yeniden gönderilmiyor: %s", client_id)
            return self._wait_for_terminal(existing, client_id)

        for attempt in range(1, attempts + 1):
            try:
                params: Dict[str, Any] = {
                    "symbol": self.symbol,
                    "side": side,
                    "type": "MARKET",
                    "newClientOrderId": client_id,
                    "newOrderRespType": "FULL",
                    "recvWindow": int(self.config.get("recv_window_ms", 10000)),
                }
                if side == "BUY":
                    params["quoteOrderQty"] = pending["requested_quote"]
                else:
                    params["quantity"] = pending["requested_qty"]

                order = self.client.create_order(**params)
                return self._wait_for_terminal(order, client_id)

            except KeyboardInterrupt:
                raise
            except Exception as exc:
                last_exc = exc
                self.logger.warning(
                    "Order submit belirsiz/hatalı (%s/%s) clientId=%s: %s",
                    attempt,
                    attempts,
                    client_id,
                    exc,
                )

                # Never issue a new identity after an uncertain response.
                # Query the SAME clientOrderId; if found, accept that order.
                for _ in range(int(self.config.get("order_query_attempts", 8))):
                    queried = self._query_order_by_client_id_once(client_id)
                    if queried is not None:
                        return self._wait_for_terminal(queried, client_id)
                    time.sleep(float(self.config.get("order_query_delay_seconds", 1.0)))

                # Same clientOrderId is reused on retry. If Binance had accepted
                # the first request, a duplicate-ID response is followed by query.
                time.sleep(delay)

        raise SafetyHalt(
            f"Emir sonucu doğrulanamadı; pending state korunuyor. clientOrderId={client_id}. "
            f"Son hata: {last_exc}"
        )

    def _paper_order(self, pending: Dict[str, Any]) -> Dict[str, Any]:
        price = D(pending["paper_price"])
        if price <= 0:
            raise SafetyHalt("Paper order price geçersiz.")

        if pending["side"] == "BUY":
            quote = D(pending["requested_quote"])
            raw_qty = quote / price
            qty = self.normalize_market_sell_qty(raw_qty)
            if qty <= 0:
                raise SafetyHalt("Paper BUY sonucu satılabilir quantity üretmedi.")
            quote_used = qty * price
        else:
            qty = D(pending["requested_qty"])
            quote_used = qty * price

        return {
            "symbol": self.symbol,
            "orderId": int(time.time() * 1_000_000),
            "clientOrderId": pending["client_order_id"],
            "status": "FILLED",
            "side": pending["side"],
            "type": "MARKET",
            "executedQty": decstr(qty),
            "cummulativeQuoteQty": decstr(quote_used),
            "fills": [],
        }

    def _submit_pending(self, pending: Dict[str, Any]) -> Dict[str, Any]:
        if self.mode == "paper":
            return self._paper_order(pending)
        return self._submit_real_pending(pending)

    def _order_commissions(self, order: Dict[str, Any]) -> Tuple[Decimal, Decimal, Dict[str, Decimal]]:
        """Return base commission, quote commission, external commissions."""
        base_fee = Decimal("0")
        quote_fee = Decimal("0")
        external: Dict[str, Decimal] = {}

        fills = order.get("fills") if isinstance(order.get("fills"), list) else None

        # Query trades if a recovered order has no fills.
        if not fills and self.mode in {"testnet", "live"} and self.client is not None and order.get("orderId") is not None:
            try:
                trades = self.client.get_my_trades(
                    symbol=self.symbol,
                    orderId=order["orderId"],
                    recvWindow=int(self.config.get("recv_window_ms", 10000)),
                )
                fills = [
                    {
                        "commission": trade.get("commission", "0"),
                        "commissionAsset": trade.get("commissionAsset"),
                    }
                    for trade in trades
                    if int(trade.get("orderId", -1)) == int(order["orderId"])
                ]
            except Exception as exc:
                self.logger.warning("Komisyon trade detayları okunamadı; gross değer kullanılacak: %s", exc)
                fills = []

        for fill in fills or []:
            fee = D(fill.get("commission", "0"))
            asset = str(fill.get("commissionAsset") or "")
            if fee <= 0 or not asset:
                continue
            if asset == self.base_asset:
                base_fee += fee
            elif asset == self.quote_asset:
                quote_fee += fee
            else:
                external[asset] = external.get(asset, Decimal("0")) + fee

        return base_fee, quote_fee, external

    def _record_external_fees(self, fees: Dict[str, Decimal]) -> None:
        store = self.state.setdefault("external_commissions", {})
        for asset, fee in fees.items():
            store[asset] = decstr(D(store.get(asset, "0")) + fee)

    def _commit_buy(self, pending: Dict[str, Any], order: Dict[str, Any]) -> None:
        sector = pending["sector"]
        rec = self.state["sectors"][sector]
        if rec["state"] != "$":
            raise SafetyHalt(f"BUY commit sırasında {sector} state $ değil.")

        executed = D(order.get("executedQty", "0"))
        cumulative_quote = D(order.get("cummulativeQuoteQty", "0"))
        base_fee, quote_fee, external = self._order_commissions(order)
        net_base = executed - base_fee
        sellable = self.normalize_market_sell_qty(net_base)

        if executed <= 0 or sellable <= 0:
            # No usable fill: clear pending without changing sector state.
            self.logger.warning("BUY usable fill yok; sector değişmedi. order=%s", order)
            self.state["pending_order"] = None
            save_state(self.state_path, self.state)
            return

        quote_cost = cumulative_quote + quote_fee
        if quote_cost <= 0:
            quote_cost = D(pending["requested_quote"])

        rec["state"] = "A"
        rec["qty"] = decstr(sellable)
        rec["cost_quote"] = decstr(quote_cost)
        rec["avg_entry_price"] = decstr(quote_cost / sellable)
        rec["last_buy_client_order_id"] = pending["client_order_id"]
        self.state["counters"]["buy_orders"] += 1
        self._record_external_fees(external)
        self.state["pending_order"] = None
        save_state(self.state_path, self.state)

        dust = net_base - sellable
        self.logger.info(
            "BUY FILLED | %s | qty=%s %s | cost=%s %s | avg=%s | dust=%s",
            sector,
            sellable,
            self.base_asset,
            quote_cost,
            self.quote_asset,
            rec["avg_entry_price"],
            dust,
        )

    def _commit_sell(self, pending: Dict[str, Any], order: Dict[str, Any]) -> None:
        sector = pending["sector"]
        rec = self.state["sectors"][sector]
        if rec["state"] != "A":
            raise SafetyHalt(f"SELL commit sırasında {sector} state A değil.")

        before_qty = D(rec["qty"])
        before_cost = D(rec["cost_quote"])
        executed = D(order.get("executedQty", "0"))
        cumulative_quote = D(order.get("cummulativeQuoteQty", "0"))
        base_fee, quote_fee, external = self._order_commissions(order)

        if executed <= 0:
            self.logger.warning("SELL fill yok; sector A olarak korunuyor.")
            self.state["pending_order"] = None
            save_state(self.state_path, self.state)
            return

        base_consumed = executed + base_fee
        if base_consumed > before_qty:
            # Fee or exchange precision can make this microscopically larger.
            base_consumed = before_qty

        fraction = (base_consumed / before_qty) if before_qty > 0 else Decimal("1")
        if fraction > 1:
            fraction = Decimal("1")
        cost_basis_sold = before_cost * fraction
        quote_net = cumulative_quote - quote_fee
        realized = quote_net - cost_basis_sold

        remaining_qty = before_qty - base_consumed
        remaining_cost = before_cost - cost_basis_sold
        normalized_remaining = self.normalize_market_sell_qty(remaining_qty)

        counters = self.state["counters"]
        counters["sell_orders"] += 1
        counters["realized_quote_pnl_before_external_fees"] = decstr(
            D(counters["realized_quote_pnl_before_external_fees"]) + realized
        )
        self._record_external_fees(external)

        if normalized_remaining > 0:
            rec["qty"] = decstr(normalized_remaining)
            rec["cost_quote"] = decstr(max(remaining_cost, Decimal("0")))
            rec["avg_entry_price"] = (
                decstr(D(rec["cost_quote"]) / normalized_remaining)
                if D(rec["cost_quote"]) > 0
                else "0"
            )
            rec["state"] = "A"
            self.logger.warning(
                "SELL kısmi kaldı | %s | remaining=%s %s",
                sector,
                normalized_remaining,
                self.base_asset,
            )
        else:
            rec["state"] = "$"
            rec["qty"] = "0"
            rec["cost_quote"] = "0"
            rec["avg_entry_price"] = "0"
            counters["completed_round_trips"] += 1

        rec["last_sell_client_order_id"] = pending["client_order_id"]
        self.state["pending_order"] = None
        save_state(self.state_path, self.state)

        self.logger.info(
            "SELL FILLED | %s | executed=%s %s | received=%s %s | realized=%s %s",
            sector,
            executed,
            self.base_asset,
            quote_net,
            self.quote_asset,
            realized,
            self.quote_asset,
        )

    def resolve_pending_on_startup(self) -> None:
        pending = self.state.get("pending_order")
        if not pending:
            return

        self.logger.warning(
            "Başlangıçta pending order bulundu: %s %s clientId=%s",
            pending.get("side"),
            pending.get("sector"),
            pending.get("client_order_id"),
        )

        if self.mode == "paper":
            # Paper orders have no exchange truth. Recreate deterministic paper fill.
            order = self._paper_order(pending)
        else:
            assert self.client is not None
            order = None
            for _ in range(int(self.config.get("order_query_attempts", 8))):
                order = self._query_order_by_client_id_once(pending["client_order_id"])
                if order is not None:
                    break
                time.sleep(float(self.config.get("order_query_delay_seconds", 1.0)))
            if order is None:
                raise SafetyHalt(
                    "Pending order Binance'te doğrulanamadı. Güvenlik için yeni emir gönderilmiyor. "
                    f"clientOrderId={pending['client_order_id']}"
                )
            order = self._wait_for_terminal(order, pending["client_order_id"])

        if pending["side"] == "BUY":
            self._commit_buy(pending, order)
        elif pending["side"] == "SELL":
            self._commit_sell(pending, order)
        else:
            raise SafetyHalt(f"Pending side geçersiz: {pending.get('side')}")

    # ---------- Trading actions ----------

    def buy_sector(self, sector: str, market_price: Decimal) -> None:
        rec = self.state["sectors"][sector]
        if rec["state"] != "$":
            self.logger.debug("BUY skip: %s zaten A", sector)
            return

        quote_amount = floor_to_decimal_places(self.sector_quote_amount, self.quote_asset_precision)
        if quote_amount <= 0:
            raise SafetyHalt("BUY quote amount <= 0")

        if self.mode in {"testnet", "live"}:
            free_quote, _ = self._wallet_balance(self.quote_asset)
            if free_quote < quote_amount:
                raise SafetyHalt(
                    f"Yetersiz {self.quote_asset}: gerekli={quote_amount}, free={free_quote}"
                )

        client_id = self._new_client_order_id("BUY", sector)
        pending = self._prepare_pending(
            side="BUY",
            sector=sector,
            client_order_id=client_id,
            requested_quote=quote_amount,
            paper_price=market_price,
        )
        order = self._submit_pending(pending)
        self._commit_buy(pending, order)

    def sell_sector(self, sector: str, market_price: Decimal) -> None:
        rec = self.state["sectors"][sector]
        if rec["state"] != "A":
            self.logger.debug("SELL skip: %s zaten $", sector)
            return

        stored_qty = D(rec["qty"])
        qty = self.normalize_market_sell_qty(stored_qty)
        if qty <= 0:
            raise SafetyHalt(
                f"{sector}=A fakat quantity Binance market lot kurallarında satılamıyor: {stored_qty}"
            )

        if self.mode in {"testnet", "live"}:
            free_base, _ = self._wallet_balance(self.base_asset)
            if free_base < qty:
                raise SafetyHalt(
                    f"Yetersiz {self.base_asset} free balance: gerekli={qty}, free={free_base}"
                )

        client_id = self._new_client_order_id("SELL", sector)
        pending = self._prepare_pending(
            side="SELL",
            sector=sector,
            client_order_id=client_id,
            requested_qty=qty,
            paper_price=market_price,
        )
        order = self._submit_pending(pending)
        self._commit_sell(pending, order)

    def process_transition(self, old_sector: str, new_sector: str, price: Decimal) -> None:
        if old_sector == new_sector:
            return

        old_rank = self.grid.rank(old_sector)
        new_rank = self.grid.rank(new_sector)

        # Re-entry from outside zones: anchor only. This intentionally avoids
        # inventing unseen historical crossings.
        if old_rank in {0, self.grid.sector_count + 1}:
            self.logger.info("Dış bölgeden grid'e anchor: %s -> %s (emir yok)", old_sector, new_sector)
            return

        action_sectors = self.grid.crossed_action_sectors(old_sector, new_sector)
        if len(action_sectors) > int(self.config.get("max_orders_per_transition", 10)):
            raise SafetyHalt(
                f"Tek geçişte {len(action_sectors)} emir adayı oluştu; max_orders_per_transition aşıldı."
            )

        direction = "DOWN" if new_rank < old_rank else "UP"
        self.logger.info(
            "TRANSITION %s -> %s | direction=%s | crossed=%s | price=%s",
            old_sector,
            new_sector,
            direction,
            action_sectors,
            price,
        )

        for sector in action_sectors:
            if direction == "DOWN":
                self.buy_sector(sector, price)
            else:
                self.sell_sector(sector, price)

    # ---------- Startup recovery ----------

    def recover_stale_positions(self, current_sector: str, current_price: Decimal) -> None:
        policy = self.config.get("restart_recovery_policy", "sell_stale_only")
        if policy != "sell_stale_only":
            return

        current_rank = self.grid.rank(current_sector)
        if current_rank == 0:
            return

        # Conservative restart policy: only close A sectors whose upper boundary
        # is already below current price. Do NOT synthesize missed BUYs.
        stale: List[str] = []
        for rank in range(1, self.grid.sector_count + 1):
            name = f"sector{rank}"
            if self.state["sectors"][name]["state"] == "A" and current_rank > rank:
                stale.append(name)

        if stale:
            self.logger.warning("Restart stale SELL recovery: %s", stale)
        for sector in stale:
            self.sell_sector(sector, current_price)

    # ---------- Main runtime ----------

    def print_grid_summary(self) -> None:
        self.logger.info("Grid: low=%s high=%s sectors=%s step=%s", self.grid.low, self.grid.high, self.grid.sector_count, self.grid.step)
        self.logger.info("Sector quote allocation: %s", self.sector_quote_amount)
        for rank in range(1, self.grid.sector_count + 1):
            lo, hi = self.grid.bounds(rank)
            rec = self.state["sectors"][f"sector{rank}"]
            self.logger.info(
                "sector%s [%s, %s) state=%s qty=%s",
                rank,
                lo,
                hi,
                rec["state"],
                rec["qty"],
            )

    def run(self) -> None:
        self.connect()
        self.resolve_pending_on_startup()
        self.reconcile_wallet()
        self.print_grid_summary()

        price, current = self.current_sector()
        self.logger.info("Başlangıç fiyat=%s sektör=%s", price, current)

        # Do not infer BUYs from downtime. Optionally close stale A positions.
        self.recover_stale_positions(current, price)
        self.reconcile_wallet()

        # Anchor runtime at the actual current sector. This also safely supports
        # startup in dead_zone / higher_zone.
        self.state["previous_sector"] = current
        save_state(self.state_path, self.state)

        poll = float(self.config.get("poll_interval_seconds", 0.5))
        previous = current

        while True:
            time.sleep(poll)
            price, current = self.current_sector()
            if current == previous:
                continue

            self.process_transition(previous, current, price)
            previous = current
            self.state["previous_sector"] = current
            save_state(self.state_path, self.state)


# -----------------------------
# Internal self-tests
# -----------------------------

def run_self_tests() -> None:
    cfg = {
        "symbol": "TESTUSDT",
        "price_low": "1.42",
        "price_high": "1.70",
        "grid_number": 4,
        "total_quote_budget": "60",
    }
    grid = GridSpec.from_config(cfg)
    assert grid.sector_count == 5
    assert grid.find_sector(D("1.419")) == "dead_zone"
    assert grid.find_sector(D("1.42")) == "sector1"
    assert grid.find_sector(D("1.70")) == "higher_zone"
    assert grid.crossed_action_sectors("sector5", "sector2") == ["sector5", "sector4", "sector3"]
    assert grid.crossed_action_sectors("sector2", "sector5") == ["sector2", "sector3", "sector4"]
    assert grid.crossed_action_sectors("sector1", "dead_zone") == ["sector1"]
    assert grid.crossed_action_sectors("sector5", "higher_zone") == ["sector5"]
    assert grid.crossed_action_sectors("dead_zone", "sector3") == []
    assert grid.crossed_action_sectors("higher_zone", "sector4") == []

    assert floor_to_step(D("8.11"), D("0.1")) == D("8.1")
    assert floor_to_step(D("8.119"), D("0.01")) == D("8.11")
    assert floor_to_step(D("8.9"), D("1")) == D("8")
    assert floor_to_step(D("0.00012349"), D("0.000001")) == D("0.000123")

    # Exhaustive local state-machine invariant over 20,480 paths.
    # Rule: DOWN can set old crossed sector $->A; UP can set A->$.
    from itertools import product

    sector_count = 5
    tested = 0
    for start in range(1, sector_count + 1):
        for directions in product((-1, 1), repeat=12):
            states = {i: "$" for i in range(1, sector_count + 1)}
            pos = start
            buys = sells = 0
            for direction in directions:
                nxt = pos + direction
                if nxt < 1 or nxt > sector_count:
                    continue
                old_name = f"sector{pos}"
                new_name = f"sector{nxt}"
                crossed = grid.crossed_action_sectors(old_name, new_name)
                for name in crossed:
                    idx = int(name[6:])
                    if direction < 0 and states[idx] == "$":
                        states[idx] = "A"
                        buys += 1
                    elif direction > 0 and states[idx] == "A":
                        states[idx] = "$"
                        sells += 1
                pos = nxt
            open_count = sum(1 for value in states.values() if value == "A")
            assert buys - sells == open_count
            tested += 1

    assert tested == 5 * (2 ** 12)
    print(f"SELF-TEST OK | {tested} state paths + grid/Decimal/gap tests passed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Grid Trading Bot v1.3 Full")
    parser.add_argument("--self-test", action="store_true", help="Run offline internal tests and exit")
    args = parser.parse_args()

    if args.self_test:
        run_self_tests()
        return 0

    lock: Optional[SingleInstanceLock] = None
    try:
        config = load_config()
        logger = setup_logging(config)

        if bool(config.get("run_self_tests_on_start", True)):
            run_self_tests()

        lock = SingleInstanceLock(int(config.get("instance_lock_port", 47821)))
        lock.acquire()

        logger.info("GridBot %s starting | mode=%s", VERSION, config["mode"])
        bot = GridBot(config, logger)
        bot.run()
        return 0

    except KeyboardInterrupt:
        print("\nBot kullanıcı tarafından durduruldu.")
        return 0
    except (ConfigError, SafetyHalt) as exc:
        logging.getLogger("gridbot").critical("SAFETY HALT: %s", exc)
        print(f"\n[SAFETY HALT] {exc}")
        return 2
    except Exception as exc:
        logging.getLogger("gridbot").exception("Beklenmeyen hata")
        print(f"\n[HATA] {type(exc).__name__}: {exc}")
        return 3
    finally:
        if lock is not None:
            lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
