# 05 — Checklist Sebelum Live Trading

> Checklist yang bisa dicentang sebelum mengaktifkan live trading — dikelompokkan per kategori; **jangan live jika ada satu pun butir yang belum tercentang**, dan ingat: mencentang semuanya pun bukan jaminan profit, hanya jaminan bahwa Anda tidak melewatkan pekerjaan rumah yang wajib.

Cara pakai: salin file ini (atau centang langsung di fork Anda), isi tanggal/nilai pada butir yang meminta angka, dan simpan sebagai arsip keputusan.

---

## A. Strategi

- [ ] Backtest final memakai `pinescript/smart_zone_strategy.pine` dengan **commission + slippage realistis** (Properties Strategy Tester), bukan default kosong.
- [ ] Jumlah sampel backtest **> 100 trade tertutup** pada kombinasi simbol+timeframe yang akan dipakai live.
- [ ] Periode backtest mencakup kondisi **trending naik, turun, dan sideways** (bukan hanya masa bull).
- [ ] Parameter diuji **out-of-sample / walk-forward** ([docs/04 §4](04-backtest.md#4-walk-forward-sederhana-in-sample--out-of-sample)) dan hasil OOS tetap positif/masuk akal.
- [ ] Expectancy per trade **positif setelah fee**, dengan margin keamanan (bukan tipis di ambang nol).
- [ ] Max drawdown backtest **sanggup saya tanggung** secara finansial dan psikologis, dengan asumsi live bisa lebih buruk.
- [ ] **Forward/paper test minimal 2–4 minggu** selesai (backend mode `paper`) tanpa mengubah parameter di tengah jalan.
- [ ] Hasil paper trading **konsisten** dengan ekspektasi backtest (tidak menyimpang drastis ke arah buruk).
- [ ] Seluruh parameter final **dikunci dan didokumentasikan** (simbol, timeframe, semua input yang diubah dari default, tanggal penguncian): `____________`.

## B. Teknis / Infrastruktur

- [ ] Backend berjalan di server yang stabil (VPS/host 24 jam), **bukan** laptop pribadi/ngrok.
- [ ] Service **auto-restart** terpasang (systemd `Restart=always` / docker restart policy) dan sudah diuji dengan mematikan proses secara paksa.
- [ ] Endpoint webhook dilayani lewat **HTTPS** dengan sertifikat valid (reverse proxy Nginx/Caddy — [docs/03 §9](03-backend.md#9-deployment-singkat)).
- [ ] `GET /health` dipantau uptime monitor, dan saya menerima peringatan jika mati.
- [ ] Alert TradingView aktif, kondisi **`Any alert() function call`**, URL benar (`/webhook/tradingview`), dan **tidak kedaluwarsa** dalam waktu dekat.
- [ ] Alur end-to-end teruji: alert TradingView → backend `accepted` → notifikasi Telegram diterima.
- [ ] Dedup dan batas harian teruji (`DEDUP_WINDOW_SECONDS`, `MAX_SIGNALS_PER_DAY`) — alert kembar benar-benar ditolak 409.
- [ ] Jam server sinkron (NTP) — validasi `SIGNAL_MAX_AGE_SECONDS` bergantung waktu yang benar.
- [ ] Backup otomatis berkas SQLite (`szt_signals.db`) terjadwal.
- [ ] Saya tahu **apa yang terjadi pada posisi terbuka jika server mati** (SL/TP terpasang di exchange, bukan hanya di memori server) dan sudah menuliskan prosedur pemulihannya.

## C. Keamanan

- [ ] `WEBHOOK_SECRET` acak dan panjang (≥ 32 byte, mis. `openssl rand -hex 32`) — bukan kata yang bisa ditebak.
- [ ] `ADMIN_TOKEN` **berbeda** dari `WEBHOOK_SECRET`, sama kuatnya.
- [ ] `.env` **tidak pernah di-commit** ke git (cek riwayat repo, bukan hanya `.gitignore`).
- [ ] `IP_ALLOWLIST` diisi IP resmi webhook TradingView dan diverifikasi masih berlaku ([docs/02 §7](02-alert-webhook.md#7-allowlist-ip-tradingview)).
- [ ] `TRUST_PROXY_HEADERS` hanya `true` jika reverse proxy tepercaya **menimpa** `X-Forwarded-For`.
- [ ] API key exchange: izin **withdraw DINONAKTIFKAN**, dibatasi ke IP server (jika didukung), dan tidak pernah dibagikan/di-screenshot.
- [ ] Akun exchange memakai **2FA**; email akun exchange juga diamankan.
- [ ] **Kill switch diuji dua arah** dalam 7 hari terakhir: ON menolak sinyal (503 `kill_switch_active`), OFF memulihkan; token admin tersimpan di tempat yang bisa saya akses cepat dari ponsel.
- [ ] Implementasi `live_trader.py` saya sudah direview: tidak ada rahasia di kode, qty dihitung dari risiko riil akun (bukan `position_size` payload), dan sudah **lulus uji di testnet/sandbox** termasuk pemasangan SL/TP dan penanganan error.

## D. Risk Management

- [ ] **Risk per trade dikunci** ≤ 1% (disarankan mulai 0.25–0.5%) dan tercatat: `____ %`.
- [ ] **RR minimum dikunci**: `MIN_RISK_REWARD` backend = `____`, konsisten dengan `TP2 (x risiko)` dan `Minimal RR ke struktur berlawanan` di script.
- [ ] **Batas loss harian aktif** dan angkanya disepakati: `MAX_DAILY_LOSS_PCT` backend = `____ %`, `Maksimal loss harian (% equity)` strategy = `____ %`.
- [ ] Batas sinyal harian masuk akal untuk gaya trading saya (`MAX_SIGNALS_PER_DAY` backend, `Maksimal sinyal per hari` script).
- [ ] **Mulai dengan ukuran posisi sangat kecil** — nominal live awal: `____` (anggap sebagai biaya belajar), dengan rencana kenaikan bertahap **tertulis** (mis. naik hanya setelah N trade & evaluasi positif).
- [ ] Total dana di akun trading adalah **uang yang siap hilang seluruhnya** — tidak ada dana kebutuhan hidup/darurat.
- [ ] Tidak ada mekanisme martingale/averaging tanpa SL yang saya tambahkan sendiri — setiap posisi selalu punya stop loss.
- [ ] Batas kerugian total tertulis yang memicu **penghentian permanen** sistem: `____` (nominal/%).

## E. Psikologis / Operasional

- [ ] Saya berkomitmen **tidak meng-override** sinyal secara impulsif (menahan SL, membesarkan posisi, revenge trading). Intervensi manual hanya lewat prosedur (kill switch + catatan alasan).
- [ ] **Jurnal trading** berjalan: setiap trade dicatat (screenshot, alasan, hasil), dibantu `GET /export/signals.csv` dan `GET /report/paper`.
- [ ] Jadwal **evaluasi rutin** ditetapkan (mis. tiap Minggu malam): review sinyal ditolak vs diterima, PnL, pelanggaran limit, kondisi server.
- [ ] **Rencana saat drawdown tertulis**: pada drawdown `____ %` saya akan (kurangi ukuran / jeda / matikan) — diputuskan sekarang, bukan saat panik.
- [ ] Rencana untuk **berita berdampak tinggi**: saya tahu cara cepat menonaktifkan (kill switch backend atau input `Bot aktif` di indikator) menjelang rilis besar.
- [ ] Ekspektasi realistis: saya menerima bahwa **rentetan loss adalah bagian normal** dari sistem apa pun, dan tidak akan menilai sistem dari 5–10 trade.
- [ ] Orang terdekat/partner (jika relevan) mengetahui aktivitas ini dan batas dananya.
- [ ] Saya sudah membaca ulang [DISCLAIMER di README](../README.md#%EF%B8%8F-disclaimer--baca-sebelum-memakai) dan menerima bahwa seluruh risiko dan keputusan adalah tanggung jawab saya sendiri.

---

**Tanggal review checklist:** `__________` · **Ditinjau ulang setiap:** disarankan tiap bulan atau setiap ada perubahan sistem/parameter.
