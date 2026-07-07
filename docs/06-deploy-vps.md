# 06 — Deploy Backend ke VPS (Mode Semi-Auto, HTTPS)

Panduan menjalankan backend Smart Zone Trading Bot **24/7 dengan HTTPS** agar bisa
menerima webhook TradingView secara real-time, lalu meneruskan sinyal ke
**Telegram** untuk Anda eksekusi manual (mode semi-auto — paling aman).

Alur: **TradingView (alert) → `https://DOMAIN/webhook/tradingview` → backend → validasi → Telegram + paper trading.**

---

## 0. Yang perlu disiapkan

| Item | Keterangan |
|---|---|
| VPS Linux | 1 vCPU / 1 GB RAM sudah cukup (DigitalOcean, Vultr, Contabo, Linode, dll). |
| Domain / subdomain | Mis. `bot.namaanda.com`. Buat **A record** ke IP publik VPS. |
| Port terbuka | **80** dan **443** (untuk penerbitan sertifikat TLS + webhook). |
| TradingView plan berbayar | Webhook alert hanya tersedia di plan **Essential** ke atas. |
| Bot Telegram | Token dari **@BotFather** + `chat_id` (lihat `docs/03-backend.md`). |

> Sertifikat HTTPS diurus **otomatis** oleh Caddy (Let's Encrypt). Anda tidak
> perlu membeli/meng-generate sertifikat sendiri.

---

## 1. Cara tercepat — Docker Compose (disarankan)

Semua berkas sudah ada di folder `backend/`: `Dockerfile`, `docker-compose.yml`, `Caddyfile`.

```bash
# 1) Pasang Docker (sekali saja) — lihat https://docs.docker.com/engine/install/
# 2) Ambil kode ke VPS
git clone <URL_REPO_ANDA> robot_trading
cd robot_trading/backend

# 3) Siapkan konfigurasi
cp .env.example .env
nano .env
#   WAJIB isi:  WEBHOOK_SECRET, ADMIN_TOKEN  (buat acak: openssl rand -hex 32)
#   Telegram :  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
#   TAMBAHKAN baris domain Anda:
#   DOMAIN=bot.namaanda.com

# 4) Jalankan (build + start di background)
docker compose up -d --build

# 5) Cek status & log
docker compose ps
docker compose logs -f backend
```

Verifikasi dari komputer mana pun:

```bash
curl https://bot.namaanda.com/health
# {"status":"ok","mode":"paper","kill_switch":false}
```

Update kode di kemudian hari:

```bash
git pull
docker compose up -d --build
```

Berhentikan / hapus:

```bash
docker compose down           # stop (data paper tetap tersimpan di volume)
docker compose down -v        # stop + HAPUS data (hati-hati)
```

> **Catatan volume:** database SQLite disimpan di named volume `szt-data`,
> jadi riwayat sinyal & paper trade **tetap aman** saat `up -d --build` ulang.
> Sertifikat TLS tersimpan di volume `caddy-data`.

---

## 2. Alternatif tanpa Docker — systemd + Caddy manual

Jika Anda lebih suka menjalankan langsung di host:

```bash
cd robot_trading/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env      # isi seperti di atas (DOMAIN tidak wajib di sini)
```

Buat service systemd `/etc/systemd/system/szt-backend.service`:

```ini
[Unit]
Description=Smart Zone Trading Bot Backend
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/home/USER/robot_trading/backend
EnvironmentFile=/home/USER/robot_trading/backend/.env
ExecStart=/home/USER/robot_trading/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now szt-backend
sudo systemctl status szt-backend
```

Pasang Caddy sebagai reverse proxy HTTPS (`/etc/caddy/Caddyfile`):

```caddyfile
bot.namaanda.com {
    reverse_proxy 127.0.0.1:8000
}
```

```bash
sudo systemctl reload caddy
```

> Karena berada di belakang Caddy, set `TRUST_PROXY_HEADERS=true` di `.env`
> agar rate-limit & IP allowlist melihat IP klien sebenarnya.

---

## 3. Uji coba lokal tanpa domain (opsional, untuk belajar)

Untuk mencoba di laptop tanpa VPS/domain, pakai tunnel:

```bash
# Terminal 1 — jalankan backend
cd backend && .venv/bin/uvicorn app.main:app --port 8000

# Terminal 2 — buka tunnel HTTPS publik sementara
ngrok http 8000      # atau: cloudflared tunnel --url http://localhost:8000
```

Gunakan URL HTTPS dari ngrok/cloudflared sebagai target webhook di TradingView.
**Hanya untuk uji coba** — URL berubah tiap restart dan tidak untuk produksi.

---

## 4. Hubungkan alert TradingView

1. Pasang `smart_zone_indicator.pine` di chart (lihat `docs/01-pemasangan-tradingview.md`).
2. Isi input **Webhook secret** di script = `WEBHOOK_SECRET` di `.env`.
3. Buat **Alert** → kondisi **"Any alert() function call"** → centang **Webhook URL**:
   ```
   https://bot.namaanda.com/webhook/tradingview
   ```
4. Detail lengkap payload & opsi frekuensi: `docs/02-alert-webhook.md`.

Uji manual tanpa menunggu sinyal (ganti waktu dengan waktu sekarang UTC):

```bash
curl -X POST https://bot.namaanda.com/webhook/tradingview \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"BTCUSDT","timeframe":"15","signal":"BUY","entry":"43250.5",
       "stop_loss":"42980.0","take_profit_1":"43656.2","take_profit_2":"43791.5",
       "risk_reward":"2.0","trend":"BULLISH","confidence":"78",
       "time":"2026-07-07T01:00:00+0000","strategy":"Smart Zone Trading Bot",
       "secret":"ISI_WEBHOOK_SECRET_ANDA"}'
# {"status":"accepted","signal_id":1,"mode":"paper","paper_trade_id":1}
```
> Jika balasan `stale_signal`, artinya field `time` lebih lama dari
> `SIGNAL_MAX_AGE_SECONDS` — gunakan waktu UTC sekarang. Ini fitur anti-sinyal-basi,
> bukan error.

---

## 5. Checklist keamanan deploy

- [ ] `WEBHOOK_SECRET` & `ADMIN_TOKEN` acak & panjang (`openssl rand -hex 32`), berbeda satu sama lain.
- [ ] `.env` **tidak** ikut ter-commit (sudah di `.gitignore`).
- [ ] HTTPS aktif (uji `https://DOMAIN/health`), port 80/443 saja yang terbuka; **jangan** ekspos port 8000 ke publik.
- [ ] `TRUST_PROXY_HEADERS=true` karena di belakang Caddy.
- [ ] (Opsional) Isi `IP_ALLOWLIST` dengan IP webhook TradingView (lihat `docs/02-alert-webhook.md`).
- [ ] Firewall VPS (ufw) hanya izinkan 22, 80, 443.
- [ ] `TRADING_MODE=paper` dulu; uji kill switch: `POST /admin/kill-switch` dengan header `X-Admin-Token`.
- [ ] Backup berkala volume `szt-data` (berisi riwayat sinyal & paper trade).

---

## 6. Setelah semi-auto berjalan mulus

Kalau Anda sudah puas dengan kualitas sinyal dari paper trading dan ingin
otomasi eksekusi, jalur berikutnya:

- **Crypto** (Binance/Bybit/dll): aktifkan template `app/live_trader.py` (berbasis `ccxt`).
- **Exness / forex-gold-CFD**: perlu adapter **MT5** baru (`MetaTrader5` di Windows VPS) —
  `ccxt` tidak mendukung Exness. Minta untuk dibuatkan bila diperlukan.

> **Selalu uji di akun demo lebih dulu, ukuran kecil, dengan kill switch &
> batas loss harian aktif.** Sistem ini bukan jaminan profit.
