# 01 — Pemasangan di TradingView & Penjelasan Semua Input

> Dokumen ini memandu pemasangan `pinescript/smart_zone_indicator.pine` dan `pinescript/smart_zone_strategy.pine` di TradingView, menjelaskan fungsi setiap input beserta saran nilai per market, perilaku anti-repaint, profil trading, dan pemilihan timeframe.

**Disclaimer:** semua saran nilai di dokumen ini adalah **titik awal eksperimen**, bukan resep profit. Selalu validasi lewat backtest ([docs/04-backtest.md](04-backtest.md)) dan paper trading sebelum dipakai dengan dana riil.

---

## 1. Prasyarat

- Akun TradingView (webhook alert membutuhkan **paket berbayar**; cek fitur paket Anda saat ini).
- File script dari repo ini:
  - `pinescript/smart_zone_indicator.pine` — sinyal live + alert webhook.
  - `pinescript/smart_zone_strategy.pine` — backtest di Strategy Tester.
- Data simbol yang memiliki **volume** jika filter volume ingin dipakai (lihat catatan per market di §3).

## 2. Langkah Pemasangan (Pine Editor)

1. Buka chart simbol tujuan di TradingView (Supercharts).
2. Klik **Pine Editor** di panel bawah.
3. Klik menu di pojok editor → **Create new indicator** (atau langsung kosongkan editor).
4. Salin **seluruh** isi `pinescript/smart_zone_indicator.pine` dan tempel ke editor (timpa semua isi lama).
5. Klik **Save**, beri nama (mis. `SZT Bot v1`).
6. Klik **Add to chart**. Jika ada error kompilasi, pastikan seluruh file tersalin utuh dari baris pertama (`//@version=6`).
7. Buka **Settings** indikator (ikon ⚙️) dan setel:
   - **🔔 Alert & Webhook → Webhook secret** = nilai `WEBHOOK_SECRET` backend (wajib jika memakai webhook).
   - Input lain sesuai market/timeframe (lihat §3 dan §5).
8. Untuk **strategy**: ulangi langkah 3–6 dengan isi `smart_zone_strategy.pine`, lalu buka tab **Strategy Tester** di bawah chart.

Yang tampil di chart setelah pemasangan indicator:

| Elemen | Keterangan |
|---|---|
| Kotak hijau/merah | Zona demand/supply (order block); memudar abu-abu saat tertembus |
| Label `HH` `HL` `LH` `LL` `SH` `SL` | Swing yang sudah terkonfirmasi (muncul terlambat `pivotLen` bar — lihat §4) |
| Label `BOS` / `CHoCH` | Break of Structure / Change of Character (diukur pada harga close) |
| Garis oranye & biru | EMA 50 dan EMA 200 |
| Garis + label Entry/SL/TP1/TP2 | Paket level saat sinyal muncul |
| Label `BUY ▲ xx%` / `SELL ▼ xx%` | Sinyal beserta skor confidence |
| Panel pojok | Dashboard: trend, status sinyal, level, sinyal hari ini, filter 6-poin |

## 3. Penjelasan Semua Input

Kolom "Saran per market" memakai singkatan: **C** = crypto, **F** = forex, **G** = gold/XAUUSD, **S** = saham, **I** = indeks. Nilai tanpa keterangan market berlaku umum.

### 3.1 ⚙️ Master

| Input | Default | Fungsi | Saran |
|---|---|---|---|
| Bot aktif (kill switch) | `true` | Mematikan semua sinyal & alert tanpa menghapus indikator | Matikan saat berita berdampak tinggi atau saat evaluasi |
| Aktifkan sinyal BUY | `true` | Izinkan sinyal long | Matikan salah satu jika hanya ingin searah bias tertentu |
| Aktifkan sinyal SELL | `true` | Izinkan sinyal short | Untuk **S** (saham spot tanpa fasilitas short): matikan SELL |

### 3.2 🏗️ Market Structure

| Input | Default | Fungsi | Saran |
|---|---|---|---|
| Panjang pivot (kiri & kanan) | `5` | Bar kiri+kanan untuk mengonfirmasi swing. Makin besar = struktur makin "mayor", tapi label & BOS makin terlambat | Umum 5. Scalping M5: 3–4. Swing H4–D1: 5–8. **F/G** yang banyak noise: 6–7 |
| Lookback order block | `15` | Berapa bar ke belakang mencari candle asal (order block) saat BOS/CHoCH | 10–20; jarang perlu diubah |
| Maksimal zona per sisi | `6` | Batas zona demand/supply tersimpan (zona tertua dihapus) | 4–8; kecilkan jika chart terasa penuh |

### 3.3 📈 Filter Trend

| Input | Default | Fungsi | Saran |
|---|---|---|---|
| EMA cepat | `50` | Trend jangka menengah | Biarkan 50 kecuali riset khusus |
| EMA lambat | `200` | Trend jangka panjang; butuh ± 200 bar riwayat sebelum stabil | Biarkan 200 |
| Periode ATR | `14` | Basis semua ukuran volatilitas (SL, buffer, filter candle) | 14 standar |
| Bar pengukur kemiringan EMA | `10` | Jendela pengukuran kemiringan EMA cepat | 8–15 |
| Ambang EMA datar (x ATR) | `0.4` | Pergerakan EMA cepat < ambang → market dianggap SIDEWAYS (tanpa sinyal, kecuali `allowRange`) | Naikkan (0.5–0.6) = lebih banyak dianggap sideways; turunkan (0.2–0.3) = lebih longgar |
| Filter volume (vol > MA volume) | `true` | Entry hanya saat volume di atas rata-rata | **C/S/I-futures**: ON. **F/G** CFD (tick volume): boleh OFF, atau ON sebagai proxy aktivitas |
| Periode MA volume | `20` | Periode SMA volume | 20 standar |
| Filter RSI overbought/oversold | `false` | Blokir BUY saat RSI ≥ overbought, SELL saat RSI ≤ oversold | Nyalakan di market yang sering mean-revert; biarkan OFF untuk trend-following murni |
| Periode RSI | `14` | Periode RSI | 14 |
| RSI overbought | `70` | Ambang atas | 70–80 |
| RSI oversold | `30` | Ambang bawah | 20–30 |

### 3.4 🎯 Zona Entry

| Input | Default | Fungsi | Saran |
|---|---|---|---|
| Pakai premium/discount sebagai confluence | `true` | Long dinilai lebih baik di bawah equilibrium (discount), short di atasnya (premium); menambah bobot skor confidence | Biarkan ON |
| Izinkan range trading saat sideways | `false` | Default MATI: tidak ada entry saat sideways. ON = boleh trading pantulan range (long di bawah equilibrium, short di atas) | Hanya untuk yang paham range trading; naikkan profil ke Conservative jika dinyalakan |

### 3.5 ✅ Validasi Entry

| Input | Default | Fungsi | Saran |
|---|---|---|---|
| Mode stop loss | `Swing + Buffer ATR` | `Swing + Buffer ATR`: SL di bawah/atas dasar zona (atau swing terdekat jika hanya sedikit di luar zona) + buffer. `ATR Murni`: SL berjarak tetap `slAtrMult` × ATR dari entry | Swing + Buffer untuk struktur; ATR Murni untuk konsistensi ukuran |
| Buffer SL di bawah/atas swing (x ATR) | `0.3` | Ruang ekstra anti "liquidity sweep" | 0.2–0.5; **G** yang suka spike: 0.4–0.5 |
| Jarak SL mode ATR murni (x ATR) | `1.5` | Dipakai hanya pada mode ATR Murni | 1.0–2.0 |
| SL maksimal (x ATR) — lebih jauh = sinyal batal | `3.0` | Sinyal dibatalkan jika SL terlalu lebar (risiko per unit terlalu besar) | 2.5–3.5 |
| TP1 (x risiko) | `1.5` | Target pertama dalam kelipatan risiko (R) | 1.0–2.0 |
| TP2 (x risiko) | `2.0` | Target akhir; juga dikirim sebagai `risk_reward` di payload. **Jaga ≥ `MIN_RISK_REWARD` backend (default 1.5)** agar sinyal tidak ditolak server | 2.0–3.0 |
| Minimal RR ke struktur berlawanan | `2.0` | Batalkan sinyal jika swing berlawanan terdekat memotong jalur target | 1.5–2.5 |
| ATR minimal (% dari harga) | `0.01` | Blokir entry saat volatilitas terlalu kecil (spread/fee jadi dominan) | **C** M15–H1: 0.05–0.15. **F** M15: 0.02–0.05. **G**: 0.05–0.10. **S** D1: 0.5–1.5. **I**: 0.05–0.15 |
| Candle sinyal maksimal (x ATR) | `2.5` | Tolak candle konfirmasi raksasa (entry sudah telat, SL jauh) | 2.0–3.0 |
| Jarak close maksimal dari zona (x ATR) | `1.0` | Jangan kejar harga yang sudah lari jauh dari zona | 0.5–1.5 |

### 3.6 🛡️ Risk Management (indicator)

| Input | Default | Fungsi | Saran |
|---|---|---|---|
| Modal akun | `10000` | Basis estimasi ukuran posisi di panel & payload | Isi sesuai akun Anda |
| Risiko per trade (%) | `1.0` | Persen modal per sinyal; qty estimasi = (modal × risiko%) ÷ jarak SL | 0.25–1.0; pemula 0.25–0.5 |
| Maksimal sinyal per hari | `5` | Rem overtrading per chart | Scalping 5–8; swing 1–3 |
| Jeda minimal antar sinyal (bar) | `5` | Cooldown antar sinyal | 3–10 |
| Sinyal kadaluarsa setelah (bar) | `96` | Sinyal belum kena SL/TP setelah sekian bar → EXPIRED, bot boleh cari sinyal baru | 96 bar M15 = 24 jam; sesuaikan TF |
| Profil trading | `Balanced` | Ambang skor confidence — lihat §6 | Mulai dari Balanced |

Catatan: estimasi posisi di panel **belum** memperhitungkan leverage, ukuran kontrak/lot, dan fee — hitung ulang di broker Anda.

### 3.7 🕐 Multi-Timeframe & Sesi

| Input | Default | Fungsi | Saran |
|---|---|---|---|
| Konfirmasi multi-timeframe | `false` | Sinyal harus searah trend EMA timeframe tinggi (bar HTF yang sudah close — anti-lookahead) | ON untuk sinyal lebih sedikit tapi lebih selaras trend besar |
| Timeframe konfirmasi | `240` | HTF dalam menit (`240` = H4, `60` = H1, `D` = daily) | Chart M5→`60`; M15→`240`; H1→`D`; H4→`W` |
| Filter sesi trading | `false` | Hanya entry dalam jam sesi | **F/G/I**: ON, sesuaikan sesi likuid. **C**: opsional |
| Sesi aktif | `0700-2100` | Rentang jam sesi (format HHMM-HHMM) | London+NY (UTC): `0700-2100`. WIB: `1400-0400` dengan timezone `Asia/Jakarta` perlu diverifikasi manual |
| Timezone sesi (kosong = timezone exchange) | `""` | Contoh: `Asia/Jakarta`, `UTC`, `America/New_York` | Isi eksplisit agar tidak tergantung exchange |

### 3.8 🔔 Alert & Webhook (indicator)

| Input | Default | Fungsi | Saran |
|---|---|---|---|
| Alert dini saat harga MASUK zona (intrabar) | `false` | Kirim alert `ZONE_TOUCH` begitu harga menyentuh zona — **informasi dini, bukan sinyal**; boleh berulang antar bar dan tidak menunggu close | ON hanya jika ingin bersiap manual sebelum konfirmasi |
| Webhook secret (samakan dengan backend) | `""` | Disisipkan ke payload sebagai field `secret`; backend menolak alert tanpa secret yang benar | **Wajib diisi** jika memakai backend |

### 3.9 🎨 Tampilan (indicator)

| Input | Default | Fungsi |
|---|---|---|
| Tampilkan zona entry | `true` | Kotak zona demand/supply |
| Tampilkan garis S/R pivot | `true` | Garis dotted S/R dari pivot |
| Tampilkan label struktur & BOS/CHoCH | `true` | Label swing & break |
| Tampilkan EMA 50 & 200 | `true` | Plot EMA |
| Tampilkan panel dashboard | `true` | Panel status |
| Posisi panel | `Kanan Atas` | `Kanan Atas` / `Kanan Bawah` / `Kiri Atas` / `Kiri Bawah` |
| Panjang garis sinyal (bar) | `20` | Panjang garis Entry/SL/TP ke kanan |
| Warna bullish / bearish / garis entry | `#089981` / `#f23645` / `#2962ff` | Kustomisasi warna |

### 3.10 Input khusus `smart_zone_strategy.pine`

Grup lain identik dengan indicator; berikut yang berbeda/tambahan:

**🛡️ Risk & Money Management**

| Input | Default | Fungsi | Saran |
|---|---|---|---|
| Dasar perhitungan risiko | `Equity berjalan` | `Equity berjalan` = compounding (risiko ikut membesar/mengecil); `Modal awal tetap` = nominal risiko konstan | Bandingkan keduanya di backtest |
| Modal (untuk mode 'Modal awal tetap') | `10000` | Basis risiko mode modal tetap | — |
| Risiko per trade (%) | `1.0` | Persen equity/modal per posisi | 0.25–1.0 |
| Nilai posisi maks (x equity) | `1.0` | Plafon nilai posisi saat SL sangat ketat; 1 = tanpa leverage | Naikkan hanya jika akun Anda memang berleverage dan Anda paham konsekuensinya |
| Maksimal loss harian (% equity) | `3.0` | Equity harian turun melebihi ini → stop entry sampai hari berikutnya | 2–5 |
| Profil trading / Maks sinyal per hari / Jeda antar sinyal | `Balanced` / `5` / `5` | Sama dengan indicator | — |

**🚪 Manajemen Exit**

| Input | Default | Fungsi | Saran |
|---|---|---|---|
| Porsi ditutup di TP1 (%) | `50` | Persen posisi yang ditutup di TP1; sisanya lari ke TP2 | 30–70 |
| Break-even setelah trigger | `true` | SL digeser ke entry setelah profit mengambang mencapai trigger (atau setelah TP1) | ON untuk mengurangi trade menang→kalah |
| Trigger break-even (x risiko) | `1.0` | Ambang profit (R) pemicu break-even | 0.8–1.5 |
| Trailing stop setelah TP1 | `false` | Setelah TP1: SL mengikuti harga sejauh `trailAtrMult` × ATR | ON untuk market trending kuat |
| Jarak trailing (x ATR) | `2.0` | Jarak trailing | 1.5–3.0 |

**🧪 Rentang Backtest**: `Mulai backtest` (default 1 Jan 2020 UTC) dan `Selesai backtest` (default 1 Jan 2030 UTC).

Perbedaan lain: `Webhook secret (untuk alert order)` ada di grup Master; strategy **tidak** punya `Sinyal kadaluarsa setelah (bar)` dan `Alert dini saat harga MASUK zona`; grup Tampilan lebih ringkas (`Tampilkan zona entry`, `Tampilkan BOS/CHoCH`, `Tampilkan EMA 50 & 200`, `Tampilkan panel statistik`, `Posisi panel`, dua warna).

## 4. Anti-Repaint: Apa yang "Terlambat" dan Mengapa

Repaint = sinyal/gambar yang berubah atau hilang setelah tampil — musuh utama evaluasi jujur. Script ini dirancang agar **apa yang sudah tampil tidak berubah**, dengan konsekuensi keterlambatan yang disengaja:

| Mekanisme | Cara kerja | Konsekuensi ("terlambat"-nya) |
|---|---|---|
| Sinyal hanya di close candle | Seluruh logika sinyal berjalan dalam `barstate.isconfirmed` | Sinyal muncul di akhir bar, bukan saat harga pertama menyentuh zona. Di H1 artinya bisa "telat" hingga 1 jam dari sentuhan pertama |
| Konfirmasi pivot `pivotLen` bar | `ta.pivothigh/pivotlow(pivotLen, pivotLen)` — sebuah puncak/lembah baru diakui setelah `pivotLen` bar berikutnya tidak melampauinya | Label HH/HL/LH/LL muncul **`pivotLen` bar setelah** puncak/lembah terjadi (default 5 bar). Ini benar secara logika: sebelum itu, kita memang belum tahu bahwa itu swing |
| BOS diukur ke pivot terkonfirmasi, pakai close | Break dihitung dari `close` yang menembus pivot yang sudah sah, bukan wick intrabar | Break "palsu" oleh wick tidak dihitung; deteksi BOS menunggu close |
| MTF anti-lookahead | `request.security(..., lookahead_on)` tetapi membaca nilai HTF indeks `[1]` (bar HTF yang **sudah close**) | Konfirmasi HTF tertinggal maksimal satu bar HTF; tidak pernah membaca data masa depan |
| Alert dini ZONE_TOUCH | Satu-satunya bagian intrabar (di luar `isconfirmed`), default OFF | Bisa "berubah pikiran" (harga masuk zona lalu batal) — karena itu berlabel informasi, bukan sinyal |

**Trade-off yang harus Anda terima:** entry rata-rata sedikit lebih jauh dari titik ideal dibanding sistem intrabar, tetapi sinyal historis di chart = sinyal yang benar-benar akan Anda terima secara live. Untuk sistem yang dievaluasi dengan backtest, "terlambat tapi pasti" selalu lebih baik daripada "cepat tapi berubah-ubah".

Perlu diketahui juga: EMA 200 membutuhkan riwayat ratusan bar — di chart dengan riwayat pendek, filter trend belum stabil.

## 5. Saran Timeframe

| Gaya | Timeframe chart | Catatan |
|---|---|---|
| Scalping | M5–M15 | Sinyal lebih banyak, noise lebih banyak, fee/slippage lebih terasa. Pakai `Timeframe konfirmasi` = 60–240, pertimbangkan `pivotLen` 3–4, filter sesi ON. Butuh minAtrPct yang pas agar tidak entry saat mati volume |
| Intraday | M15–H1 | Titik tengah yang umum untuk sistem ini. Default input dirancang di sekitar zona ini. `Sinyal kadaluarsa` 96 bar M15 ≈ 24 jam |
| Swing | H4–D1 | Sinyal jarang (bisa hanya beberapa per bulan per simbol) tapi struktur lebih bermakna. Naikkan `pivotLen` ke 5–8, MTF ke `D`/`W`, turunkan `Maksimal sinyal per hari` ke 1–3 |

Ingat: keterlambatan pivot diukur dalam **bar timeframe chart** — 5 bar di M5 = 25 menit, di D1 = 5 hari. Pilih timeframe yang keterlambatannya masih masuk akal untuk rencana Anda.

## 6. Profil Trading: Conservative / Balanced / Aggressive

Input `Profil trading` menentukan ambang minimal **skor confidence** sinyal (skor 30–100 dihitung dari kesegaran BOS, kualitas candle konfirmasi, volume, RSI, premium/discount, dan MTF):

| Profil | Ambang confidence | Karakter | Saran pendamping |
|---|---|---|---|
| Conservative | ≥ 75 | Sinyal paling jarang, hanya confluence terbaik | `useMtf` ON, risiko 0.25–0.5%, `Maksimal sinyal per hari` 2–3 |
| Balanced | ≥ 60 | Default; kompromi frekuensi vs kualitas | Risiko ≤ 1% |
| Aggressive | ≥ 45 | Sinyal terbanyak, termasuk setup lemah | **Bukan** alasan menaikkan risiko per trade; justru pertimbangkan 0.5% karena frekuensi naik. Wajib backtest terpisah |

Profil hanya mengubah ambang skor — semua filter keras (trend, zona, RR ke struktur, SL maksimal, dsb.) tetap berlaku di ketiganya.

## 7. Langkah Berikutnya

1. Backtest dengan file strategy — [docs/04-backtest.md](04-backtest.md).
2. Pasang alert webhook — [docs/02-alert-webhook.md](02-alert-webhook.md).
3. Jalankan backend mode paper — [docs/03-backend.md](03-backend.md).
4. Sebelum live: [docs/05-checklist-live.md](05-checklist-live.md).
