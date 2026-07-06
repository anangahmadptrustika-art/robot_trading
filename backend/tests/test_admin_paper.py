"""Tes endpoint admin (kill switch, tutup paper trade), laporan, dan ekspor CSV."""

from __future__ import annotations

import pytest

from tests.conftest import TEST_ADMIN_TOKEN, buy_payload, sell_payload

URL = "/webhook/tradingview"
ADMIN = {"X-Admin-Token": TEST_ADMIN_TOKEN}


class TestKillSwitch:
    def test_toggle_dengan_token_benar(self, client) -> None:
        r = client.post("/admin/kill-switch", json={"enabled": True}, headers=ADMIN)
        assert r.status_code == 200
        assert r.json()["kill_switch"] is True
        assert client.get("/health").json()["kill_switch"] is True

    def test_token_salah_401(self, client) -> None:
        r = client.post(
            "/admin/kill-switch", json={"enabled": True}, headers={"X-Admin-Token": "salah"}
        )
        assert r.status_code == 401

    def test_tanpa_token_401(self, client) -> None:
        r = client.post("/admin/kill-switch", json={"enabled": True})
        assert r.status_code == 401

    def test_webhook_saat_kill_switch_503(self, client) -> None:
        client.post("/admin/kill-switch", json={"enabled": True}, headers=ADMIN)
        r = client.post(URL, json=buy_payload())
        assert r.status_code == 503
        assert r.json()["reason"] == "kill_switch_active"

    def test_webhook_normal_setelah_dimatikan(self, client) -> None:
        client.post("/admin/kill-switch", json={"enabled": True}, headers=ADMIN)
        client.post("/admin/kill-switch", json={"enabled": False}, headers=ADMIN)
        assert client.get("/health").json()["kill_switch"] is False
        assert client.post(URL, json=buy_payload()).status_code == 200


class TestPaperClose:
    def test_close_buy_pnl_dan_saldo_benar(self, client) -> None:
        r = client.post(URL, json=buy_payload())
        trade_id = r.json()["paper_trade_id"]
        exit_price = 43791.5  # TP2
        r = client.post(f"/paper/close/{trade_id}", json={"exit_price": exit_price}, headers=ADMIN)
        assert r.status_code == 200
        body = r.json()
        qty = 100.0 / 270.5
        pnl_harapan = (exit_price - 43250.5) * qty  # BUY: (exit - entry) * qty
        assert body["pnl"] == pytest.approx(pnl_harapan)
        assert body["paper_balance"] == pytest.approx(10000.0 + pnl_harapan)

    def test_close_sell_pnl_dan_saldo_benar(self, client) -> None:
        r = client.post(URL, json=sell_payload())
        trade_id = r.json()["paper_trade_id"]
        r = client.post(f"/paper/close/{trade_id}", json={"exit_price": 95.0}, headers=ADMIN)
        assert r.status_code == 200
        body = r.json()
        qty = 100.0 / 5.0  # risk 100 / |100 - 105|
        pnl_harapan = (100.0 - 95.0) * qty  # SELL: (entry - exit) * qty
        assert body["pnl"] == pytest.approx(pnl_harapan)
        assert body["paper_balance"] == pytest.approx(10000.0 + pnl_harapan)

    def test_laporan_mencerminkan_penutupan(self, client) -> None:
        r = client.post(URL, json=sell_payload())
        trade_id = r.json()["paper_trade_id"]
        client.post(f"/paper/close/{trade_id}", json={"exit_price": 95.0}, headers=ADMIN)
        laporan = client.get("/report/paper").json()
        assert laporan["open_trades_count"] == 0
        assert laporan["closed_trades_count"] == 1
        # qty = 100 / |100 - 105| = 20; pnl = (100 - 95) * 20 = 100.
        assert laporan["total_pnl"] == pytest.approx(100.0)
        assert laporan["win_rate_pct"] == pytest.approx(100.0)
        assert laporan["paper_balance"] == pytest.approx(10100.0)

    def test_close_token_salah_401(self, client) -> None:
        r = client.post(URL, json=buy_payload())
        trade_id = r.json()["paper_trade_id"]
        r = client.post(
            f"/paper/close/{trade_id}",
            json={"exit_price": 43500.0},
            headers={"X-Admin-Token": "salah"},
        )
        assert r.status_code == 401

    def test_close_trade_tidak_ada_404(self, client) -> None:
        r = client.post("/paper/close/9999", json={"exit_price": 100.0}, headers=ADMIN)
        assert r.status_code == 404

    def test_close_dua_kali_400(self, client) -> None:
        r = client.post(URL, json=buy_payload())
        trade_id = r.json()["paper_trade_id"]
        assert (
            client.post(f"/paper/close/{trade_id}", json={"exit_price": 43500.0}, headers=ADMIN)
        ).status_code == 200
        r = client.post(f"/paper/close/{trade_id}", json={"exit_price": 43600.0}, headers=ADMIN)
        assert r.status_code == 400


class TestLaporanDanEkspor:
    def test_health(self, client) -> None:
        body = client.get("/health").json()
        assert body == {"status": "ok", "mode": "paper", "kill_switch": False}

    def test_csv_export_header_dan_baris(self, client) -> None:
        client.post(URL, json=buy_payload())
        client.post(URL, json=buy_payload(secret="salah"))  # baris rejected
        r = client.get("/export/signals.csv")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")
        baris = [b for b in r.text.strip().splitlines() if b]
        assert baris[0].startswith("id,received_at,symbol,timeframe,signal,entry")
        assert len(baris) == 3  # header + 1 accepted + 1 rejected
        assert "BTCUSDT" in baris[1]

    def test_daftar_sinyal_filter_status(self, client) -> None:
        client.post(URL, json=buy_payload())
        client.post(URL, json=buy_payload())  # duplikat → rejected
        assert client.get("/signals", params={"status": "accepted"}).json()["count"] == 1
        assert client.get("/signals", params={"status": "rejected"}).json()["count"] == 1
        assert client.get("/signals").json()["count"] == 2
