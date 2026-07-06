"""Tes unit keamanan, rate limiter, konfigurasi gagal-cepat, dan template live."""

from __future__ import annotations

import pytest

from app import security
from app.config import Settings, validate_startup_settings
from app.live_trader import execute_live_order
from app.models import Signal


class TestSecret:
    def test_secret_benar(self) -> None:
        assert security.check_webhook_secret("rahasia", "rahasia") is True

    def test_secret_salah_atau_kosong(self) -> None:
        assert security.check_webhook_secret("salah", "rahasia") is False
        assert security.check_webhook_secret("", "rahasia") is False
        assert security.check_webhook_secret(None, "rahasia") is False
        assert security.check_webhook_secret(123, "rahasia") is False

    def test_secret_server_kosong_selalu_gagal(self) -> None:
        assert security.check_webhook_secret("apapun", "") is False


class TestRateLimiter:
    def test_sliding_window(self) -> None:
        rl = security.SlidingWindowRateLimiter(window_seconds=60.0)
        assert rl.allow("ip1", 2, now=0.0) is True
        assert rl.allow("ip1", 2, now=1.0) is True
        assert rl.allow("ip1", 2, now=2.0) is False  # batas tercapai
        assert rl.allow("ip2", 2, now=2.0) is True  # kunci lain tidak terpengaruh
        assert rl.allow("ip1", 2, now=61.5) is True  # jendela sudah bergeser

    def test_reset(self) -> None:
        rl = security.SlidingWindowRateLimiter()
        assert rl.allow("ip1", 1, now=0.0) is True
        assert rl.allow("ip1", 1, now=1.0) is False
        rl.reset()
        assert rl.allow("ip1", 1, now=2.0) is True


class TestAllowlistIP:
    def test_kosong_izinkan_semua(self) -> None:
        assert security.is_ip_allowed("1.2.3.4", set()) is True

    def test_terdaftar_dan_tidak(self) -> None:
        assert security.is_ip_allowed("1.2.3.4", {"1.2.3.4"}) is True
        assert security.is_ip_allowed("5.6.7.8", {"1.2.3.4"}) is False


class TestKonfigurasiGagalCepat:
    def test_webhook_secret_kosong_ditolak(self) -> None:
        s = Settings(WEBHOOK_SECRET="", ADMIN_TOKEN="abc", _env_file=None)
        with pytest.raises(RuntimeError, match="WEBHOOK_SECRET"):
            validate_startup_settings(s)

    def test_admin_token_kosong_ditolak(self) -> None:
        s = Settings(WEBHOOK_SECRET="abc", ADMIN_TOKEN="", _env_file=None)
        with pytest.raises(RuntimeError, match="ADMIN_TOKEN"):
            validate_startup_settings(s)

    def test_konfigurasi_lengkap_lolos(self) -> None:
        s = Settings(WEBHOOK_SECRET="abc", ADMIN_TOKEN="def", _env_file=None)
        validate_startup_settings(s)  # tidak boleh raise

    def test_trading_mode_tidak_valid_ditolak(self) -> None:
        with pytest.raises(Exception, match="TRADING_MODE"):
            Settings(WEBHOOK_SECRET="a", ADMIN_TOKEN="b", TRADING_MODE="yolo", _env_file=None)


class TestTemplateLive:
    def _settings(self, **kw) -> Settings:
        dasar = {"WEBHOOK_SECRET": "a", "ADMIN_TOKEN": "b", "_env_file": None}
        dasar.update(kw)
        return Settings(**dasar)

    def _sinyal(self) -> Signal:
        return Signal(id=1, symbol="BTCUSDT", signal="BUY", status="accepted")

    def test_menolak_saat_mode_bukan_live(self) -> None:
        s = self._settings(TRADING_MODE="paper", ENABLE_LIVE_TRADING=True)
        with pytest.raises(RuntimeError, match="tidak aktif|TIDAK aktif"):
            execute_live_order(self._sinyal(), s)

    def test_menolak_saat_flag_mati(self) -> None:
        s = self._settings(TRADING_MODE="live", ENABLE_LIVE_TRADING=False)
        with pytest.raises(RuntimeError):
            execute_live_order(self._sinyal(), s)

    def test_menolak_tanpa_kredensial(self) -> None:
        s = self._settings(TRADING_MODE="live", ENABLE_LIVE_TRADING=True)
        with pytest.raises(RuntimeError, match="Kredensial"):
            execute_live_order(self._sinyal(), s)

    def test_pesan_import_ccxt_membantu(self) -> None:
        # ccxt sengaja tidak terpasang di lingkungan tes.
        s = self._settings(
            TRADING_MODE="live",
            ENABLE_LIVE_TRADING=True,
            EXCHANGE_ID="binance",
            EXCHANGE_API_KEY="k",
            EXCHANGE_API_SECRET="s",
        )
        with pytest.raises(ImportError, match="pip install ccxt"):
            execute_live_order(self._sinyal(), s)
