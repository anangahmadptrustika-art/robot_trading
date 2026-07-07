"""Utilitas keamanan: cek secret constant-time, rate limiter, allowlist IP."""

from __future__ import annotations

import hmac
import threading
import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import Request


def constant_time_equals(provided: str, expected: str) -> bool:
    """Bandingkan dua string dalam waktu konstan (anti timing attack)."""
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def check_webhook_secret(provided: Optional[object], expected: str) -> bool:
    """Cek secret webhook; gagal jika kosong/tidak ada/bukan string/salah."""
    if not expected:
        # Konfigurasi server tidak boleh membuka pintu tanpa secret.
        return False
    if not isinstance(provided, str) or not provided:
        return False
    return constant_time_equals(provided, expected)


class SlidingWindowRateLimiter:
    """Rate limiter sliding-window sederhana di memori, per kunci (IP klien).

    Menyimpan timestamp request dalam deque; request lama di luar jendela
    dibuang setiap kali dicek. Cukup untuk satu proses uvicorn.
    """

    def __init__(self, window_seconds: float = 60.0) -> None:
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, now: Optional[float] = None) -> bool:
        """True jika request masih di bawah `limit` dalam jendela berjalan."""
        if limit <= 0:
            return False
        ts = now if now is not None else time.monotonic()
        batas_bawah = ts - self._window
        with self._lock:
            antrian = self._hits[key]
            while antrian and antrian[0] <= batas_bawah:
                antrian.popleft()
            if len(antrian) >= limit:
                return False
            antrian.append(ts)
            return True

    def reset(self) -> None:
        """Kosongkan seluruh riwayat (dipakai saat testing)."""
        with self._lock:
            self._hits.clear()


def is_ip_allowed(client_ip: str, allowlist: set[str]) -> bool:
    """Cek allowlist IP; set kosong berarti semua IP diizinkan."""
    if not allowlist:
        return True
    return client_ip in allowlist


def get_client_ip(request: Request, trust_proxy_headers: bool) -> str:
    """Ambil IP klien; hormati X-Forwarded-For (nilai pertama) hanya jika
    TRUST_PROXY_HEADERS aktif."""
    if trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            pertama = forwarded.split(",")[0].strip()
            if pertama:
                return pertama
    if request.client is not None and request.client.host:
        return request.client.host
    return "unknown"
