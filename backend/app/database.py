"""Helper engine/session SQLAlchemy dan penyimpanan key-value sederhana."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import datetime, timezone

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

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


def init_engine(database_url: str) -> Engine:
    """Inisialisasi (ulang) engine dan session factory dari URL database."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    connect_args = {}
    if database_url.startswith("sqlite"):
        # TestClient/uvicorn bisa memakai thread berbeda dari thread pembuat koneksi.
        connect_args["check_same_thread"] = False
    _engine = create_engine(database_url, connect_args=connect_args, future=True)
    _session_factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    logger.info("Engine database diinisialisasi: %s", database_url)
    return _engine


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
        raise RuntimeError("Session factory belum diinisialisasi. Panggil init_engine() dulu.")
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
