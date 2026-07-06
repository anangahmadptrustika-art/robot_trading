"""Rantai validasi bisnis: fungsi murni yang mengembalikan (ok, alasan)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

# Pola offset zona waktu tanpa titik dua, mis. "+0000" atau "-0530".
_OFFSET_TANPA_KOLON = re.compile(r"([+-]\d{2})(\d{2})$")

SIDES = {"BUY", "SELL"}


def check_signal_side(signal: str) -> tuple[bool, str]:
    """Sinyal harus BUY atau SELL."""
    if signal in SIDES:
        return True, ""
    return False, "invalid_signal_side"


def check_prices_positive(
    entry: float, stop_loss: float, take_profit_1: float, take_profit_2: float
) -> tuple[bool, str]:
    """Semua harga wajib lebih besar dari nol."""
    if all(p > 0 for p in (entry, stop_loss, take_profit_1, take_profit_2)):
        return True, ""
    return False, "invalid_prices"


def check_price_structure(
    signal: str,
    entry: float,
    stop_loss: float,
    take_profit_1: float,
    take_profit_2: float,
) -> tuple[bool, str]:
    """Struktur harga: BUY perlu SL < entry < TP1 <= TP2; SELL kebalikannya."""
    if signal == "BUY":
        ok = stop_loss < entry < take_profit_1 <= take_profit_2
    elif signal == "SELL":
        ok = stop_loss > entry > take_profit_1 >= take_profit_2
    else:
        ok = False
    return (True, "") if ok else (False, "invalid_price_structure")


def compute_risk_reward(entry: float, stop_loss: float, take_profit_2: float) -> Optional[float]:
    """Hitung ulang RR = |TP2 - entry| / |entry - SL|; None jika risiko nol."""
    risiko = abs(entry - stop_loss)
    if risiko <= 0:
        return None
    return abs(take_profit_2 - entry) / risiko


def check_min_risk_reward(rr: Optional[float], min_rr: float) -> tuple[bool, str]:
    """RR hasil hitung ulang tidak boleh di bawah ambang minimum."""
    if rr is None or rr < min_rr:
        return False, "risk_reward_too_low"
    return True, ""


def check_symbol_allowed(symbol: str, allowlist: set[str]) -> tuple[bool, str]:
    """Allowlist simbol; set kosong berarti semua simbol diizinkan."""
    if not allowlist or symbol.upper() in allowlist:
        return True, ""
    return False, "symbol_not_allowed"


def parse_signal_time(raw: Optional[str]) -> Optional[datetime]:
    """Parse waktu sinyal ISO-8601; dukung akhiran 'Z' dan offset '+0000'.

    Mengembalikan datetime aware UTC, atau None jika tidak bisa di-parse.
    """
    if not raw:
        return None
    s = str(raw).strip()
    if s.upper().endswith("Z"):
        s = s[:-1] + "+00:00"
    s = _OFFSET_TANPA_KOLON.sub(r"\1:\2", s)
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)  # tanpa zona waktu → anggap UTC
    return dt.astimezone(timezone.utc)


def check_signal_age(
    raw_time: Optional[str],
    max_age_seconds: int,
    now: Optional[datetime] = None,
) -> tuple[bool, str]:
    """Tolak sinyal yang lebih tua dari max_age_seconds (0 = nonaktif).

    Waktu yang tidak bisa di-parse TIDAK menolak sinyal — kembalikan
    (True, "unparseable_time") agar pemanggil mencatat peringatan.
    """
    if max_age_seconds <= 0:
        return True, ""
    dt = parse_signal_time(raw_time)
    if dt is None:
        return True, "unparseable_time"
    now = now or datetime.now(timezone.utc)
    umur = (now - dt).total_seconds()
    if umur > max_age_seconds:
        return False, "stale_signal"
    return True, ""
