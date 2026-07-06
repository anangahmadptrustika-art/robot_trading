"""Tes unit fungsi murni di app.validators."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import validators


class TestStrukturHarga:
    def test_buy_valid(self) -> None:
        ok, alasan = validators.check_price_structure("BUY", 100, 95, 105, 110)
        assert ok and alasan == ""

    def test_buy_sl_di_atas_entry(self) -> None:
        ok, alasan = validators.check_price_structure("BUY", 100, 101, 105, 110)
        assert not ok and alasan == "invalid_price_structure"

    def test_buy_tp1_boleh_sama_dengan_tp2(self) -> None:
        ok, _ = validators.check_price_structure("BUY", 100, 95, 110, 110)
        assert ok

    def test_sell_valid(self) -> None:
        ok, _ = validators.check_price_structure("SELL", 100, 105, 92, 90)
        assert ok

    def test_sell_terbalik(self) -> None:
        ok, alasan = validators.check_price_structure("SELL", 100, 95, 105, 110)
        assert not ok and alasan == "invalid_price_structure"

    def test_entry_sama_dengan_sl_tidak_valid(self) -> None:
        ok, _ = validators.check_price_structure("BUY", 100, 100, 105, 110)
        assert not ok


class TestRiskReward:
    def test_hitung_rr(self) -> None:
        assert validators.compute_risk_reward(100, 95, 110) == pytest.approx(2.0)

    def test_rr_risiko_nol(self) -> None:
        assert validators.compute_risk_reward(100, 100, 110) is None

    def test_ambang_minimum(self) -> None:
        assert validators.check_min_risk_reward(1.4, 1.5) == (False, "risk_reward_too_low")
        assert validators.check_min_risk_reward(1.5, 1.5) == (True, "")
        assert validators.check_min_risk_reward(None, 1.5) == (False, "risk_reward_too_low")


class TestParseWaktu:
    def test_offset_tanpa_kolon(self) -> None:
        dt = validators.parse_signal_time("2026-07-06T12:00:00+0000")
        assert dt == datetime(2026, 7, 6, 12, 0, 0, tzinfo=timezone.utc)

    def test_akhiran_z(self) -> None:
        dt = validators.parse_signal_time("2026-07-06T12:00:00Z")
        assert dt == datetime(2026, 7, 6, 12, 0, 0, tzinfo=timezone.utc)

    def test_offset_non_utc_dinormalkan(self) -> None:
        dt = validators.parse_signal_time("2026-07-06T19:00:00+0700")
        assert dt == datetime(2026, 7, 6, 12, 0, 0, tzinfo=timezone.utc)

    def test_tanpa_zona_dianggap_utc(self) -> None:
        dt = validators.parse_signal_time("2026-07-06T12:00:00")
        assert dt == datetime(2026, 7, 6, 12, 0, 0, tzinfo=timezone.utc)

    def test_sampah_mengembalikan_none(self) -> None:
        assert validators.parse_signal_time("kemarin sore") is None
        assert validators.parse_signal_time("") is None
        assert validators.parse_signal_time(None) is None


class TestUmurSinyal:
    def test_nonaktif_jika_nol(self) -> None:
        assert validators.check_signal_age("2000-01-01T00:00:00Z", 0) == (True, "")

    def test_basi(self) -> None:
        lama = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        assert validators.check_signal_age(lama, 300) == (False, "stale_signal")

    def test_segar(self) -> None:
        baru = datetime.now(timezone.utc).isoformat()
        assert validators.check_signal_age(baru, 300) == (True, "")

    def test_tak_terbaca_lolos_dengan_penanda(self) -> None:
        assert validators.check_signal_age("???", 300) == (True, "unparseable_time")


class TestAllowlistSimbol:
    def test_kosong_izinkan_semua(self) -> None:
        assert validators.check_symbol_allowed("BTCUSDT", set()) == (True, "")

    def test_di_dalam_daftar(self) -> None:
        assert validators.check_symbol_allowed("btcusdt", {"BTCUSDT"}) == (True, "")

    def test_di_luar_daftar(self) -> None:
        ok, alasan = validators.check_symbol_allowed("DOGEUSDT", {"BTCUSDT"})
        assert not ok and alasan == "symbol_not_allowed"
