# 04 — Panduan Backtest

> Dokumen ini memandu backtest `pinescript/smart_zone_strategy.pine` di Strategy Tester TradingView: menyiapkan properti yang realistis, membaca metrik dengan rumusnya, menentukan jumlah sampel minimal, melakukan walk-forward sederhana, menghindari kesalahan umum, dan membandingkan profil risiko.

**Ingat tujuan backtest:** memvalidasi dan **membuang** strategi/parameter yang jelek — bukan mencari kurva equity terindah, dan bukan janji profit. Hasil masa lalu tidak menjamin hasil masa depan.

---

## 1. Persiapan

1. Pasang `smart_zone_strategy.pine` di chart ([docs/01 §2](01-pemasangan-tradingview.md#2-langkah-pemasangan-pine-editor)) dan buka tab **Strategy Tester**.
2. Buka **Settings → Properties** dan samakan dengan kondisi riil Anda:

   | Properti | Default script | Yang harus Anda lakukan |
   |---|---|---|
   | Initial capital | 10.000 | Samakan dengan rencana modal riil |
   | Commission | 0.05% per sisi | Isi fee taker/maker broker/exchange Anda (spot crypto umumnya ~0.1%; futures lebih kecil; forex biasanya lewat spread — pertimbangkan slippage lebih besar sebagai gantinya) |
   | Slippage | 2 tick | Naikkan untuk market tipis / timeframe kecil |
   | Pyramiding | 0 | Biarkan 0 (satu posisi pada satu waktu) |

3. Atur **🧪 Rentang Backtest** di input script (default 1 Jan 2020 – 1 Jan 2030) sesuai ketersediaan data. Riwayat bar yang bisa dimuat bergantung paket TradingView dan timeframe.
4. Pastikan periode uji mencakup **beragam kondisi market**: trending naik, turun, dan sideways. Strategi trend-following yang hanya diuji di masa bull akan tampak jauh lebih bagus dari kenyataannya.

## 2. Membaca Metrik (dengan Rumus)

Sumber angka: tab **Overview** dan **Performance Summary** Strategy Tester, plus panel statistik bawaan script (winrate, profit factor, expectancy, total trades).

### Winrate (Percent Profitable)

```text
winrate = jumlah trade profit ÷ jumlah trade tertutup × 100%
```

Winrate **tidak berdiri sendiri**. Sistem RR 1:2 dengan winrate 40% bisa lebih menguntungkan daripada winrate 70% dengan RR 1:0.5. Selalu baca bersama RR/expectancy.

### Profit Factor (PF)

```text
PF = gross profit ÷ gross loss
```

- PF > 1: total untung kotor melebihi total rugi kotor.
- Sebagai gambaran umum, PF di kisaran 1.2–2.0 pada sampel besar lebih dapat dipercaya daripada PF > 3 pada sampel kecil (yang biasanya kebetulan atau overfit). Ini heuristik pembacaan, bukan target yang dijanjikan.

### Max Drawdown (MDD)

```text
MDD = maksimum dari (puncak equity − lembah equity sesudahnya) ÷ puncak equity × 100%
```

Ukuran "seberapa dalam sakitnya". Perhatikan juga **durasi** drawdown (berapa lama equity di bawah puncak). Aturan praktis: asumsikan drawdown live bisa lebih buruk dari backtest; jika MDD backtest saja sudah tidak sanggup Anda tanggung, turunkan risiko per trade atau buang strateginya.

### Expectancy (harapan per trade)

Dua bentuk yang setara:

```text
Expectancy = net profit ÷ jumlah trade tertutup          ← yang ditampilkan panel script

Expectancy = (winrate × rata-rata profit trade menang)
           − ((1 − winrate) × rata-rata rugi trade kalah)
```

Harus **positif setelah commission + slippage**. Expectancy kecil yang positif bisa habis dimakan fee riil yang sedikit lebih besar dari asumsi — beri margin keamanan.

### Metrik pendukung

- **Total trades / jumlah sampel** — dasar signifikansi (lihat §3).
- **Avg trade, Avg win/Avg loss** — memverifikasi RR riil vs RR desain (TP1 parsial + break-even menurunkan rata-rata win per trade dibanding `tp2RR` teoretis; itu normal).
- **Sharpe/Sortino** (jika tersedia) — konsistensi hasil, bukan hanya totalnya.

## 3. Berapa Sampel Minimal?

- Targetkan **lebih dari 100 trade tertutup** per kombinasi simbol+timeframe yang dinilai. Di bawah itu, statistik didominasi kebetulan: dengan 30 trade, selisih beberapa trade beruntung bisa mengubah winrate belasan persen.
- Sistem ini **selektif by design** (filter berlapis + batas sinyal harian), jadi mencapai 100+ trade mungkin butuh periode bertahun-tahun atau agregasi beberapa simbol. Keduanya sah — asal setiap kombinasi tetap diuji dengan parameter yang **sama**.
- Jika data tidak cukup untuk 100+ trade: perlakukan hasil sebagai indikasi lemah, perpanjang periode, tambah simbol sejenis, atau turunkan timeframe **untuk pengujian** (sambil sadar perilaku antar timeframe bisa berbeda).

## 4. Walk-Forward Sederhana (In-Sample / Out-of-Sample)

Tujuan: memastikan parameter tidak hanya bagus di data yang dipakai untuk menyetelnya.

1. **Bagi data** memakai input `Mulai backtest` / `Selesai backtest`. Contoh dengan data 2020–2025:
   - In-sample (IS): 2020-01-01 → 2023-12-31 — boleh dipakai menyetel parameter.
   - Out-of-sample (OOS): 2024-01-01 → 2025-12-31 — **tidak disentuh** selama tuning.
2. **Tuning di IS saja**: pilih parameter (profil, pivotLen, filter, TP/SL) berdasarkan hasil IS. Batasi jumlah kombinasi yang dicoba — makin banyak kombinasi dicoba, makin besar peluang menemukan yang "bagus karena kebetulan".
3. **Uji sekali di OOS** dengan parameter final. Bandingkan:
   - PF dan expectancy OOS masih positif dan tidak jauh di bawah IS → parameter cukup tangguh.
   - OOS jauh lebih buruk / negatif → overfit; kembali ke desain, bukan sekadar menyetel ulang di OOS (itu membuat OOS menjadi IS baru).
4. **Versi bergulir (opsional):** ulangi dengan jendela bergeser (IS 2 tahun → OOS 6 bulan, geser 6 bulan, dst.) dan nilai konsistensi seluruh potongan OOS.
5. Fase **paper trading** ([docs/03 §7](03-backend.md#7-cara-kerja-paper-trading)) adalah out-of-sample sejati terakhir sebelum dana riil.

## 5. Kesalahan Umum

| Kesalahan | Kenapa menyesatkan | Penangkal |
|---|---|---|
| **Overfitting** — menyetel parameter sampai kurva equity masa lalu mulus | Anda memodelkan noise, bukan pola; live langsung meleset | Sedikit parameter yang diubah, walk-forward (§4), curiga pada hasil "terlalu bagus" |
| **Cherry-picking timeframe/simbol** — melaporkan hanya kombinasi terbaik | Satu kombinasi bagus di antara 20 yang dicoba ≈ kebetulan | Tetapkan matriks uji **sebelum** mulai (mis. 4 simbol × 3 TF) dan laporkan semuanya |
| **Mengabaikan fee & slippage** | Strategi berfrekuensi tinggi bisa berubah dari untung ke rugi hanya karena fee | Isi commission & slippage realistis (bahkan sedikit lebih buruk) di Properties |
| **Survivorship bias** — hanya menguji aset yang terbukti naik (BTC, saham unggulan hari ini) | Aset yang mati/delisting tidak ikut diuji; hasil terlalu optimis | Sertakan aset yang stagnan/turun; untuk saham, sadari keterbatasan data delisted di TradingView |
| **Periode uji seragam** — hanya masa bull (mis. 2020–2021 crypto) | Strategi tampak hebat karena pasarnya, bukan sistemnya | Wajib mencakup bear & sideways |
| **Sampel kecil dianggap bukti** | Varians mendominasi | ≥ 100 trade (§3) |
| **Mengubah parameter di tengah forward test** | Statistik campuran dua sistem tidak bermakna | Kunci parameter; perubahan = mulai hitung ulang |
| **Membandingkan hasil intrabar vs close-confirmed** | Sistem ini anti-repaint (sinyal di close; eksekusi di open bar berikutnya) — jangan "menghitung ulang" seolah entry di harga sentuhan zona | Terima keterlambatan sebagai bagian sistem ([docs/01 §4](01-pemasangan-tradingview.md#4-anti-repaint-apa-yang-terlambat-dan-mengapa)) |

Catatan teknis Strategy Tester: deteksi TP1/BE/trailing memakai high/low bar (tanpa data tick). Pada bar yang menyentuh SL dan TP sekaligus, urutan intrabar tidak diketahui — script memilih asumsi konservatif, tetapi tetap perlakukan hasil bar-magnifier/tick sebagai pembanding bila paket Anda mendukungnya.

## 6. Menguji Multi-Market & Multi-Timeframe

Tentukan matriks di awal, misalnya:

| | M15 | H1 | H4 |
|---|---|---|---|
| BTCUSDT | ✔ | ✔ | ✔ |
| ETHUSDT | ✔ | ✔ | ✔ |
| EURUSD | ✔ | ✔ | ✔ |
| XAUUSD | ✔ | ✔ | ✔ |

Dengan **parameter yang sama** per baris market (boleh berbeda antar market sesuai saran [docs/01 §3](01-pemasangan-tradingview.md#3-penjelasan-semua-input), tapi konsisten di seluruh sel yang dibandingkan). Yang dicari bukan "semua sel hijau", melainkan **pola yang masuk akal** (mis. bekerja di market trending, lemah saat sideways) dan tidak ada ketergantungan ekstrem pada satu sel.

## 7. Membandingkan Profil Risiko

Uji ketiga nilai input `Profil trading` pada data dan properti yang identik, catat:

| Metrik | Conservative (≥75) | Balanced (≥60) | Aggressive (≥45) |
|---|---|---|---|
| Total trades | … | … | … |
| Winrate | … | … | … |
| Profit factor | … | … | … |
| Expectancy/trade | … | … | … |
| Max drawdown | … | … | … |
| Net profit % | … | … | … |

Cara membaca: Conservative biasanya menghasilkan trade lebih sedikit — pastikan sampelnya masih bermakna; Aggressive menambah frekuensi tapi menyertakan setup lemah — lihat apakah expectancy per trade turun lebih cepat daripada kenaikan frekuensinya. Bandingkan juga variasi exit (`Porsi ditutup di TP1`, break-even, trailing) dan `Dasar perhitungan risiko` (equity berjalan vs modal tetap) dengan metode yang sama: **satu perubahan per eksperimen**.

## 8. Sesudah Backtest

1. Kunci parameter final (tulis di jurnal — simbol, TF, semua input yang diubah dari default).
2. Jalankan **paper trading 2–4 minggu** minimum lewat backend ([docs/03](03-backend.md)) tanpa mengubah parameter.
3. Bandingkan hasil paper dengan ekspektasi backtest; baru lanjut ke [checklist live](05-checklist-live.md) jika konsisten.
