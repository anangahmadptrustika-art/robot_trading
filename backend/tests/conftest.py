"""Fixture bersama: klien uji dengan DB SQLite sementara & Telegram di-mock."""

from __future__ import annotations

import contextlib
import itertools
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import pytest
from fastapi.testclient import TestClient

from app import config, main, notifier

TEST_SECRET = "secret-uji-webhook"
TEST_ADMIN_TOKEN = "token-admin-uji"


@pytest.fixture(autouse=True)
def telegram_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Cegat SEMUA httpx.post di notifier — nol panggilan jaringan saat tes."""
    calls: list[dict[str, Any]] = []

    class _ResponPalsu:
        def raise_for_status(self) -> None:  # pragma: no cover - stub sederhana
            return None

    def _post_palsu(url: str, json: dict[str, Any] | None = None, **_: Any) -> _ResponPalsu:
        calls.append({"url": url, "json": json})
        return _ResponPalsu()

    monkeypatch.setattr(notifier.httpx, "post", _post_palsu)
    return calls


@pytest.fixture
def make_client(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> Callable[..., TestClient]:
    """Pabrik TestClient: DB SQLite sementara per tes + override env settings."""
    stack = contextlib.ExitStack()
    counter = itertools.count()

    def _buat(**env_overrides: Any) -> TestClient:
        db_file = tmp_path / f"uji_{next(counter)}.db"
        env = {
            "WEBHOOK_SECRET": TEST_SECRET,
            "ADMIN_TOKEN": TEST_ADMIN_TOKEN,
            "DATABASE_URL": f"sqlite:///{db_file}",
            "TELEGRAM_BOT_TOKEN": "",
            "TELEGRAM_CHAT_ID": "",
            "TRADING_MODE": "paper",
        }
        env.update({k: str(v) for k, v in env_overrides.items()})
        for kunci, nilai in env.items():
            monkeypatch.setenv(kunci, nilai)
        config.get_settings.cache_clear()
        main.rate_limiter.reset()
        # Konteks TestClient menjalankan lifespan (init DB, validasi settings).
        return stack.enter_context(TestClient(main.app))

    yield _buat
    stack.close()
    config.get_settings.cache_clear()


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    """Klien default dengan pengaturan uji standar."""
    return make_client()


def fresh_time(offset_seconds: int = 0) -> str:
    """Waktu sekarang (UTC) dalam format '+0000' seperti kiriman Pine Script."""
    dt = datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
    return dt.strftime("%Y-%m-%dT%H:%M:%S%z")


def buy_payload(**overrides: Any) -> dict[str, Any]:
    """Payload BUY valid persis seperti contoh Pine Script (RR terhitung = 2.0)."""
    payload: dict[str, Any] = {
        "symbol": "BTCUSDT",
        "timeframe": "15",
        "signal": "BUY",
        "entry": "43250.5",
        "stop_loss": "42980.0",
        "take_profit_1": "43656.2",
        "take_profit_2": "43791.5",
        "risk_reward": "2.0",
        "trend": "BULLISH",
        "confidence": "78",
        "position_size": "0.023",
        "time": fresh_time(),
        "strategy": "Smart Zone Trading Bot",
        "secret": TEST_SECRET,
    }
    payload.update(overrides)
    return payload


def sell_payload(**overrides: Any) -> dict[str, Any]:
    """Payload SELL valid (SL 105 > entry 100 > TP1 92 >= TP2 90; RR = 2.0)."""
    payload: dict[str, Any] = {
        "symbol": "ETHUSDT",
        "timeframe": "15",
        "signal": "SELL",
        "entry": "100",
        "stop_loss": "105",
        "take_profit_1": "92",
        "take_profit_2": "90",
        "risk_reward": "2.0",
        "trend": "BEARISH",
        "confidence": "70",
        "time": fresh_time(),
        "strategy": "Smart Zone Trading Bot",
        "secret": TEST_SECRET,
    }
    payload.update(overrides)
    return payload


def zone_touch_payload(**overrides: Any) -> dict[str, Any]:
    """Payload alert informasi ZONE_TOUCH."""
    payload: dict[str, Any] = {
        "type": "ZONE_TOUCH",
        "side": "BUY",
        "symbol": "BTCUSDT",
        "timeframe": "15",
        "zone_top": "43300.0",
        "zone_bottom": "43200.0",
        "time": fresh_time(),
        "secret": TEST_SECRET,
    }
    payload.update(overrides)
    return payload
