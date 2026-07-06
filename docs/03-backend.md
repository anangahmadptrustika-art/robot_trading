# 03 — Backend FastAPI

> Dokumen ini membedah backend webhook di folder `backend/`: struktur kode, semua endpoint beserta contoh request/response, seluruh environment variable, mode trading (paper/live/signal_only), cara kerja paper trading, keamanan, dan catatan deployment.

---

## 1. Peran & Prinsip

Backend adalah **gerbang validasi** antara alert TradingView dan aksi apa pun. Prinsipnya:

- **Jangan percaya payload** — secret dicek constant-time, risk-reward dihitung ulang dari harga, `position_size` payload diabaikan untuk perhitungan.
- **Semua tercatat** — setiap alert masuk (diterima/ditolak/info) disimpan ke SQLite lengkap dengan alasan penolakan.
- **Gagal aman** — kill switch persisten, batas harian, live trading terkunci ganda dan default MATI.
- **Sederhana** — satu proses uvicorn, SQLite lokal, dependensi minimal (`backend/requirements.txt`).

## 2. Struktur Folder

```text
backend/
├── .env.example        ← contoh konfigurasi; salin menjadi .env
├── requirements.txt    ← fastapi, uvicorn, pydantic(-settings), SQLAlchemy, httpx, pytest
├── pytest.ini
├── app/
│   ├── main.py         ← app FastAPI, endpoint, rantai validasi webhook
│   ├── config.py       ← Settings (pydantic-settings); gagal-cepat jika secret kosong
│   ├── schemas.py      ← TradeSignalPayload, ZoneTouchPayload, KillSwitchRequest,
│   │                     PaperCloseRequest, HealthResponse (koersi string toleran)
│   ├── validators.py   ← validasi bisnis: sisi sinyal, harga, struktur, RR, simbol, umur
│   ├── security.py     ← constant_time_equals, SlidingWindowRateLimiter, allowlist IP,
│   │                     get_client_ip (X-Forwarded-For opsional)
│   ├── database.py     ← engine SQLAlchemy, kv_store, kill switch persisten
│   ├── models.py       ← tabel: signals, paper_trades, kv_store
│   ├── paper_trader.py ← saldo paper, buka/tutup posisi simulasi, laporan
│   ├── notifier.py     ← Telegram (kegagalan ditelan; webhook tetap sukses)
│   └── live_trader.py  ← TEMPLATE live (berhenti di NotImplementedError)
└── tests/              ← pytest: validators, security/config, webhook, admin/paper
```

Database default: berkas SQLite `szt_signals.db` di direktori kerja (lihat `DATABASE_URL`).

## 3. Semua Environment Variable

Sumber: `backend/.env.example` dan `backend/app/config.py`. Aplikasi **menolak start** jika `WEBHOOK_SECRET` atau `ADMIN_TOKEN` kosong.

| Variabel | Default | Keterangan |
|---|---|---|
| `WEBHOOK_SECRET` | *(kosong — wajib diisi)* | Harus sama persis dengan field `secret` payload Pine Script. Buat acak: `openssl rand -hex 32` |
| `ADMIN_TOKEN` | *(kosong — wajib diisi)* | Token endpoint admin (header `X-Admin-Token`); buat **berbeda** dari `WEBHOOK_SECRET` |
| `TELEGRAM_BOT_TOKEN` | *(kosong)* | Token dari @BotFather; kosong = notifikasi nonaktif |
| `TELEGRAM_CHAT_ID` | *(kosong)* | ID chat/grup tujuan (mis. dari @userinfobot) |
| `TELEGRAM_NOTIFY_REJECTED` | `false` | `true` = kirim notifikasi juga saat sinyal ditolak |
| `TELEGRAM_NOTIFY_ZONE_TOUCH` | `false` | `true` = kirim notifikasi alert informasi ZONE_TOUCH |
| `TRADING_MODE` | `paper` | `paper` / `signal_only` / `live` (lihat §6) |
| `ENABLE_LIVE_TRADING` | `false` | Sakelar pengaman kedua untuk mode live |
| `EXCHANGE_ID` | *(kosong)* | ID exchange ccxt (mis. `binance`) — hanya untuk live |
| `EXCHANGE_API_KEY` | *(kosong)* | API key exchange — **nonaktifkan izin withdraw** |
| `EXCHANGE_API_SECRET` | *(kosong)* | API secret exchange |
| `PAPER_START_BALANCE` | `10000` | Saldo awal simulasi (mata uang quote, mis. USDT) |
| `RISK_PER_TRADE_PCT` | `1.0` | Persen saldo paper yang dipertaruhkan per posisi |
| `MIN_RISK_REWARD` | `1.5` | RR minimum hasil **hitung ulang server**; di bawah ini ditolak |
| `MAX_SIGNALS_PER_DAY` | `10` | Maksimum sinyal **diterima** per hari UTC (global, semua simbol) |
| `MAX_DAILY_LOSS_PCT` | `3.0` | Total rugi paper yang ditutup hari ini melebihi persen ini dari saldo → sinyal baru ditolak sampai hari UTC berikutnya |
| `DEDUP_WINDOW_SECONDS` | `300` | Jendela dedup simbol+arah+timeframe (tolak 409) |
| `SIGNAL_MAX_AGE_SECONDS` | `300` | Umur maksimum sinyal dari field `time` (0 = nonaktif) |
| `SYMBOL_ALLOWLIST` | *(kosong)* | Simbol diizinkan, dipisah koma (mis. `BTCUSDT,ETHUSDT`); kosong = semua |
| `IP_ALLOWLIST` | *(kosong)* | IP pengirim diizinkan, dipisah koma; kosong = semua. IP TradingView: lihat [docs/02 §7](02-alert-webhook.md#7-allowlist-ip-tradingview) |
| `TRUST_PROXY_HEADERS` | `false` | `true` HANYA di belakang reverse proxy tepercaya yang **menimpa** `X-Forwarded-For` |
| `RATE_LIMIT_PER_MINUTE` | `30` | Batas request per menit per IP (sliding window di memori) |
| `DATABASE_URL` | `sqlite:///./szt_signals.db` | URL SQLAlchemy |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

## 4. Endpoint

### 4.1 `POST /webhook/tradingview` — pintu masuk alert

- **Auth:** field `secret` di body JSON (bukan header).
- **Body:** payload sinyal atau ZONE_TOUCH (lihat [docs/02 §5](02-alert-webhook.md#5-payload-lengkap-semua-field--tipe)).

Contoh request:

```bash
curl -X POST http://localhost:8000/webhook/tradingview \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTCUSDT","timeframe":"60","signal":"BUY","entry":"64230.5","stop_loss":"63780.0","take_profit_1":"64906.25","take_profit_2":"65131.5","risk_reward":"2","trend":"BULLISH","confidence":"72","time":"2026-07-06T13:00:00+0000","strategy":"Smart Zone Trading Bot","secret":"SECRET-ANDA"}'
```

Respons diterima (200):

```json
{"status": "accepted", "signal_id": 12, "mode": "paper", "paper_trade_id": 7}
```

Respons ditolak (contoh 400):

```json
{"status": "rejected", "reason": "risk_reward_too_low"}
```

Respons ZONE_TOUCH (200): `{"status": "info", "signal_id": 13}`.

### 4.2 `GET /health` — cek kesehatan

```bash
curl http://localhost:8000/health
# {"status":"ok","mode":"paper","kill_switch":false}
```

### 4.3 `GET /signals` — daftar sinyal

Query: `limit` (1–500, default 50), `offset` (default 0), `status` (`accepted` | `rejected` | `info`).

```bash
curl "http://localhost:8000/signals?limit=2&status=accepted"
```

```json
{
  "count": 2,
  "signals": [
    {
      "id": 12,
      "received_at": "2026-07-06T13:00:02.412331",
      "symbol": "BTCUSDT",
      "timeframe": "60",
      "signal": "BUY",
      "entry": 64230.5,
      "stop_loss": 63780.0,
      "take_profit_1": 64906.25,
      "take_profit_2": 65131.5,
      "risk_reward_reported": 2.0,
      "risk_reward_computed": 2.0,
      "trend": "BULLISH",
      "confidence": 72.0,
      "signal_time": "2026-07-06T13:00:00+0000",
      "strategy": "Smart Zone Trading Bot",
      "status": "accepted",
      "reject_reason": null,
      "raw_payload": { "symbol": "BTCUSDT", "...": "(tanpa field secret)" }
    }
  ]
}
```

### 4.4 `GET /report/paper` — laporan paper trading

```bash
curl http://localhost:8000/report/paper
```

```json
{
  "paper_balance": 10057.5,
  "open_trades_count": 1,
  "closed_trades_count": 4,
  "total_pnl": 57.5,
  "win_rate_pct": 75.0,
  "trades": [
    {
      "id": 7, "signal_id": 12, "symbol": "BTCUSDT", "side": "BUY",
      "entry": 64230.5, "stop_loss": 63780.0,
      "take_profit_1": 64906.25, "take_profit_2": 65131.5,
      "qty": 0.2219, "risk_amount": 100.0, "status": "open",
      "exit_price": null, "pnl": null,
      "opened_at": "2026-07-06T13:00:02.498001", "closed_at": null
    }
  ]
}
```

### 4.5 `GET /export/signals.csv` — ekspor CSV

Mengembalikan seluruh tabel `signals` sebagai CSV (kolom: id, received_at, symbol, timeframe, signal, entry, stop_loss, take_profit_1, take_profit_2, risk_reward_reported, risk_reward_computed, trend, confidence, signal_time, strategy, status, reject_reason) — **tanpa** raw_payload/secret. Cocok untuk analisis di spreadsheet.

```bash
curl -o signals.csv http://localhost:8000/export/signals.csv
```

### 4.6 `POST /admin/kill-switch` — kill switch (auth: `X-Admin-Token`)

Status disimpan persisten di tabel `kv_store` — bertahan melewati restart.

```bash
# Nyalakan (semua sinyal berikutnya ditolak 503 kill_switch_active)
curl -X POST http://localhost:8000/admin/kill-switch \
  -H "X-Admin-Token: ADMIN-TOKEN-ANDA" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
# {"status":"ok","kill_switch":true}

# Matikan kembali
curl -X POST http://localhost:8000/admin/kill-switch \
  -H "X-Admin-Token: ADMIN-TOKEN-ANDA" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

Token salah/kosong → `401 {"detail":"Token admin tidak valid."}`.

### 4.7 `POST /paper/close/{trade_id}` — tutup paper trade manual (auth: `X-Admin-Token`)

```bash
curl -X POST http://localhost:8000/paper/close/7 \
  -H "X-Admin-Token: ADMIN-TOKEN-ANDA" \
  -H "Content-Type: application/json" \
  -d '{"exit_price": 64906.25}'
```

```json
{
  "status": "ok", "trade_id": 7, "side": "BUY",
  "entry": 64230.5, "exit_price": 64906.25,
  "qty": 0.2219, "pnl": 149.97, "paper_balance": 10207.47
}
```

Error: 404 jika trade tidak ada, 400 jika sudah ditutup, 422 jika `exit_price` ≤ 0.

## 5. Rantai Validasi & Kode Alasan Penolakan

Urutan persis di `app/main.py` (`tradingview_webhook`). Setiap penolakan tetap **dicatat** ke tabel `signals` dengan `status=rejected` + `reject_reason`.

| # | Langkah | `reason` | HTTP |
|---|---|---|---|
| 1a | Rate limit per IP (jendela geser 60 detik, `RATE_LIMIT_PER_MINUTE`) | `rate_limited` | 429 |
| 1b | Allowlist IP (`IP_ALLOWLIST`; kosong = semua) | `ip_not_allowed` | 403 |
| 2 | Kill switch (persisten di `kv_store`) | `kill_switch_active` | 503 |
| 3 | Cek `secret` constant-time; secret tidak pernah dicatat/di-log | `invalid_secret` | 401 |
| — | Cabang `type=ZONE_TOUCH` → dicatat `status=info`, selesai | (`invalid_payload` jika rusak) | 200 / 422 |
| 4 | Skema/koersi Pydantic (`TradeSignalPayload`) | `invalid_payload` | 422 |
| 5 | Sisi sinyal ∈ {BUY, SELL}; semua harga > 0; struktur harga (BUY: SL < entry < TP1 ≤ TP2, SELL kebalikan) | `invalid_signal_side` / `invalid_prices` / `invalid_price_structure` | 400 |
| 6 | RR hitung ulang = \|TP2−entry\|/\|entry−SL\| ≥ `MIN_RISK_REWARD` | `risk_reward_too_low` | 400 |
| 7 | Allowlist simbol (`SYMBOL_ALLOWLIST`) | `symbol_not_allowed` | 400 |
| 8 | Umur sinyal ≤ `SIGNAL_MAX_AGE_SECONDS` (waktu tak terbaca → **diterima** + warning `unparseable_time` di log) | `stale_signal` | 400 |
| 9 | Dedup: ada sinyal `accepted` dengan simbol+arah+timeframe sama dalam `DEDUP_WINDOW_SECONDS` | `duplicate_signal` | 409 |
| 10a | Jumlah sinyal `accepted` hari ini (UTC) ≥ `MAX_SIGNALS_PER_DAY` | `daily_signal_limit` | 400 |
| 10b | Total PnL paper yang **ditutup** hari ini ≤ −`MAX_DAILY_LOSS_PCT`% × saldo | `daily_loss_limit` | 400 |

Lolos semua → simpan `status=accepted` → eksekusi sesuai mode (§6) → notifikasi Telegram.

## 6. Mode Trading: `paper` / `signal_only` / `live`

| Mode | Yang terjadi saat sinyal diterima | Kapan dipakai |
|---|---|---|
| `paper` *(default)* | Buka **paper trade** di buku besar simulasi + catat + notifikasi | Forward test — tahap wajib sebelum live |
| `signal_only` | Hanya catat + notifikasi; tanpa buku besar paper | Sekadar jurnal sinyal / eksekusi manual |
| `live` | Panggil `execute_live_order()` — **hanya jika** `ENABLE_LIVE_TRADING=true` | Setelah paper memuaskan **dan** Anda menulis + menguji implementasi order sendiri |

Fakta penting tentang mode `live`:

- `app/live_trader.py` adalah **template**: tiga lapis penjaga (mode+flag, kredensial lengkap, ccxt terpasang) lalu **sengaja berhenti** dengan `NotImplementedError`. Tidak ada satu order riil pun yang bisa terkirim tanpa Anda menulis kodenya sendiri.
- `ccxt` **sengaja tidak ada** di `requirements.txt`; pasang manual (`pip install ccxt`) hanya jika sadar risikonya.
- Kegagalan `execute_live_order` di-log tetapi tidak mematikan webhook.
- Contoh implementasi (dikomentari di file) menyarankan: mulai dari **sandbox/testnet**, hitung qty dari risiko riil akun (jangan percaya `position_size` payload), dan pastikan order SL/TP benar-benar terpasang sebelum menganggap posisi aman.

## 7. Cara Kerja Paper Trading

**Buka posisi** (otomatis, mode `paper`, sinyal diterima):

```text
risk_amount = saldo_paper × RISK_PER_TRADE_PCT / 100
qty         = risk_amount ÷ |entry − stop_loss|
```

Posisi tercatat `status=open` di tabel `paper_trades` dengan entry/SL/TP1/TP2 dari sinyal. Saldo paper disimpan persisten di `kv_store` dan diinisialisasi dari `PAPER_START_BALANCE` saat pertama dipakai.

**Tutup posisi** — di v1 **manual** lewat endpoint admin (belum ada auto-resolve harga live; itu rencana v2 di [README §12](../README.md#12-saran-pengembangan-lanjutan--roadmap)):

1. Lihat posisi terbuka: `GET /report/paper` (cari `status: "open"`).
2. Saat harga menyentuh SL/TP di chart (atau sinyal EXPIRED), tutup dengan harga tersebut:
   `POST /paper/close/{trade_id}` body `{"exit_price": <harga>}`.
3. PnL dihitung server: BUY = `(exit − entry) × qty`; SELL = `(entry − exit) × qty`; saldo paper diperbarui.

Disiplin menutup paper trade sesuai harga yang benar-benar terjadi (bukan harga "seandainya") adalah syarat agar statistik paper Anda jujur. PnL paper yang ditutup hari ini juga menjadi dasar guard `MAX_DAILY_LOSS_PCT`.

**Laporan:** `GET /report/paper` → saldo, jumlah posisi open/closed, total PnL, win rate, dan daftar seluruh trade.

## 8. Keamanan

- **Secret & token**: `WEBHOOK_SECRET` dan `ADMIN_TOKEN` wajib terisi (start-up gagal jika kosong), dibandingkan constant-time (`hmac.compare_digest`), tidak pernah masuk log/database.
- **Jangan hardcode key**: semua rahasia dibaca dari environment/`.env` (`app/config.py` tidak memuat satu pun rahasia). Rahasia yang di-hardcode akan ikut ter-commit ke git, muncul di diff/backup, dan tidak bisa dirotasi tanpa rilis kode — **jangan pernah** menuliskan API key di kode, dan jangan commit `.env`.
- **Rate limit**: sliding window per IP di memori (`RATE_LIMIT_PER_MINUTE`, jendela 60 detik). Cukup untuk satu proses uvicorn; jika menjalankan banyak worker/instance, pindahkan ke lapisan proxy atau store bersama.
- **Allowlist IP**: `IP_ALLOWLIST` + `TRUST_PROXY_HEADERS` (lihat peringatan di [docs/02 §7](02-alert-webhook.md#7-allowlist-ip-tradingview)).
- **Allowlist simbol**: `SYMBOL_ALLOWLIST` membatasi instrumen yang boleh diproses.
- **Kill switch**: `POST /admin/kill-switch` — persisten, cara tercepat menghentikan pemrosesan sinyal tanpa mematikan server. Uji secara rutin.
- **Umur sinyal & dedup**: menolak replay alert lama dan alert kembar.
- **API key exchange** (jika kelak live): tanpa izin withdraw, dibatasi IP server, akun ber-2FA.
- Pertimbangkan juga membatasi akses endpoint baca (`/signals`, `/report/paper`, `/export/signals.csv`) di lapisan proxy jika server publik — endpoint tersebut tidak berautentikasi di aplikasi.

## 9. Deployment Singkat

### systemd (VPS Linux)

`/etc/systemd/system/szt-backend.service`:

```ini
[Unit]
Description=Smart Zone Trading Bot Backend
After=network.target

[Service]
User=szt
WorkingDirectory=/opt/robot_trading/backend
Environment=PATH=/opt/robot_trading/backend/.venv/bin
ExecStart=/opt/robot_trading/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now szt-backend
journalctl -u szt-backend -f     # pantau log
```

### Reverse proxy HTTPS

Bind uvicorn ke `127.0.0.1` dan taruh proxy TLS di depannya. Contoh **Caddy** (sertifikat Let's Encrypt otomatis):

```text
bot.domain-anda.com {
    reverse_proxy 127.0.0.1:8000
}
```

Atau **Nginx** + certbot:

```nginx
server {
    listen 443 ssl;
    server_name bot.domain-anda.com;
    # ssl_certificate ... (certbot)
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header X-Forwarded-For $remote_addr;   # MENIMPA, bukan meneruskan
    }
}
```

Dengan proxy yang menimpa `X-Forwarded-For` seperti di atas, set `TRUST_PROXY_HEADERS=true` agar rate limit & allowlist IP membaca IP klien asli.

### Docker (catatan)

Belum ada `Dockerfile` di repo; jika membuatnya sendiri: base `python:3.11-slim`, `pip install -r requirements.txt`, jalankan `uvicorn app.main:app --host 0.0.0.0 --port 8000`, **mount volume** untuk berkas SQLite (mis. set `DATABASE_URL=sqlite:////data/szt_signals.db`), dan suntik konfigurasi lewat env (bukan menyalin `.env` ke image). Tambahkan `restart: always` di compose.

### Operasional

- Pantau `GET /health` dari uptime monitor.
- Backup berkas SQLite secara berkala.
- Satu proses uvicorn sudah memadai untuk beban webhook; hindari multi-worker tanpa memindahkan rate limiter (lihat §8).
