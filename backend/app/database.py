"""Helper engine/session SQLAlchemy dan penyimpanan key-value sederhana."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import datetime, timezone

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)

# Kunci kv_store yang dipakai aplikasi.
KV_PAPER_BALANCE = "paper_balance"
KV_KILL_SWITCH = "kill_switch"


class Base(DeclarativeBase):
    """Base deklaratif untuk semua model."""


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def utcnow_naive() -> datetime:
    """Waktu UTC sekarang tanpa tzinfo (konsisten untuk kolom SQLite)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_db_url(url: str) -> str:
    """Samakan skema URL Postgres agar cocok dengan driver psycopg (v3).

    Vercel Postgres / Neon / Supabase sering memberi skema 'postgres://' atau
    'postgresql://'. SQLAlchemy butuh dialek+driver eksplisit; kita pakai
    'postgresql+psycopg://' (psycopg v3, tercantum di requirements.txt).
    """
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def init_engine(database_url: str) -> Engine:
    """Inisialisasi (ulang) engine dan session factory dari URL database."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    url = _normalize_db_url(database_url)
    connect_args: dict = {}
    engine_kwargs: dict = {"future": True}
    if url.startswith("sqlite"):
        # TestClient/uvicorn bisa memakai thread berbeda dari thread pembuat koneksi.
        connect_args["check_same_thread"] = False
    else:
        # Serverless (mis. Vercel): jangan tahan koneksi antar invocation dan
        # deteksi koneksi yang sudah mati sebelum dipakai.
        engine_kwargs["poolclass"] = NullPool
        engine_kwargs["pool_pre_ping"] = True
    _engine = create_engine(url, connect_args=connect_args, **engine_kwargs)
    _session_factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    # Catat skema saja — JANGAN log URL penuh (bisa memuat kredensial).
    logger.info("Engine database diinisialisasi (%s).", url.split("://", 1)[0])
    return _engine


def ensure_initialized(database_url: str) -> None:
    """Pastikan engine + tabel siap. Aman dipanggil berulang.

    Dipakai jalur serverless (Vercel) yang tidak menjalankan lifespan, di mana
    inisialisasi harus terjadi malas pada request pertama.
    """
    if _session_factory is not None:
        return
    init_engine(database_url)
    create_tables()


def get_engine() -> Engine:
    """Ambil engine aktif; error jelas jika belum diinisialisasi."""
    if _engine is None:
        raise RuntimeError("Engine database belum diinisialisasi. Panggil init_engine() dulu.")
    return _engine


def create_tables() -> None:
    """Buat semua tabel yang terdaftar pada Base."""
    from app import models  # noqa: F401  # registrasi model sebelum create_all

    Base.metadata.create_all(bind=get_engine())


def get_db() -> Iterator[Session]:
    """Dependency FastAPI: satu session per request, selalu ditutup."""
    if _session_factory is None:
        # Jalur serverless (Vercel) tanpa lifespan: inisialisasi malas dari settings.
        from app.config import get_settings

        ensure_initialized(get_settings().DATABASE_URL)
    assert _session_factory is not None  # dipastikan oleh ensure_initialized
    db = _session_factory()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Helper kv_store (persistensi saldo paper & status kill switch)
# ---------------------------------------------------------------------------

def get_kv(db: Session, key: str) -> str | None:
    """Baca nilai kv_store; None jika kunci belum ada."""
    from app.models import KVStore

    row = db.execute(select(KVStore).where(KVStore.key == key)).scalar_one_or_none()
    return row.value if row is not None else None


def set_kv(db: Session, key: str, value: str) -> None:
    """Tulis (upsert) nilai kv_store dan commit."""
    from app.models import KVStore

    row = db.execute(select(KVStore).where(KVStore.key == key)).scalar_one_or_none()
    if row is None:
        db.add(KVStore(key=key, value=value))
    else:
        row.value = value
    db.commit()


def is_kill_switch_on(db: Session) -> bool:
    """Status kill switch dari kv_store (default: mati)."""
    return get_kv(db, KV_KILL_SWITCH) == "1"


def set_kill_switch(db: Session, enabled: bool) -> None:
    """Simpan status kill switch secara persisten."""
    set_kv(db, KV_KILL_SWITCH, "1" if enabled else "0")
