# Smart Zone Trading Bot [SZT]

> Sistem trading semi-otomatis berbasis market structure: indikator + strategy Pine Script v6 untuk TradingView, dan backend webhook FastAPI dengan validasi berlapis, paper trading, serta notifikasi Telegram.

`Pine Script v6` · `FastAPI` · `SQLite (SQLAlchemy)` · `Telegram` · `Paper Trading` · `Anti-Repaint` · `Risk Management` · `Kill Switch`

**Fitur inti:**

- 📐 **Market structure** — deteksi HH/HL/LH/LL, BOS (Break of Structure), CHoCH (Change of Character), dan arah trend.
- 🎯 **Zona entry** — order block sederhana yang terbentuk saat BOS/CHoCH, plus S/R pivot dan filter premium/discount.
- ✅ **Konfirmasi berlapis** — candle rejection/engulfing, filter EMA 50/200, ATR, volume, RSI, multi-timeframe, dan sesi.
- 🛡️ **Risk management bawaan** — SL berbasis swing/ATR, TP1 & TP2 berbasis risk-reward, batas sinyal harian, cooldown, skor confidence.
- 🔔 **Alert JSON siap webhook** — payload terstandar yang divalidasi ulang oleh backend (secret, RR hitung ulang, dedup, batas harian).
- 🧪 **Mode strategy untuk backtest** — position sizing risiko %, TP1 parsial, break-even, trailing stop, guard loss harian.
- 📄 **Paper trading + log SQLite** — semua sinyal dicatat; live trading hanyalah *template* yang **default MATI**.

---

> ## ⚠️ DISCLAIMER — BACA SEBELUM MEMAKAI
>
> **Perangkat ini adalah alat bantu analisis dan manajemen risiko, BUKAN jaminan profit.** Tidak ada strategi, indikator, atau bot yang bisa menjamin keuntungan. Hasil backtest tidak menjamin hasil di masa depan. Trading instrumen finansial (crypto, forex, saham, komoditas, indeks) mengandung risiko kerugian besar, termasuk kehilangan seluruh modal.
>
> - Sistem ini **tidak memakai martingale, averaging tanpa stop loss, atau teknik "anti-loss"** apa pun — setiap posisi selalu punya stop loss.
> - **Wajib** backtest (file strategy) dan paper trading beberapa minggu sebelum menyentuh dana riil.
> - Live trading di backend **default nonaktif** dan hanya berupa template yang harus Anda implementasikan serta pertanggungjawabkan sendiri.
> - Gunakan hanya dana yang siap Anda hilangkan. Semua keputusan trading dan akibatnya adalah tanggung jawab Anda sendiri. Ini bukan saran finansial.

---

## Struktur Repositori

```text
robot_trading/
├── README.md                          ← dokumen ini
├── docs/
│   ├── 01-pemasangan-tradingview.md   ← pemasangan + penjelasan semua input
│   ├── 02-alert-webhook.md            ← detail alert & payload webhook
│   ├── 03-backend.md                  ← detail backend FastAPI
│   ├── 04-backtest.md                 ← panduan backtest lengkap
│   └── 05-checklist-live.md           ← checklist sebelum live trading
├── pinescript/
│   ├── smart_zone_indicator.pine      ← MODE INDICATOR (sinyal + alert webhook)
│   └── smart_zone_strategy.pine       ← MODE STRATEGY (backtest di Strategy Tester)
└── backend/
    ├── .env.example                   ← contoh konfigurasi (salin menjadi .env)
    ├── requirements.txt               ← dependensi Python (sengaja minimal)
    ├── pytest.ini
    ├── app/
    │   ├── main.py                    ← aplikasi FastAPI + rantai validasi webhook
    │   ├── config.py                  ← Settings (env var, gagal-cepat saat startup)
    │   ├── schemas.py                 ← skema payload Pydantic
    │   ├── validators.py              ← validasi bisnis (fungsi murni)
    │   ├── security.py                ← secret constant-time, rate limiter, allowlist IP
    │   ├── database.py                ← engine SQLite, kv_store, kill switch
    │   ├── models.py                  ← tabel signals, paper_trades, kv_store
    │   ├── paper_trader.py            ← buku besar paper trading
    │   ├── notifier.py                ← notifikasi Telegram
    │   └── live_trader.py             ← TEMPLATE live trading (default MATI)
    └── tests/                         ← pytest untuk validator, security, webhook, admin
```

---

## Daftar Isi

1. [Arsitektur Sistem](#1-arsitektur-sistem)
2. [Pine Script: Indicator vs Strategy](#2-pine-script-indicator-vs-strategy)
3. [Penjelasan Input Setting Pine Script](#3-penjelasan-input-setting-pine-script)
4. [Cara Memasang Script di TradingView](#4-cara-memasang-script-di-tradingview)
5. [Cara Membuat Alert Webhook](#5-cara-membuat-alert-webhook)
6. [Contoh Payload JSON Alert](#6-contoh-payload-json-alert)
7. [Backend Webhook](#7-backend-webhook)
8. [Cara Menjalankan Backend](#8-cara-menjalankan-backend)
9. [Cara Menghubungkan ke Telegram](#9-cara-menghubungkan-ke-telegram)
10. [Cara Melakukan Backtest](#10-cara-melakukan-backtest)
11. [Checklist Sebelum Live Trading](#11-checklist-sebelum-live-trading)
12. [Saran Pengembangan Lanjutan & Roadmap](#12-saran-pengembangan-lanjutan--roadmap)

---

## 1. Arsitektur Sistem

Sistem terdiri dari tiga komponen yang bekerja berurutan: **indikator di TradingView** menghasilkan sinyal pada penutupan candle, **alert TradingView** mengirim payload JSON ke server Anda lewat webhook, lalu **backend FastAPI** memvalidasi ulang sinyal sebelum mencatat, mensimulasikan (paper), dan mengirim notifikasi.

```text
┌──────────────────────────────────────────────┐
│                 TradingView                  │
│   pinescript/smart_zone_indicator.pine       │
│   struktur pasar → zona → konfirmasi close   │
│   → sinyal BUY/SELL + SL/TP1/TP2             │
└──────────────────────┬───────────────────────┘
                       │ alert() → payload JSON
                       │ (HTTPS POST via webhook TradingView)
                       ▼
┌──────────────────────────────────────────────┐
│  Backend FastAPI — POST /webhook/tradingview │
│                                              │
│  Rantai validasi 10 langkah:                 │
│  rate limit → allowlist IP → kill switch →   │
│  secret → skema → validasi bisnis →          │
│  RR hitung ulang → allowlist simbol →        │
│  umur sinyal → dedup + batas harian          │
└───────────┬──────────────────────┬───────────┘
            │ DITOLAK              │ DITERIMA
            ▼                      ▼
   ┌─────────────────┐   ┌──────────────────────────────┐
   │ Log SQLite      │   │ Log SQLite (status=accepted) │
   │ (rejected +     │   │  ├─▶ Notifikasi Telegram     │
   │  alasan) +      │   │  ├─▶ Paper trading (default) │
   │ notif opsional  │   │  └─▶ Live trading (template, │
   └─────────────────┘   │      DEFAULT MATI)           │
                         └──────────────────────────────┘
```

Prinsip desain penting:

- **Anti-repaint di sumbernya** — sinyal hanya dihasilkan pada candle yang sudah close (`barstate.isconfirmed`); sinyal yang sudah tampil tidak berubah/hilang.
- **Backend tidak percaya payload** — secret dicek constant-time, risk-reward dihitung ulang dari harga, `position_size` dari payload hanya informasi (qty paper dihitung ulang server).
- **Gagal aman (fail-safe)** — kill switch persisten, batas sinyal & loss harian, live trading terkunci di balik dua sakelar (`TRADING_MODE=live` **dan** `ENABLE_LIVE_TRADING=true`) dan tetap berupa template `NotImplementedError`.

## 2. Pine Script: Indicator vs Strategy

Kedua file ada di folder [`pinescript/`](pinescript/) dan memakai **logika sinyal yang sama** (struktur → zona → konfirmasi close). Bedanya ada pada tujuan pemakaian:

| Aspek | [`smart_zone_indicator.pine`](pinescript/smart_zone_indicator.pine) | [`smart_zone_strategy.pine`](pinescript/smart_zone_strategy.pine) |
|---|---|---|
| Tipe script | `indicator()` — "SZT Bot v1" | `strategy()` — "SZT Strategy v1" |
| Tujuan | Sinyal live di chart + **alert webhook** ke backend | **Backtest** di Strategy Tester |
| Eksekusi | Sinyal dievaluasi di close candle; alert dikirim saat itu | Sinyal di close candle → order dieksekusi di **open bar berikutnya** (realistis) |
| Tracking posisi | Status virtual di panel (AKTIF / TP1 HIT / TP2 HIT / SL HIT / EXPIRED) | Posisi riil Strategy Tester: TP1 parsial, TP2, break-even, trailing |
| Risk tambahan | Batas sinyal/hari, cooldown, sinyal kadaluarsa (`timeoutBars`) | + Guard **loss harian** (`maxDailyLoss`), batas leverage, basis risiko equity/modal tetap |
| Alert | `alert()` payload JSON (BUY/SELL + ZONE_TOUCH opsional) | `alert_message` pada order (untuk alat semi-auto; opsional) |
| Panel | Dashboard sinyal & filter | Statistik backtest live: winrate, profit factor, expectancy |
| Biaya transaksi | — (tidak relevan) | Commission 0.05% + slippage 2 tick (default; sesuaikan di Properties) |

**Alur kerja yang disarankan:** backtest dengan file *strategy* → paper trading dengan file *indicator* + backend mode `paper` → baru pertimbangkan live (lihat [checklist](docs/05-checklist-live.md)).

## 3. Penjelasan Input Setting Pine Script

Nama dan nilai default di bawah diambil **persis** dari file `.pine`. Penjelasan fungsi tiap input beserta saran nilai per market ada di [docs/01-pemasangan-tradingview.md](docs/01-pemasangan-tradingview.md).

### 3.1 Input `smart_zone_indicator.pine`

**⚙️ Master**

| Input | Default | Keterangan |
|---|---|---|
| Bot aktif (kill switch) | `true` | Matikan untuk menghentikan semua sinyal & alert tanpa menghapus indikator |
| Aktifkan sinyal BUY | `true` | Izinkan sinyal long |
| Aktifkan sinyal SELL | `true` | Izinkan sinyal short |

**🏗️ Market Structure**

| Input | Default | Keterangan |
|---|---|---|
| Panjang pivot (kiri & kanan) | `5` | Bar kiri/kanan untuk konfirmasi swing; makin besar = struktur makin mayor tapi konfirmasi makin terlambat |
| Lookback order block | `15` | Berapa bar ke belakang mencari candle asal order block saat BOS/CHoCH |
| Maksimal zona per sisi | `6` | Batas jumlah zona demand/supply yang disimpan |

**📈 Filter Trend**

| Input | Default | Keterangan |
|---|---|---|
| EMA cepat | `50` | Periode EMA cepat |
| EMA lambat | `200` | Periode EMA lambat |
| Periode ATR | `14` | Basis semua perhitungan volatilitas |
| Bar pengukur kemiringan EMA | `10` | Jumlah bar untuk mengukur kemiringan EMA cepat |
| Ambang EMA datar (x ATR) | `0.4` | Jika pergerakan EMA cepat < ambang ini, market dianggap SIDEWAYS |
| Filter volume (vol > MA volume) | `true` | Hanya entry jika volume di atas rata-ratanya |
| Periode MA volume | `20` | Periode SMA volume |
| Filter RSI overbought/oversold | `false` | Blokir BUY saat RSI ≥ overbought, SELL saat RSI ≤ oversold |
| Periode RSI | `14` | Periode RSI |
| RSI overbought | `70` | Ambang overbought |
| RSI oversold | `30` | Ambang oversold |

**🎯 Zona Entry**

| Input | Default | Keterangan |
|---|---|---|
| Pakai premium/discount sebagai confluence | `true` | Long lebih dipercaya di area discount, short di premium (menambah skor confidence) |
| Izinkan range trading saat sideways | `false` | Default MATI: tidak entry saat sideways |

**✅ Validasi Entry**

| Input | Default | Keterangan |
|---|---|---|
| Mode stop loss | `Swing + Buffer ATR` | Opsi: `Swing + Buffer ATR`, `ATR Murni` |
| Buffer SL di bawah/atas swing (x ATR) | `0.3` | Jarak tambahan SL dari dasar/puncak zona-swing |
| Jarak SL mode ATR murni (x ATR) | `1.5` | Dipakai jika mode SL = ATR Murni |
| SL maksimal (x ATR) — lebih jauh = sinyal batal | `3.0` | Sinyal dibatalkan jika SL terlalu lebar |
| TP1 (x risiko) | `1.5` | Target pertama, kelipatan risiko (R) |
| TP2 (x risiko) | `2.0` | Target kedua; juga nilai `risk_reward` di payload |
| Minimal RR ke struktur berlawanan | `2.0` | Sinyal batal jika swing berlawanan terlalu dekat (TP terhalang struktur) |
| ATR minimal (% dari harga) | `0.01` | Jangan entry saat volatilitas terlalu kecil |
| Candle sinyal maksimal (x ATR) | `2.5` | Jangan entry jika candle konfirmasi terlalu besar (sudah terlambat) |
| Jarak close maksimal dari zona (x ATR) | `1.0` | Jangan kejar harga yang sudah lari jauh dari zona |

**🛡️ Risk Management**

| Input | Default | Keterangan |
|---|---|---|
| Modal akun | `10000` | Basis perhitungan estimasi ukuran posisi |
| Risiko per trade (%) | `1.0` | Persen modal yang dipertaruhkan per sinyal |
| Maksimal sinyal per hari | `5` | Batas sinyal per hari (per chart) |
| Jeda minimal antar sinyal (bar) | `5` | Cooldown antar sinyal |
| Sinyal kadaluarsa setelah (bar) | `96` | Belum kena SL/TP setelah sekian bar → status EXPIRED |
| Profil trading | `Balanced` | `Conservative` (confidence ≥ 75) / `Balanced` (≥ 60) / `Aggressive` (≥ 45) |

**🕐 Multi-Timeframe & Sesi**

| Input | Default | Keterangan |
|---|---|---|
| Konfirmasi multi-timeframe | `false` | Sinyal harus searah trend timeframe tinggi |
| Timeframe konfirmasi | `240` | Timeframe HTF (menit; 240 = H4) |
| Filter sesi trading | `false` | Hanya entry dalam jam sesi |
| Sesi aktif | `0700-2100` | Rentang jam sesi |
| Timezone sesi (kosong = timezone exchange) | `""` | Contoh: `Asia/Jakarta`, `UTC` |

**🔔 Alert & Webhook**

| Input | Default | Keterangan |
|---|---|---|
| Alert dini saat harga MASUK zona (intrabar) | `false` | Peringatan awal ZONE_TOUCH sebelum konfirmasi close |
| Webhook secret (samakan dengan backend) | `""` | Disisipkan ke payload sebagai field `secret`; harus sama dengan `WEBHOOK_SECRET` backend |

**🎨 Tampilan**

| Input | Default | Keterangan |
|---|---|---|
| Tampilkan zona entry | `true` | Kotak zona demand/supply |
| Tampilkan garis S/R pivot | `true` | Garis putus-putus S/R |
| Tampilkan label struktur & BOS/CHoCH | `true` | Label HH/HL/LH/LL, BOS, CHoCH |
| Tampilkan EMA 50 & 200 | `true` | Plot EMA |
| Tampilkan panel dashboard | `true` | Panel status di pojok chart |
| Posisi panel | `Kanan Atas` | `Kanan Atas` / `Kanan Bawah` / `Kiri Atas` / `Kiri Bawah` |
| Panjang garis sinyal (bar) | `20` | Panjang garis entry/SL/TP |
| Warna bullish | `#089981` | — |
| Warna bearish | `#f23645` | — |
| Warna garis entry | `#2962ff` | — |

### 3.2 Input tambahan/berbeda di `smart_zone_strategy.pine`

Grup Master, Market Structure, Filter Trend, Zona Entry, Validasi Entry, MTF & Sesi sama dengan indicator. Perbedaannya:

**🛡️ Risk & Money Management** (menggantikan grup Risk Management)

| Input | Default | Keterangan |
|---|---|---|
| Dasar perhitungan risiko | `Equity berjalan` | `Equity berjalan` = compounding; `Modal awal tetap` = risiko konstan |
| Modal (untuk mode 'Modal awal tetap') | `10000` | Dipakai jika basis risiko = modal tetap |
| Risiko per trade (%) | `1.0` | Persen equity/modal per posisi |
| Nilai posisi maks (x equity) | `1.0` | Batas ukuran posisi saat SL sangat ketat; 1 = tanpa leverage |
| Maksimal sinyal per hari | `5` | — |
| Maksimal loss harian (% equity) | `3.0` | Equity hari ini turun melebihi ini → tidak ada entry baru sampai besok |
| Jeda minimal antar sinyal (bar) | `5` | — |
| Profil trading | `Balanced` | Sama dengan indicator |

**🚪 Manajemen Exit** (hanya di strategy)

| Input | Default | Keterangan |
|---|---|---|
| Porsi ditutup di TP1 (%) | `50` | Persentase posisi ditutup di TP1 |
| Break-even setelah trigger | `true` | Geser SL ke harga entry setelah trigger tercapai |
| Trigger break-even (x risiko) | `1.0` | Profit mengambang (dalam R) yang memicu break-even |
| Trailing stop setelah TP1 | `false` | Trailing berbasis ATR setelah TP1 tersentuh |
| Jarak trailing (x ATR) | `2.0` | Jarak trailing dari harga |

**🧪 Rentang Backtest** (hanya di strategy)

| Input | Default | Keterangan |
|---|---|---|
| Mulai backtest | `1 Jan 2020 00:00 UTC` | Awal periode uji |
| Selesai backtest | `1 Jan 2030 00:00 UTC` | Akhir periode uji |

Catatan lain: di strategy, input `Webhook secret (untuk alert order)` berada di grup **⚙️ Master**; tidak ada input `Sinyal kadaluarsa setelah (bar)`, `Alert dini saat harga MASUK zona`, `Tampilkan garis S/R pivot`, `Panjang garis sinyal (bar)`, dan `Warna garis entry` (grup Tampilan strategy: `Tampilkan zona entry`, `Tampilkan BOS/CHoCH`, `Tampilkan EMA 50 & 200`, `Tampilkan panel statistik`, `Posisi panel`, warna bullish/bearish).

## 4. Cara Memasang Script di TradingView

Panduan lebih detail (plus profil setting dan saran timeframe): [docs/01-pemasangan-tradingview.md](docs/01-pemasangan-tradingview.md).

1. Buka [tradingview.com](https://www.tradingview.com), login, lalu buka chart simbol yang ingin dipantau (**Products → Supercharts**).
2. Klik menu **Pine Editor** di bagian bawah layar chart.
3. Hapus isi editor bawaan, lalu salin-tempel seluruh isi file [`pinescript/smart_zone_indicator.pine`](pinescript/smart_zone_indicator.pine).
4. Klik **Save** (beri nama, mis. `SZT Bot v1`), lalu klik **Add to chart**.
5. Indikator muncul di chart: zona demand/supply, label struktur (HH/HL/LH/LL, BOS/CHoCH), EMA 50/200, dan panel dashboard di pojok kanan atas.
6. Buka **Settings** (klik ⚙️ pada nama indikator di chart) untuk menyetel input — minimal isi **Webhook secret** (grup 🔔 Alert & Webhook) dengan nilai yang sama dengan `WEBHOOK_SECRET` di backend.
7. Ulangi langkah yang sama untuk [`pinescript/smart_zone_strategy.pine`](pinescript/smart_zone_strategy.pine) jika ingin backtest (buka tab **Strategy Tester** setelah ditambahkan ke chart).

> **Catatan anti-repaint:** sinyal hanya muncul di **penutupan candle**, dan label struktur (pivot) baru terkonfirmasi setelah `pivotLen` bar (default 5). Ini disengaja: sinyal sedikit lebih lambat, tetapi **tidak berubah atau hilang** setelah tampil. Penjelasan trade-off lengkap ada di [docs/01](docs/01-pemasangan-tradingview.md#4-anti-repaint-apa-yang-terlambat-dan-mengapa).

## 5. Cara Membuat Alert Webhook

Detail lengkap (opsi frekuensi, IP TradingView, keamanan secret): [docs/02-alert-webhook.md](docs/02-alert-webhook.md).

1. Pastikan indikator sudah terpasang di chart **dengan timeframe dan setting final** — alert "membekukan" setting saat dibuat.
2. Isi input **Webhook secret** pada setting indikator. Field `secret` di payload JSON diisi otomatis dari input ini — **bukan** dari kolom pesan alert.
3. Klik ikon **⏰ Alert** (atau tekan `Alt + A`).
4. Pada **Condition**, pilih indikator **`SZT Bot v1`**, lalu pilih **`Any alert() function call`**. (Wajib opsi ini — sinyal dikirim lewat fungsi `alert()` di dalam script, sehingga isi payload dan frekuensinya dikontrol script, bukan dialog alert.)
5. Pada **Expiration**, pilih *Open-ended* jika tersedia di paket Anda.
6. Buka tab **Notifications**, centang **Webhook URL**, lalu isi URL backend Anda, contoh:

   ```text
   https://domain-anda.com/webhook/tradingview
   ```

   Untuk uji lokal via ngrok: `https://xxxx.ngrok.app/webhook/tradingview`.
7. Kolom **Message** boleh dibiarkan default — untuk kondisi `Any alert() function call`, teks yang dikirim adalah payload JSON dari script, bukan isi kolom ini.
8. Klik **Create**. Satu alert ini menangani semua jenis pesan script: sinyal BUY, SELL, dan (jika diaktifkan) ZONE_TOUCH.

> Webhook TradingView membutuhkan **paket berbayar** dan hanya mengirim ke port 80/443. Gunakan **HTTPS**.

## 6. Contoh Payload JSON Alert

Payload dibuat fungsi `f_json()` di script. **Semua nilai dikirim sebagai string** (backend melakukan koersi ke angka). Alert asli dikirim satu baris; di bawah dirapikan agar terbaca.

**Sinyal BUY** (dikirim di close candle, anti-repaint):

```json
{
  "symbol": "BTCUSDT",
  "timeframe": "60",
  "signal": "BUY",
  "entry": "64230.5",
  "stop_loss": "63780.0",
  "take_profit_1": "64906.25",
  "take_profit_2": "65131.5",
  "risk_reward": "2",
  "trend": "BULLISH",
  "confidence": "72",
  "position_size": "0.221975",
  "time": "2026-07-06T13:00:00+0000",
  "strategy": "Smart Zone Trading Bot",
  "secret": "ISI-SESUAI-WEBHOOK_SECRET"
}
```

**Sinyal SELL:**

```json
{
  "symbol": "EURUSD",
  "timeframe": "15",
  "signal": "SELL",
  "entry": "1.0842",
  "stop_loss": "1.0865",
  "take_profit_1": "1.08075",
  "take_profit_2": "1.0796",
  "risk_reward": "2",
  "trend": "BEARISH",
  "confidence": "65",
  "position_size": "43478.26087",
  "time": "2026-07-06T13:15:00+0000",
  "strategy": "Smart Zone Trading Bot",
  "secret": "ISI-SESUAI-WEBHOOK_SECRET"
}
```

**Alert dini ZONE_TOUCH** (opsional, intrabar, hanya informasi — backend tidak pernah membuka posisi dari alert ini):

```json
{
  "type": "ZONE_TOUCH",
  "side": "BUY",
  "symbol": "BTCUSDT",
  "timeframe": "60",
  "zone_top": "63950.0",
  "zone_bottom": "63700.0",
  "time": "2026-07-06T12:47:12+0000",
  "secret": "ISI-SESUAI-WEBHOOK_SECRET"
}
```

Catatan format:

- `risk_reward` = nilai input `TP2 (x risiko)` (format `#.##`, jadi `2.0` tampil sebagai `"2"`).
- `time` memakai format `yyyy-MM-dd'T'HH:mm:ssZ` (UTC) — offset ditulis `+0000` tanpa titik dua; parser backend mendukung bentuk ini maupun akhiran `Z`.
- `position_size` hanya **informasi** (estimasi dari modal × risiko% ÷ jarak SL). Backend menghitung ulang qty paper sendiri.
- Field `secret` hanya disertakan jika input Webhook secret diisi, dan **tidak pernah** disimpan/di-log oleh backend.

## 7. Backend Webhook

Backend adalah aplikasi FastAPI satu proses ([`backend/app/main.py`](backend/app/main.py)) dengan penyimpanan SQLite. Perannya: **gerbang validasi** antara alert TradingView dan aksi apa pun (log, notifikasi, paper, live). Detail lengkap: [docs/03-backend.md](docs/03-backend.md).

### Tabel Endpoint

| Method | Path | Auth | Fungsi |
|---|---|---|---|
| `POST` | `/webhook/tradingview` | Field `secret` di body | Pintu masuk alert TradingView (rantai validasi lengkap) |
| `GET` | `/health` | — | Status layanan, mode trading, keadaan kill switch |
| `GET` | `/signals` | — | Daftar sinyal terbaru (query: `limit`, `offset`, `status=accepted\|rejected\|info`) |
| `GET` | `/report/paper` | — | Laporan paper trading: saldo, posisi, PnL total, win rate |
| `GET` | `/export/signals.csv` | — | Ekspor seluruh tabel signals sebagai CSV (tanpa payload mentah/secret) |
| `POST` | `/admin/kill-switch` | Header `X-Admin-Token` | Nyalakan/matikan kill switch (persisten) |
| `POST` | `/paper/close/{trade_id}` | Header `X-Admin-Token` | Tutup posisi paper manual dengan `exit_price` |

### Rantai Validasi 10 Langkah (`POST /webhook/tradingview`)

Setiap langkah gagal → sinyal **ditolak**, dicatat ke SQLite dengan alasan, dan dibalas `{"status":"rejected","reason":"..."}`.

| # | Langkah | Alasan penolakan | HTTP |
|---|---|---|---|
| 1 | Rate limit per IP (sliding window 60 detik) + allowlist IP | `rate_limited` / `ip_not_allowed` | 429 / 403 |
| 2 | Kill switch (persisten di database) | `kill_switch_active` | 503 |
| 3 | Cek `secret` (perbandingan constant-time; secret tidak pernah di-log) | `invalid_secret` | 401 |
| 4 | Validasi skema/koersi Pydantic (field wajib, angka valid) | `invalid_payload` | 422 |
| 5 | Validasi bisnis: sinyal `BUY`/`SELL`, semua harga > 0, struktur harga benar (BUY: SL < entry < TP1 ≤ TP2; SELL kebalikannya) | `invalid_signal_side` / `invalid_prices` / `invalid_price_structure` | 400 |
| 6 | **Hitung ulang** RR = \|TP2 − entry\| / \|entry − SL\| ≥ `MIN_RISK_REWARD` (nilai payload tidak dipercaya) | `risk_reward_too_low` | 400 |
| 7 | Allowlist simbol (`SYMBOL_ALLOWLIST`; kosong = semua) | `symbol_not_allowed` | 400 |
| 8 | Umur sinyal ≤ `SIGNAL_MAX_AGE_SECONDS` (waktu tak terbaca → diterima + warning) | `stale_signal` | 400 |
| 9 | Dedup: sinyal diterima dengan simbol+arah+timeframe sama dalam `DEDUP_WINDOW_SECONDS` | `duplicate_signal` | 409 |
| 10 | Batas harian: jumlah sinyal diterima (`MAX_SIGNALS_PER_DAY`) dan total rugi paper hari ini (`MAX_DAILY_LOSS_PCT`) — keduanya per hari UTC | `daily_signal_limit` / `daily_loss_limit` | 400 |

Alert bertipe `ZONE_TOUCH` diproses setelah langkah 3 (secret): hanya dicatat berstatus `info` + notifikasi opsional — **tidak pernah** membuka posisi.

Sinyal yang lolos semua langkah: disimpan `status=accepted` → mode `paper` membuka paper trade, mode `live` (+ `ENABLE_LIVE_TRADING=true`) memanggil template `live_trader` (yang sengaja berhenti di `NotImplementedError`), mode `signal_only` hanya mencatat → notifikasi Telegram dikirim.

## 8. Cara Menjalankan Backend

Butuh **Python 3.11+**.

```bash
cd backend

# 1. Buat & aktifkan virtualenv
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Pasang dependensi (produksi)
pip install -r requirements.txt
#    Untuk menjalankan test, pasang juga dependensi dev:
#    pip install -r requirements-dev.txt

# 3. Siapkan konfigurasi
cp .env.example .env
# Edit .env — WAJIB isi WEBHOOK_SECRET dan ADMIN_TOKEN
# (aplikasi menolak start jika kosong). Buat nilai acak kuat:
#   openssl rand -hex 32

# 4. Jalankan server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Verifikasi cepat:

```bash
curl http://localhost:8000/health
# {"status":"ok","mode":"paper","kill_switch":false}
```

Jalankan test (butuh `requirements-dev.txt`):

```bash
pip install -r requirements-dev.txt
pytest
```

### Menerima webhook dari TradingView (HTTPS wajib praktis)

TradingView hanya bisa mengirim ke URL publik (port 80/443). Dua opsi:

- **Uji cepat — ngrok:**

  ```bash
  ngrok http 8000
  ```

  Pakai URL `https://xxxx.ngrok.app/webhook/tradingview` di alert. Ingat: URL ngrok gratis **berubah setiap restart** — alert harus diperbarui.
- **Produksi — VPS + HTTPS otomatis (Docker Compose):** folder `backend/` sudah berisi `Dockerfile`, `docker-compose.yml`, dan `Caddyfile` untuk deploy satu perintah dengan sertifikat TLS otomatis (Let's Encrypt via Caddy). Panduan langkah demi langkah: **[docs/06-deploy-vps.md](docs/06-deploy-vps.md)**. Alternatif tanpa Docker (systemd + Caddy manual) juga ada di sana.
- **Serverless — Vercel:** backend juga siap deploy ke Vercel (`backend/api/index.py` + `backend/vercel.json`). **Catatan penting:** Vercel serverless **wajib memakai Postgres** (Vercel Postgres/Neon/Supabase), bukan SQLite, karena filesystem-nya sementara. Panduan lengkap: **[docs/07-deploy-vercel.md](docs/07-deploy-vercel.md)**.

## 9. Cara Menghubungkan ke Telegram

Notifikasi opsional — kosongkan variabel Telegram di `.env` untuk menonaktifkan. Kegagalan kirim Telegram tidak pernah menggagalkan webhook.

1. **Buat bot:** buka Telegram, cari **@BotFather**, kirim `/newbot`, ikuti instruksi (nama bot + username berakhiran `bot`). BotFather membalas dengan **token** berformat `123456789:AAF...`.
2. **Dapatkan chat_id:**
   - Cara mudah: chat **@userinfobot** → balasan berisi `Id` numerik Anda; atau
   - Kirim pesan apa pun ke bot Anda, lalu buka `https://api.telegram.org/bot<TOKEN>/getUpdates` di browser dan baca `message.chat.id`;
   - Untuk **grup**: masukkan bot ke grup, kirim pesan di grup, cek `getUpdates` — chat_id grup bernilai negatif (mis. `-100123...`).
3. **Isi `.env`:**

   ```bash
   TELEGRAM_BOT_TOKEN=123456789:AAF...
   TELEGRAM_CHAT_ID=987654321
   TELEGRAM_NOTIFY_REJECTED=false      # true = kirim juga saat sinyal ditolak
   TELEGRAM_NOTIFY_ZONE_TOUCH=false    # true = kirim juga alert info ZONE_TOUCH
   ```

4. Restart backend, kirim satu alert uji (atau `curl` payload contoh ke `/webhook/tradingview`) — pesan berformat HTML akan masuk ke chat Anda.

## 10. Cara Melakukan Backtest

Panduan lengkap dengan rumus metrik dan walk-forward: [docs/04-backtest.md](docs/04-backtest.md).

1. Pasang [`pinescript/smart_zone_strategy.pine`](pinescript/smart_zone_strategy.pine) di chart (cara sama dengan §4), lalu buka tab **Strategy Tester** di bawah chart.
2. Buka **Settings → Properties** dan sesuaikan dengan kondisi riil broker/exchange Anda:
   - **Initial capital** (default script: 10.000),
   - **Commission** (default script: 0.05% per sisi — cek fee broker Anda),
   - **Slippage** (default script: 2 tick — naikkan untuk market tipis).
   Backtest tanpa fee/slippage yang realistis hampir selalu terlalu optimis.
3. Atur **Rentang Backtest** di input script (default 2020–2030) dan pilih periode dengan data yang cukup.
4. Baca hasil di tab **Overview / Performance Summary**:
   - **Percent profitable (winrate)** — jangan dinilai sendirian; winrate rendah bisa tetap profit jika RR tinggi.
   - **Profit factor** = gross profit ÷ gross loss; > 1 berarti untung kotor melebihi rugi kotor.
   - **Max drawdown** — penurunan equity terdalam; ukuran "seberapa sakit" strategi ini secara psikologis dan finansial.
   - **Expectancy** (panel script: net profit ÷ jumlah trade) — rata-rata hasil per trade; harus positif setelah fee.
5. **Uji multi-market & multi-timeframe:** jalankan strategi di beberapa simbol (mis. BTCUSDT, ETHUSDT, EURUSD, XAUUSD) dan beberapa timeframe (M15, H1, H4). Strategi yang hanya bagus di satu kombinasi simbol+TF+parameter kemungkinan besar **overfit**.
6. **Peringatan overfitting:** semakin sering Anda menyetel parameter agar kurva equity masa lalu bagus, semakin kecil kemungkinan hasil itu terulang. Sisakan data out-of-sample yang tidak disentuh saat tuning, dan curigai hasil yang "terlalu bagus".

Target minimal yang wajar sebelum lanjut paper trading: **> 100 trade tertutup** pada kombinasi pasar/timeframe yang akan dipakai, expectancy positif setelah fee, dan drawdown yang sanggup Anda tanggung. (Ini kriteria proses, bukan janji hasil.)

## 11. Checklist Sebelum Live Trading

Versi lengkap yang bisa dicentang per kategori: [docs/05-checklist-live.md](docs/05-checklist-live.md).

1. ☐ Backtest dengan **> 100 trade tertutup** di pasar & timeframe yang akan dipakai, sudah termasuk commission + slippage realistis.
2. ☐ Hasil backtest diuji **out-of-sample** (periode yang tidak dipakai saat tuning) dan tetap masuk akal.
3. ☐ **Forward/paper test minimal 2–4 minggu** berjalan (backend mode `paper`) tanpa perubahan parameter di tengah jalan.
4. ☐ Hasil paper konsisten dengan ekspektasi backtest (bukan lebih buruk secara drastis).
5. ☐ **Risk per trade dikunci ≤ 1%** dan RR minimum dikunci (`MIN_RISK_REWARD` di backend + `minRR`/`tp2RR` di script) — tidak diubah-ubah impulsif.
6. ☐ **Batas loss harian** aktif dan angkanya disepakati (`MAX_DAILY_LOSS_PCT` backend, `Maksimal loss harian` strategy).
7. ☐ Batas sinyal harian & jendela dedup terpasang dan teruji (`MAX_SIGNALS_PER_DAY`, `DEDUP_WINDOW_SECONDS`).
8. ☐ **Kill switch diuji dua arah**: `POST /admin/kill-switch` bisa menolak sinyal (503) dan bisa dinyalakan kembali.
9. ☐ `WEBHOOK_SECRET` dan `ADMIN_TOKEN` **acak, panjang (≥ 32 byte), dan berbeda satu sama lain**; `.env` tidak pernah di-commit.
10. ☐ Endpoint webhook hanya lewat **HTTPS** dengan sertifikat valid.
11. ☐ `IP_ALLOWLIST` diisi IP resmi webhook TradingView (lihat [docs/02](docs/02-alert-webhook.md#7-allowlist-ip-tradingview)) dan diverifikasi masih berlaku.
12. ☐ API key exchange **tanpa izin withdraw**, dibatasi IP jika exchange mendukung, dan akun exchange memakai 2FA.
13. ☐ Implementasi `live_trader.py` Anda sudah **diuji penuh di testnet/sandbox** exchange, termasuk pemasangan SL/TP dan penanganan error.
14. ☐ **Mulai dengan ukuran posisi sangat kecil** (anggap dana pertama sebagai biaya belajar), dengan rencana kenaikan bertahap yang tertulis.
15. ☐ Server produksi punya **auto-restart** (systemd/docker restart policy), monitoring `/health`, dan Anda tahu apa yang terjadi pada posisi terbuka jika server mati.
16. ☐ Notifikasi Telegram berfungsi sehingga setiap eksekusi terpantau real-time.
17. ☐ Ada **jurnal trading** dan jadwal evaluasi rutin (mingguan) berbasis data `/export/signals.csv` dan `/report/paper`.
18. ☐ Anda menerima secara tertulis (untuk diri sendiri) skenario terburuk: berapa maksimal uang yang siap hilang, dan kapan sistem dimatikan permanen.

**Jangan live jika ada satu pun butir yang belum tercentang.**

## 12. Saran Pengembangan Lanjutan & Roadmap

### v1 — yang ada sekarang

- Indikator TradingView: market structure (HH/HL/LH/LL, BOS/CHoCH), zona order block, filter EMA50/200 + ATR + volume + RSI + MTF + sesi, sinyal BUY/SELL dengan SL/TP1/TP2, skor confidence, panel dashboard, alert JSON, anti-repaint.
- Strategy Tester: position sizing risiko %, TP1 parsial, break-even, trailing, guard loss harian, panel statistik.
- Backend FastAPI: rantai validasi 10 langkah, log SQLite, notifikasi Telegram, paper trading (close manual), ekspor CSV, kill switch, rate limit, allowlist IP/simbol, template live trading (default mati).

### v2 — otomasi & observabilitas

- **Auto-resolve paper trade** via harga live exchange (websocket/polling ccxt): SL/TP1/TP2 tereksekusi otomatis di buku besar paper, bukan close manual.
- **Dashboard web** (baca-saja dulu): kurva equity paper, daftar sinyal + alasan penolakan, status kill switch.
- **Multi-strategy**: field `strategy` di payload dipakai untuk routing aturan validasi/risiko per strategi.
- **Deteksi FVG (Fair Value Gap)** sebagai jenis zona tambahan di Pine Script.
- **Filter berita manual / preset sesi**: jendela "jangan trading" yang bisa dijadwalkan (mis. rilis data berdampak tinggi), preset sesi per market.
- **Laporan mingguan Telegram** otomatis: ringkasan sinyal, winrate paper, PnL, pelanggaran limit.

### v3 — eksekusi penuh & riset

- **Eksekusi live ccxt penuh dengan reconciliation**: order nyata + verifikasi status order/posisi terhadap exchange, retry idempoten, penanganan partial fill, sinkronisasi saat restart.
- **Multi-account / multi-exchange** dengan konfigurasi risiko per akun.
- **Optimasi parameter walk-forward** terotomasi (rolling in-sample/out-of-sample) alih-alih tuning manual.
- **Machine-learning scoring opsional**: model klasifikasi sebagai filter tambahan di atas skor confidence — tetap dengan SL wajib dan batas risiko yang sama, dan hanya setelah v1/v2 terbukti stabil secara operasional.

---

*Dokumentasi: [docs/](docs/) · Lisensi & tanggung jawab pemakaian ada pada pengguna. Bukan saran finansial.*
