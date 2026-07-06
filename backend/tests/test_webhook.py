"""Tes endpoint POST /webhook/tradingview: rantai validasi lengkap."""

from __future__ import annotations

import pytest

from tests.conftest import TEST_SECRET, buy_payload, fresh_time, sell_payload, zone_touch_payload

URL = "/webhook/tradingview"


class TestSecret:
    def test_secret_hilang_ditolak_401(self, client) -> None:
        payload = buy_payload()
        payload.pop("secret")
        r = client.post(URL, json=payload)
        assert r.status_code == 401
        assert r.json() == {"status": "rejected", "reason": "invalid_secret"}

    def test_secret_salah_ditolak_401(self, client) -> None:
        r = client.post(URL, json=buy_payload(secret="secret-salah"))
        assert r.status_code == 401
        assert r.json()["reason"] == "invalid_secret"

    def test_secret_tidak_pernah_disimpan(self, client) -> None:
        client.post(URL, json=buy_payload())
        data = client.get("/signals").json()
        for sinyal in data["signals"]:
            assert "secret" not in (sinyal["raw_payload"] or {})
            assert TEST_SECRET not in str(sinyal["raw_payload"])


class TestBuyValid:
    def test_buy_valid_diterima(self, client) -> None:
        r = client.post(URL, json=buy_payload())
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "accepted"
        assert body["mode"] == "paper"
        assert body["signal_id"] is not None
        assert body["paper_trade_id"] is not None

    def test_sinyal_tersimpan_dengan_rr_hitung_ulang(self, client) -> None:
        client.post(URL, json=buy_payload())
        data = client.get("/signals", params={"status": "accepted"}).json()
        assert data["count"] == 1
        sinyal = data["signals"][0]
        assert sinyal["symbol"] == "BTCUSDT"
        assert sinyal["signal"] == "BUY"
        assert sinyal["entry"] == pytest.approx(43250.5)
        assert sinyal["risk_reward_reported"] == pytest.approx(2.0)
        # RR hitung ulang: |43791.5 - 43250.5| / |43250.5 - 42980.0| = 541/270.5
        assert sinyal["risk_reward_computed"] == pytest.approx(541.0 / 270.5)

    def test_paper_trade_dibuka_dengan_qty_benar(self, client) -> None:
        client.post(URL, json=buy_payload())
        laporan = client.get("/report/paper").json()
        assert laporan["open_trades_count"] == 1
        trade = laporan["trades"][0]
        # risk_amount = 10000 * 1% = 100; qty = 100 / |43250.5 - 42980.0|
        assert trade["risk_amount"] == pytest.approx(100.0)
        assert trade["qty"] == pytest.approx(100.0 / 270.5)
        assert trade["side"] == "BUY"
        assert trade["status"] == "open"

    def test_mode_signal_only_tanpa_paper_trade(self, make_client) -> None:
        client = make_client(TRADING_MODE="signal_only")
        r = client.post(URL, json=buy_payload())
        assert r.status_code == 200
        assert r.json()["paper_trade_id"] is None
        assert client.get("/report/paper").json()["open_trades_count"] == 0


class TestValidasiBisnis:
    def test_rr_di_bawah_minimum_ditolak_400(self, client) -> None:
        # entry 100, SL 95, TP2 102 → RR = 2/5 = 0.4 < 1.5
        r = client.post(
            URL,
            json=buy_payload(entry="100", stop_loss="95", take_profit_1="101", take_profit_2="102"),
        )
        assert r.status_code == 400
        assert r.json()["reason"] == "risk_reward_too_low"

    def test_buy_sl_di_atas_entry_ditolak_400(self, client) -> None:
        r = client.post(URL, json=buy_payload(stop_loss="43500.0"))
        assert r.status_code == 400
        assert r.json()["reason"] == "invalid_price_structure"

    def test_sell_struktur_salah_ditolak_400(self, client) -> None:
        # SELL dengan SL di bawah entry = struktur terbalik.
        r = client.post(URL, json=sell_payload(stop_loss="95"))
        assert r.status_code == 400
        assert r.json()["reason"] == "invalid_price_structure"

    def test_sinyal_bukan_buy_sell_ditolak_400(self, client) -> None:
        r = client.post(URL, json=buy_payload(signal="HOLD"))
        assert r.status_code == 400
        assert r.json()["reason"] == "invalid_signal_side"

    def test_harga_negatif_ditolak_400(self, client) -> None:
        r = client.post(URL, json=buy_payload(entry="-5"))
        assert r.status_code == 400
        assert r.json()["reason"] == "invalid_prices"

    def test_payload_sampah_ditolak_422(self, client) -> None:
        r = client.post(URL, json={"secret": TEST_SECRET, "entry": "bukan-angka"})
        assert r.status_code == 422
        assert r.json()["reason"] == "invalid_payload"

    def test_simbol_di_luar_allowlist_ditolak(self, make_client) -> None:
        client = make_client(SYMBOL_ALLOWLIST="ETHUSDT,SOLUSDT")
        r = client.post(URL, json=buy_payload())
        assert r.status_code == 400
        assert r.json()["reason"] == "symbol_not_allowed"

    def test_penolakan_tercatat_di_database(self, client) -> None:
        client.post(URL, json=buy_payload(signal="HOLD"))
        data = client.get("/signals", params={"status": "rejected"}).json()
        assert data["count"] == 1
        assert data["signals"][0]["reject_reason"] == "invalid_signal_side"


class TestUmurDanDedup:
    def test_sinyal_basi_ditolak(self, make_client) -> None:
        client = make_client(SIGNAL_MAX_AGE_SECONDS=10)
        r = client.post(URL, json=buy_payload(time=fresh_time(offset_seconds=-3600)))
        assert r.status_code == 400
        assert r.json()["reason"] == "stale_signal"

    def test_waktu_tak_terbaca_tetap_diterima(self, client) -> None:
        r = client.post(URL, json=buy_payload(time="kemarin sore"))
        assert r.status_code == 200
        assert r.json()["status"] == "accepted"

    def test_akhiran_z_diterima(self, make_client) -> None:
        client = make_client(SIGNAL_MAX_AGE_SECONDS=3600)
        waktu_z = fresh_time().replace("+0000", "Z")
        r = client.post(URL, json=buy_payload(time=waktu_z))
        assert r.status_code == 200

    def test_duplikat_dalam_jendela_ditolak_409(self, client) -> None:
        assert client.post(URL, json=buy_payload()).status_code == 200
        r = client.post(URL, json=buy_payload())
        assert r.status_code == 409
        assert r.json()["reason"] == "duplicate_signal"

    def test_simbol_beda_bukan_duplikat(self, client) -> None:
        assert client.post(URL, json=buy_payload()).status_code == 200
        r = client.post(URL, json=buy_payload(symbol="ETHUSDT"))
        assert r.status_code == 200


class TestBatasHarian:
    def test_max_signals_per_day_ditegakkan(self, make_client) -> None:
        client = make_client(MAX_SIGNALS_PER_DAY=2)
        assert client.post(URL, json=buy_payload(symbol="AAAUSDT")).status_code == 200
        assert client.post(URL, json=buy_payload(symbol="BBBUSDT")).status_code == 200
        r = client.post(URL, json=buy_payload(symbol="CCCUSDT"))
        assert r.status_code == 400
        assert r.json()["reason"] == "daily_signal_limit"

    def test_daily_loss_limit_ditegakkan(self, make_client) -> None:
        from tests.conftest import TEST_ADMIN_TOKEN

        client = make_client(MAX_DAILY_LOSS_PCT=1.0)
        r = client.post(URL, json=buy_payload())
        trade_id = r.json()["paper_trade_id"]
        # Tutup jauh di bawah entry → rugi ~1000 (>1% saldo).
        r = client.post(
            f"/paper/close/{trade_id}",
            json={"exit_price": 43250.5 - 2705.0},
            headers={"X-Admin-Token": TEST_ADMIN_TOKEN},
        )
        assert r.status_code == 200
        r = client.post(URL, json=buy_payload(symbol="ETHUSDT"))
        assert r.status_code == 400
        assert r.json()["reason"] == "daily_loss_limit"


class TestZoneTouch:
    def test_zone_touch_dicatat_sebagai_info(self, client) -> None:
        r = client.post(URL, json=zone_touch_payload())
        assert r.status_code == 200
        assert r.json()["status"] == "info"
        data = client.get("/signals", params={"status": "info"}).json()
        assert data["count"] == 1
        assert data["signals"][0]["strategy"] == "ZONE_TOUCH"
        assert "secret" not in (data["signals"][0]["raw_payload"] or {})

    def test_zone_touch_tidak_membuka_paper_trade(self, client) -> None:
        client.post(URL, json=zone_touch_payload())
        assert client.get("/report/paper").json()["open_trades_count"] == 0

    def test_zone_touch_secret_salah_ditolak_401(self, client) -> None:
        r = client.post(URL, json=zone_touch_payload(secret="salah"))
        assert r.status_code == 401


class TestRateLimit:
    def test_rate_limit_429(self, make_client) -> None:
        client = make_client(RATE_LIMIT_PER_MINUTE=3)
        for _ in range(3):
            client.post(URL, json=buy_payload(secret="salah"))  # tetap kena limit
        r = client.post(URL, json=buy_payload())
        assert r.status_code == 429
        assert r.json()["reason"] == "rate_limited"
