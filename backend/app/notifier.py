"""Notifikasi Telegram via httpx.

Kegagalan pengiriman HANYA dicatat di log dan ditelan — webhook harus
tetap sukses walau Telegram sedang bermasalah.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.config import Settings
from app.models import PaperTrade, Signal

logger = logging.getLogger(__name__)

_TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"
_TIMEOUT_SECONDS = 10.0


def send_telegram(settings: Settings, text: str) -> bool:
    """Kirim pesan HTML ke Telegram; False (tanpa exception) jika gagal/nonaktif."""
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        logger.debug("Telegram tidak dikonfigurasi; notifikasi dilewati.")
        return False
    try:
        response = httpx.post(
            _TELEGRAM_URL.format(token=settings.TELEGRAM_BOT_TOKEN),
            json={
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return True
    except Exception:  # noqa: BLE001 — sengaja ditelan agar webhook tetap sukses
        logger.warning("Gagal mengirim notifikasi Telegram.", exc_info=True)
        return False


def _fmt(nilai: Optional[float]) -> str:
    """Format angka untuk pesan; strip nol berlebih."""
    if nilai is None:
        return "-"
    return f"{nilai:,.8f}".rstrip("0").rstrip(".")


def format_signal_accepted(signal: Signal, mode: str, trade: Optional[PaperTrade]) -> str:
    """Susun pesan HTML (Bahasa Indonesia) untuk sinyal yang diterima."""
    baris = [
        f"📊 <b>Sinyal {signal.signal} Diterima</b>",
        f"<b>Simbol:</b> {signal.symbol} ({signal.timeframe})",
        f"<b>Entry:</b> {_fmt(signal.entry)}",
        f"<b>Stop Loss:</b> {_fmt(signal.stop_loss)}",
        f"<b>TP1:</b> {_fmt(signal.take_profit_1)} | <b>TP2:</b> {_fmt(signal.take_profit_2)}",
        f"<b>RR (hitung ulang):</b> {_fmt(signal.risk_reward_computed)}",
        f"<b>Tren:</b> {signal.trend or '-'} | <b>Keyakinan:</b> {_fmt(signal.confidence)}%",
        f"<b>Mode:</b> {mode}",
    ]
    if trade is not None:
        baris.append(
            f"<b>Paper trade #{trade.id}:</b> qty {_fmt(trade.qty)}, "
            f"risiko {_fmt(trade.risk_amount)}"
        )
    baris.append("⚠️ <i>Bukan saran finansial. Selalu kelola risiko Anda sendiri.</i>")
    return "\n".join(baris)


def format_signal_rejected(payload: dict[str, Any], reason: str) -> str:
    """Susun pesan HTML untuk sinyal yang ditolak."""
    return (
        "🚫 <b>Sinyal Ditolak</b>\n"
        f"<b>Simbol:</b> {payload.get('symbol', '-')}"
        f" | <b>Sinyal:</b> {payload.get('signal', '-')}\n"
        f"<b>Alasan:</b> {reason}"
    )


def format_zone_touch(payload: dict[str, Any]) -> str:
    """Susun pesan HTML untuk alert informasi ZONE_TOUCH."""
    return (
        "👀 <b>Zona Tersentuh</b> (informasi saja, tanpa posisi)\n"
        f"<b>Simbol:</b> {payload.get('symbol', '-')} ({payload.get('timeframe', '-')})\n"
        f"<b>Sisi:</b> {payload.get('side', '-')}\n"
        f"<b>Zona:</b> {payload.get('zone_bottom', '-')} – {payload.get('zone_top', '-')}"
    )


def notify_signal_accepted(
    settings: Settings, signal: Signal, mode: str, trade: Optional[PaperTrade]
) -> None:
    """Kirim notifikasi sinyal diterima (kegagalan ditelan)."""
    send_telegram(settings, format_signal_accepted(signal, mode, trade))


def notify_signal_rejected(settings: Settings, payload: dict[str, Any], reason: str) -> None:
    """Kirim notifikasi penolakan jika TELEGRAM_NOTIFY_REJECTED aktif."""
    if settings.TELEGRAM_NOTIFY_REJECTED:
        send_telegram(settings, format_signal_rejected(payload, reason))


def notify_zone_touch(settings: Settings, payload: dict[str, Any]) -> None:
    """Kirim notifikasi zona tersentuh jika TELEGRAM_NOTIFY_ZONE_TOUCH aktif."""
    if settings.TELEGRAM_NOTIFY_ZONE_TOUCH:
        send_telegram(settings, format_zone_touch(payload))
