# 02 — Alert & Webhook TradingView

> Dokumen ini menjelaskan cara membuat alert webhook untuk `smart_zone_indicator.pine`, perbedaan alert sinyal (close-confirmed) dengan alert dini ZONE_TOUCH (intrabar), format lengkap payload JSON, konfigurasi URL webhook, allowlist IP TradingView, dan keamanan secret.

---

## 1. Prasyarat

- Indikator `pinescript/smart_zone_indicator.pine` sudah terpasang di chart ([docs/01](01-pemasangan-tradingview.md)).
- Input **🔔 Alert & Webhook → Webhook secret** sudah diisi, nilainya **sama persis** dengan `WEBHOOK_SECRET` di `backend/.env`.
- Backend sudah berjalan dan dapat diakses publik lewat HTTPS ([docs/03](03-backend.md)) — TradingView hanya mengirim webhook ke port **80/443**.
- Paket TradingView Anda mendukung **webhook notification** (fitur paket berbayar; verifikasi di halaman paket TradingView).

## 2. Cara Membuat Alert

1. Buka chart dengan **simbol, timeframe, dan setting indikator final**. Alert menyimpan snapshot setting saat dibuat — mengubah input setelahnya **tidak** mengubah alert yang sudah ada (buat ulang alert-nya).
2. Tekan `Alt + A` atau klik ikon **⏰ Alert** di toolbar kanan.
3. **Condition** (baris pertama): pilih **`SZT Bot v1`** (nama indikator), lalu pada dropdown kedua pilih **`Any alert() function call`**.
4. **Expiration**: pilih *Open-ended* bila tersedia, atau perpanjang manual sebelum kedaluwarsa.
5. **Alert name**: bebas, mis. `SZT BTCUSDT M15`.
6. Tab **Notifications**:
   - Centang **Webhook URL** dan isi URL backend (lihat §6).
   - Opsional: centang juga notifikasi app/email sebagai cadangan pemantauan.
7. Kolom **Message**: biarkan apa adanya. Untuk kondisi `Any alert() function call`, pesan yang dikirim adalah **string JSON yang dibuat script** lewat fungsi `alert()` — kolom message dialog tidak dipakai. Ini juga alasan `secret` diisi lewat **input script**, bukan diketik di dialog alert.
8. Klik **Create**.

Satu alert menangani semua pesan script pada chart tersebut: sinyal `BUY`, `SELL`, dan (jika input diaktifkan) `ZONE_TOUCH`. Untuk memantau banyak simbol/timeframe, buat satu alert per chart.

## 3. Frekuensi Alert: Siapa yang Mengontrol?

Dengan kondisi `Any alert() function call`, **frekuensi ditentukan oleh script**, bukan dialog alert:

- Semua panggilan `alert()` di script ini memakai `alert.freq_once_per_bar` — maksimal satu kali per bar per jenis pemicu.
- Sinyal BUY/SELL dihitung **di dalam blok `barstate.isconfirmed`**, sehingga efeknya alert sinyal terkirim **hanya pada penutupan candle** (setara "once per bar close").
- `ZONE_TOUCH` dievaluasi **di luar** blok tersebut, sehingga bisa terkirim **intrabar** — begitu harga menyentuh zona, tanpa menunggu close (tetap maksimal sekali per bar per sisi).

## 4. Alert Sinyal vs Alert Dini ZONE_TOUCH

| Aspek | Sinyal BUY/SELL | ZONE_TOUCH |
|---|---|---|
| Kapan terkirim | Penutupan candle (anti-repaint) | Intrabar, saat harga masuk zona |
| Syarat | Lolos SEMUA filter + skor confidence ≥ ambang profil | Cukup zona aktif tersentuh (dan master/kill switch ON) |
| Isi | Level lengkap entry/SL/TP1/TP2 + skor | Hanya batas zona |
| Default | Selalu aktif (selama bot ON) | **OFF** — input `Alert dini saat harga MASUK zona (intrabar)` |
| Perlakuan backend | Divalidasi penuh; bisa membuka paper trade | Dicatat `status=info` saja; **tidak pernah** membuka posisi |
| Kegunaan | Basis eksekusi/paper | "Bersiap-siap" — harga di area menarik, konfirmasi belum tentu terjadi |

Jangan mengeksekusi apa pun hanya dari ZONE_TOUCH: harga bisa masuk zona lalu menembusnya tanpa pernah menghasilkan sinyal.

## 5. Payload Lengkap: Semua Field + Tipe

Payload dibuat `f_json()` (sinyal) dan string literal (ZONE_TOUCH). **Semua nilai dikirim sebagai string JSON**; kolom "Tipe efektif" adalah hasil koersi backend (`backend/app/schemas.py`).

### 5.1 Payload sinyal (BUY/SELL)

| Field | Contoh | Tipe efektif | Keterangan |
|---|---|---|---|
| `symbol` | `"BTCUSDT"` | string | `syminfo.ticker` — ticker **tanpa** prefix exchange |
| `timeframe` | `"60"` | string | `timeframe.period` (menit; `"D"`, `"W"` untuk daily/weekly) |
| `signal` | `"BUY"` | string | `BUY` atau `SELL` |
| `entry` | `"64230.5"` | float | Harga close candle sinyal, format `mintick` |
| `stop_loss` | `"63780.0"` | float | SL hasil mode swing/ATR |
| `take_profit_1` | `"64906.25"` | float | entry ± `tp1RR` × risiko |
| `take_profit_2` | `"65131.5"` | float | entry ± `tp2RR` × risiko |
| `risk_reward` | `"2"` | float (opsional) | Nilai input `TP2 (x risiko)`, format `#.##`. Backend **menghitung ulang** RR sendiri dan mengabaikan nilai ini untuk keputusan |
| `trend` | `"BULLISH"` | string (opsional) | `BULLISH` / `BEARISH` / `SIDEWAYS` |
| `confidence` | `"72"` | float (opsional) | Skor 30–100 |
| `position_size` | `"0.221975"` | float (opsional) | Estimasi qty = (modal × risiko%) ÷ jarak SL, format `#.######`. **Informasi saja** — backend menghitung qty paper sendiri |
| `time` | `"2026-07-06T13:00:00+0000"` | string (opsional) | Waktu close candle, UTC, format `yyyy-MM-dd'T'HH:mm:ssZ` (offset tanpa titik dua). Dipakai untuk cek umur sinyal |
| `strategy` | `"Smart Zone Trading Bot"` | string (opsional) | Nama tetap |
| `secret` | `"..."` | string | Hanya ada jika input Webhook secret diisi. Dibuang backend sebelum disimpan/di-log |

Contoh mentah persis seperti yang dikirim (satu baris):

```json
{"symbol":"BTCUSDT","timeframe":"60","signal":"BUY","entry":"64230.5","stop_loss":"63780.0","take_profit_1":"64906.25","take_profit_2":"65131.5","risk_reward":"2","trend":"BULLISH","confidence":"72","position_size":"0.221975","time":"2026-07-06T13:00:00+0000","strategy":"Smart Zone Trading Bot","secret":"ISI-SECRET-ANDA"}
```

### 5.2 Payload ZONE_TOUCH

| Field | Contoh | Tipe efektif | Keterangan |
|---|---|---|---|
| `type` | `"ZONE_TOUCH"` | string | Penanda alert informasi |
| `side` | `"BUY"` | string (opsional) | `BUY` = zona demand, `SELL` = zona supply |
| `symbol` | `"BTCUSDT"` | string (opsional) | — |
| `timeframe` | `"60"` | string (opsional) | — |
| `zone_top` | `"63950.0"` | float (opsional) | Batas atas zona |
| `zone_bottom` | `"63700.0"` | float (opsional) | Batas bawah zona |
| `time` | `"2026-07-06T12:47:12+0000"` | string (opsional) | Waktu sentuhan (intrabar) |
| `secret` | `"..."` | string | Sama seperti di atas |

```json
{"type":"ZONE_TOUCH","side":"BUY","symbol":"BTCUSDT","timeframe":"60","zone_top":"63950.0","zone_bottom":"63700.0","time":"2026-07-06T12:47:12+0000","secret":"ISI-SECRET-ANDA"}
```

## 6. Mengatur Webhook URL

Format URL yang harus diisikan di alert:

```text
https://<host-anda>/webhook/tradingview
```

Ketentuan dan tips:

- Path **harus** `/webhook/tradingview` — endpoint lain akan menolak/404.
- Harus URL publik, port **80/443** saja; **HTTPS sangat dianjurkan** (payload memuat secret).
- Backend harus merespons cepat (desain backend ini memang ringan); kegagalan berulang dapat membuat TradingView menonaktifkan webhook alert Anda.
- **Uji manual** sebelum mengandalkan alert:

  ```bash
  curl -X POST https://<host-anda>/webhook/tradingview \
    -H "Content-Type: application/json" \
    -d '{"symbol":"BTCUSDT","timeframe":"60","signal":"BUY","entry":"64230.5","stop_loss":"63780.0","take_profit_1":"64906.25","take_profit_2":"65131.5","risk_reward":"2","time":"2026-07-06T13:00:00+0000","strategy":"Smart Zone Trading Bot","secret":"ISI-SECRET-ANDA"}'
  ```

  Respons sukses: `{"status":"accepted","signal_id":1,"mode":"paper","paper_trade_id":1}`.
- Uji lokal: `ngrok http 8000` → pakai URL `https://xxxx.ngrok.app/webhook/tradingview`. URL ngrok gratis berubah tiap restart — perbarui alert.

## 7. Allowlist IP TradingView

Webhook TradingView dikirim dari sekumpulan IP tetap. Untuk memperketat keamanan, isi `IP_ALLOWLIST` di `backend/.env` dengan daftar berikut (dipisah koma):

```bash
IP_ALLOWLIST=52.89.214.238,34.212.75.30,54.218.53.128,52.32.178.7
```

Catatan penting:

- Daftar IP di atas adalah IP resmi yang dipublikasikan TradingView, namun **dapat berubah** — selalu verifikasi terhadap dokumentasi resmi TradingView sebelum dan sesudah mengaktifkan allowlist. Jika alert tiba-tiba ditolak dengan alasan `ip_not_allowed`, cek pembaruan daftar IP lebih dulu.
- Jika backend berada di belakang reverse proxy (Nginx/Caddy/Cloudflare), IP yang terlihat aplikasi adalah IP proxy. Set `TRUST_PROXY_HEADERS=true` **hanya** jika proxy Anda tepercaya dan **menimpa** header `X-Forwarded-For` (bukan sekadar meneruskan nilai dari klien) — jika tidak, penyerang bisa memalsukan IP-nya.
- Saat memakai ngrok, permintaan datang lewat infrastruktur ngrok — allowlist IP TradingView tidak cocok untuk skenario ini; kosongkan allowlist selama pengujian dan andalkan secret.
- Allowlist kosong = semua IP diizinkan (validasi tetap dilindungi secret + rate limit).

## 8. Keamanan Secret

- **Buat secret acak yang panjang**, contoh: `openssl rand -hex 32`. Jangan memakai kata yang bisa ditebak.
- Secret dikirim di **body** payload (bukan URL) — URL sering tercatat di access log; body tidak.
- Backend membandingkan secret secara **constant-time** (anti timing attack) dan **tidak pernah** menyimpan/me-log-nya (field dibuang sebelum payload disimpan; kolom `raw_payload` di database sudah bersih dari secret).
- Backend **menolak start** jika `WEBHOOK_SECRET` kosong, dan menolak semua request jika payload tak membawa secret yang benar (`invalid_secret`, HTTP 401).
- Jangan bagikan screenshot setting indikator yang memperlihatkan kolom Webhook secret; perlakukan seperti password.
- **Rotasi berkala**: ganti nilai di `.env`, restart backend, perbarui input Webhook secret di indikator, lalu **buat ulang alert** (alert menyimpan snapshot setting lama).
- `ADMIN_TOKEN` (untuk endpoint admin) harus **berbeda** dari `WEBHOOK_SECRET`.

## 9. Pemecahan Masalah Cepat

| Gejala | Kemungkinan penyebab |
|---|---|
| Alert terkirim tapi backend membalas 401 | Secret input indikator ≠ `WEBHOOK_SECRET`, atau alert dibuat sebelum secret diisi (buat ulang alert) |
| 409 `duplicate_signal` | Sinyal sama (simbol+arah+TF) diterima dalam `DEDUP_WINDOW_SECONDS` — normal jika dua chart/alert kembar |
| 400 `risk_reward_too_low` | `TP2 (x risiko)` di script lebih kecil dari `MIN_RISK_REWARD` backend |
| 400 `stale_signal` | Jam server melenceng atau alert tertunda melebihi `SIGNAL_MAX_AGE_SECONDS` |
| 403 `ip_not_allowed` | `IP_ALLOWLIST` aktif tapi IP pengirim tidak terdaftar (cek §7) |
| 503 `kill_switch_active` | Kill switch sedang ON — matikan via `POST /admin/kill-switch` |
| Tidak ada request sama sekali | URL webhook salah/typo, backend tidak publik, bukan port 80/443, atau sertifikat HTTPS tidak valid |

Daftar lengkap kode alasan penolakan: [docs/03-backend.md](03-backend.md#5-rantai-validasi--kode-alasan-penolakan).
