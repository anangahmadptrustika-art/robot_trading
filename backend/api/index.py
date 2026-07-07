"""Entrypoint Vercel Serverless Function.

Vercel menjalankan aplikasi ASGI `app` di berkas ini. Semua rute diarahkan
ke fungsi ini via `vercel.json` (rewrites).

Catatan penting untuk Vercel:
  - Database WAJIB Postgres serverless (Vercel Postgres/Neon/Supabase), BUKAN
    SQLite — filesystem serverless bersifat sementara & read-only. Set
    DATABASE_URL di Environment Variables project Vercel.
  - Set juga WEBHOOK_SECRET & ADMIN_TOKEN di Environment Variables; validasi
    di bawah akan menggagalkan cold start bila belum diisi (fail-fast).
"""

from __future__ import annotations

import os
import sys

# Pastikan paket 'app' (di folder backend/) dapat diimpor saat berjalan di Vercel.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_settings, validate_startup_settings  # noqa: E402
from app.main import app  # noqa: E402  (di-expose sebagai ASGI app untuk Vercel)

# Gagal cepat di cold start bila konfigurasi wajib belum diisi di dashboard Vercel.
validate_startup_settings(get_settings())

__all__ = ["app"]
