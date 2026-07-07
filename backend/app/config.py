"""Konfigurasi aplikasi berbasis pydantic-settings.

Semua nilai dibaca dari environment variable / berkas .env.
Tidak ada rahasia yang di-hardcode di sini.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_VALID_TRADING_MODES = {"paper", "live", "signal_only"}


class Settings(BaseSettings):
    """Kumpulan pengaturan aplikasi (lihat .env.example untuk penjelasan)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Keamanan ---
    WEBHOOK_SECRET: str = ""
    ADMIN_TOKEN: str = ""

    # --- Telegram ---
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_NOTIFY_REJECTED: bool = False
    TELEGRAM_NOTIFY_ZONE_TOUCH: bool = False

    # --- Mode trading ---
    TRADING_MODE: str = "paper"  # paper | live | signal_only
    ENABLE_LIVE_TRADING: bool = False
    EXCHANGE_ID: str = ""
    EXCHANGE_API_KEY: str = ""
    EXCHANGE_API_SECRET: str = ""

    # --- Paper trading & manajemen risiko ---
    PAPER_START_BALANCE: float = 10000
    RISK_PER_TRADE_PCT: float = 1.0
    MIN_RISK_REWARD: float = 1.5
    MAX_SIGNALS_PER_DAY: int = 10
    MAX_DAILY_LOSS_PCT: float = 3.0

    # --- Filter sinyal ---
    DEDUP_WINDOW_SECONDS: int = 300
    SIGNAL_MAX_AGE_SECONDS: int = 300
    SYMBOL_ALLOWLIST: str = ""

    # --- Jaringan ---
    IP_ALLOWLIST: str = ""
    TRUST_PROXY_HEADERS: bool = False
    RATE_LIMIT_PER_MINUTE: int = 30

    # --- Lain-lain ---
    DATABASE_URL: str = "sqlite:///./szt_signals.db"
    LOG_LEVEL: str = "INFO"

    @field_validator("TRADING_MODE")
    @classmethod
    def _validasi_trading_mode(cls, v: str) -> str:
        """Pastikan TRADING_MODE salah satu dari: paper, live, signal_only."""
        mode = v.strip().lower()
        if mode not in _VALID_TRADING_MODES:
            raise ValueError(
                "TRADING_MODE tidak valid: "
                f"'{v}'. Pilihan yang benar: paper, live, atau signal_only."
            )
        return mode

    def symbol_allowlist_set(self) -> set[str]:
        """Allowlist simbol sebagai set huruf besar; kosong = izinkan semua."""
        return {s.strip().upper() for s in self.SYMBOL_ALLOWLIST.split(",") if s.strip()}

    def ip_allowlist_set(self) -> set[str]:
        """Allowlist IP sebagai set; kosong = izinkan semua IP."""
        return {s.strip() for s in self.IP_ALLOWLIST.split(",") if s.strip()}


def validate_startup_settings(settings: Settings) -> None:
    """Gagal cepat saat startup jika konfigurasi wajib belum diisi.

    Dipanggil sekali di lifespan aplikasi sebelum menerima request.
    """
    kosong = [
        nama
        for nama, nilai in (
            ("WEBHOOK_SECRET", settings.WEBHOOK_SECRET),
            ("ADMIN_TOKEN", settings.ADMIN_TOKEN),
        )
        if not nilai.strip()
    ]
    if kosong:
        raise RuntimeError(
            "KONFIGURASI TIDAK LENGKAP: "
            + " dan ".join(kosong)
            + " masih kosong. Salin .env.example menjadi .env lalu isi nilai "
            "rahasia yang kuat sebelum menjalankan aplikasi."
        )


@lru_cache
def get_settings() -> Settings:
    """Ambil instance Settings (di-cache; cache_clear() dipakai saat testing)."""
    return Settings()
