# 07 — Deploy Backend ke Vercel (Serverless)

Panduan men-deploy backend Smart Zone Trading Bot ke **Vercel** sebagai
Serverless Function. Cocok untuk mode **semi-auto** (webhook → validasi →
Telegram + paper trading) tanpa mengurus server/HTTPS sendiri.

> ⚠️ **Wajib baca dulu — perbedaan penting dengan VPS:**
> Vercel itu **serverless** (fungsi hidup sesaat, filesystem sementara &
> read-only). **SQLite tidak bisa dipakai** di sini karena datanya akan hilang.
> Anda **harus** memakai **Postgres serverless** (Vercel Postgres / Neon /
> Supabase). Kode sudah disiapkan untuk ini — Anda hanya mengarahkan
> `DATABASE_URL` ke Postgres.
>
> Jika Anda ingin tetap pakai SQLite & selalu-hidup, gunakan jalur VPS di
> [docs/06-deploy-vps.md](06-deploy-vps.md) — sering kali lebih pas untuk bot
> stateful seperti ini.

Berkas yang relevan (sudah ada di repo): `backend/api/index.py`,
`backend/vercel.json`, `backend/requirements.txt`.

---

## Langkah 1 — Siapkan database Postgres serverless

Pilih salah satu (semuanya punya paket gratis):

- **Vercel Postgres** — di dashboard Vercel: tab **Storage → Create Database →
  Postgres**. Setelah dibuat, Vercel menyediakan variabel `POSTGRES_URL`
  (pooled) secara otomatis untuk project yang terhubung.
- **Neon** (https://neon.tech) — buat project, salin **connection string**
  (yang berakhiran `?sslmode=require`). Gunakan endpoint **pooled**.
- **Supabase** (https://supabase.com) — Settings → Database → Connection string
  (mode **Session/Transaction pooler**).

Simpan connection string-nya; ini akan menjadi `DATABASE_URL`.

> Kode otomatis menormalkan skema `postgres://` / `postgresql://` menjadi
> `postgresql+psycopg://` (driver psycopg v3), jadi Anda cukup menempelkan URL
> apa adanya.

---

## Langkah 2 — Impor repo ke Vercel

1. Push repo ini ke GitHub (sudah, di branch Anda).
2. Di dashboard Vercel: **Add New… → Project → Import** repo GitHub Anda.
3. **PENTING — set Root Directory ke `backend`** (Settings → Build & Output,
   atau saat import). Backend berada di subfolder, bukan root repo.
4. Framework Preset: **Other** (biarkan Vercel mendeteksi fungsi Python).

---

## Langkah 3 — Set Environment Variables

Project Settings → **Environment Variables** (untuk Production, dan Preview jika
perlu). Isi minimal:

| Variabel | Nilai | Wajib |
|---|---|---|
| `WEBHOOK_SECRET` | string acak kuat (`openssl rand -hex 32`) | ✅ |
| `ADMIN_TOKEN` | string acak kuat, berbeda dari di atas | ✅ |
| `DATABASE_URL` | connection string Postgres dari Langkah 1 (pakai **pooled**) | ✅ |
| `TRADING_MODE` | `paper` | ✅ |
| `TELEGRAM_BOT_TOKEN` | token @BotFather | opsional |
| `TELEGRAM_CHAT_ID` | chat/grup tujuan | opsional |
| `TRUST_PROXY_HEADERS` | `true` (Vercel di depan fungsi) | disarankan |
| `MIN_RISK_REWARD`, `MAX_SIGNALS_PER_DAY`, dst | lihat `.env.example` | opsional |

> Jika `WEBHOOK_SECRET`/`ADMIN_TOKEN` belum diisi, fungsi **sengaja gagal saat
> cold start** (fail-fast) — ini fitur keamanan, bukan bug.

> Jika pakai **Vercel Postgres** yang otomatis mengisi `POSTGRES_URL`, tambahkan
> juga `DATABASE_URL` yang menunjuk ke nilai yang sama (kode ini membaca
> `DATABASE_URL`, bukan `POSTGRES_URL`).

---

## Langkah 4 — Deploy

Klik **Deploy** (atau `git push` — Vercel auto-deploy tiap push). Setelah
selesai Anda dapat URL seperti `https://nama-project.vercel.app`.

Tabel database dibuat **otomatis** saat request pertama (lazy init).

Uji:

```bash
curl https://nama-project.vercel.app/health
# {"status":"ok","mode":"paper","kill_switch":false}
```

Uji webhook (ganti waktu dengan waktu UTC sekarang):

```bash
curl -X POST https://nama-project.vercel.app/webhook/tradingview \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"BTCUSDT","timeframe":"15","signal":"BUY","entry":"43250.5",
       "stop_loss":"42980.0","take_profit_1":"43656.2","take_profit_2":"43791.5",
       "risk_reward":"2.0","trend":"BULLISH","confidence":"78",
       "time":"2026-07-07T01:00:00+0000","strategy":"Smart Zone Trading Bot",
       "secret":"ISI_WEBHOOK_SECRET_ANDA"}'
# {"status":"accepted", ...}
```

---

## Langkah 5 — Hubungkan alert TradingView

Webhook URL di alert TradingView:

```
https://nama-project.vercel.app/webhook/tradingview
```

Selebihnya sama seperti [docs/02-alert-webhook.md](02-alert-webhook.md).

---

## Keterbatasan serverless (penting dipahami)

| Aspek | Catatan |
|---|---|
| **Rate limiter** | Rate limiter di-memori bersifat **per-instance** dan reset saat cold start, jadi kurang efektif di serverless. Andalkan `WEBHOOK_SECRET` + `SYMBOL_ALLOWLIST` sebagai gerbang utama. |
| **Cold start** | Setelah idle, webhook pertama bisa lebih lambat (beberapa ratus ms–beberapa detik). Untuk sinyal per candle, ini biasanya tidak masalah. |
| **Timeout fungsi** | Diset `maxDuration: 30` detik di `vercel.json` (cukup untuk validasi + Telegram). |
| **State persisten** | Log sinyal, paper trade, saldo, & kill switch kini di **Postgres** → aman lintas invocation. |
| **IP allowlist** | IP sumber terlihat via `X-Forwarded-For` (butuh `TRUST_PROXY_HEADERS=true`). IP TradingView bisa berubah; lihat catatan di docs/02. |
| **Live trading (ccxt)** | Bisa jalan, tapi menambah `ccxt` memperbesar cold start; untuk eksekusi order yang andal, jalur selalu-hidup (VPS) lebih disarankan daripada serverless. |

---

## Deploy cepat via CLI (alternatif)

```bash
npm i -g vercel
cd backend
vercel            # ikuti prompt; set Root Directory = . (karena sudah di backend)
vercel env add WEBHOOK_SECRET
vercel env add ADMIN_TOKEN
vercel env add DATABASE_URL
vercel --prod
```

---

## Checklist keamanan (Vercel)

- [ ] `WEBHOOK_SECRET` & `ADMIN_TOKEN` acak, kuat, berbeda.
- [ ] `DATABASE_URL` memakai Postgres **pooled** + `sslmode=require`.
- [ ] Environment Variables diisi di scope **Production** (dan Preview bila dipakai).
- [ ] `TRADING_MODE=paper` dulu; uji kill switch via `POST /admin/kill-switch` + header `X-Admin-Token`.
- [ ] `TRUST_PROXY_HEADERS=true`.
- [ ] `.env` tidak pernah ikut ter-commit (sudah di `.gitignore`).
- [ ] Uji `GET /health` mengembalikan 200 sebelum menghubungkan alert.
