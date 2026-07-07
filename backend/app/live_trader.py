"""TEMPLATE live trading — NONAKTIF secara default. BACA SEMUA PERINGATAN.

=============================================================================
PERINGATAN PENTING — WAJIB DIBACA SEBELUM MENGAKTIFKAN LIVE TRADING
=============================================================================
1. PAPER TRADE DULU. Jalankan sistem dalam mode "paper" minimal beberapa
   minggu dan evaluasi hasilnya sebelum memikirkan uang sungguhan.
2. MULAI DARI NOMINAL SANGAT KECIL. Anggap dana pertama sebagai biaya belajar.
3. JANGAN PERNAH membagikan API key ke siapa pun atau meng-commit-nya ke git.
4. NONAKTIFKAN izin WITHDRAW pada API key exchange Anda. Key trading tidak
   pernah butuh izin penarikan dana.
5. Tidak ada jaminan profit. Sinyal apa pun bisa salah; kerugian total
   mungkin terjadi. Gunakan hanya dana yang siap Anda hilangkan.
6. File ini hanyalah TEMPLATE: fungsi di bawah sengaja berhenti dengan
   NotImplementedError. Anda harus menulis, menguji, dan bertanggung jawab
   atas implementasi order Anda sendiri.
=============================================================================
"""

from __future__ import annotations

import logging

from app.config import Settings
from app.models import Signal

logger = logging.getLogger(__name__)


def execute_live_order(signal: Signal, settings: Settings) -> None:
    """Template eksekusi order live — dijaga berlapis agar tidak jalan tak sengaja.

    Syarat minimal sebelum fungsi ini mau bekerja:
    - settings.TRADING_MODE == "live"
    - settings.ENABLE_LIVE_TRADING == True
    - Kredensial exchange (EXCHANGE_ID, EXCHANGE_API_KEY, EXCHANGE_API_SECRET) terisi
    - Paket ccxt terpasang (di-import malas di dalam fungsi ini)
    """
    # --- Penjaga 1: mode & flag eksplisit ---
    if settings.TRADING_MODE != "live" or not settings.ENABLE_LIVE_TRADING:
        raise RuntimeError(
            "Live trading TIDAK aktif. Set TRADING_MODE=live dan "
            "ENABLE_LIVE_TRADING=true secara sadar di .env — dan hanya setelah "
            "hasil paper trading Anda meyakinkan."
        )

    # --- Penjaga 2: kredensial exchange wajib lengkap ---
    if not (settings.EXCHANGE_ID and settings.EXCHANGE_API_KEY and settings.EXCHANGE_API_SECRET):
        raise RuntimeError(
            "Kredensial exchange belum lengkap. Isi EXCHANGE_ID, EXCHANGE_API_KEY, "
            "dan EXCHANGE_API_SECRET di .env (dan pastikan izin withdraw DINONAKTIFKAN)."
        )

    # --- Penjaga 3: ccxt di-import malas agar tidak menjadi dependensi wajib ---
    try:
        import ccxt  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "Modul ccxt belum terpasang. Jalankan 'pip install ccxt' dulu "
            "di virtualenv backend sebelum mengaktifkan live trading."
        ) from exc

    logger.warning(
        "execute_live_order dipanggil untuk sinyal #%s (%s %s) — template belum diimplementasi.",
        signal.id,
        signal.signal,
        signal.symbol,
    )

    # =========================================================================
    # CONTOH IMPLEMENTASI (SENGAJA DIKOMENTARI — pahami dulu, uji di testnet!)
    # =========================================================================
    # exchange_class = getattr(ccxt, settings.EXCHANGE_ID)   # mis. "binance"
    # exchange = exchange_class({
    #     "apiKey": settings.EXCHANGE_API_KEY,
    #     "secret": settings.EXCHANGE_API_SECRET,
    #     "enableRateLimit": True,
    # })
    # # Banyak exchange menyediakan sandbox/testnet — SELALU mulai dari sana:
    # # exchange.set_sandbox_mode(True)
    #
    # # Hitung qty dari risiko riil akun Anda, JANGAN percaya position_size payload.
    # # qty = risiko_usd / abs(signal.entry - signal.stop_loss)
    #
    # # Order market sederhana:
    # # order = exchange.create_order(
    # #     symbol=signal.symbol,          # format ccxt biasanya "BTC/USDT"
    # #     type="market",
    # #     side=signal.signal.lower(),    # "buy" | "sell"
    # #     amount=qty,
    # # )
    #
    # # Catatan stop-loss / take-profit:
    # # - Tidak semua exchange mendukung SL/TP dalam satu createOrder.
    # # - Umumnya Anda perlu order terpisah: STOP_MARKET untuk stop_loss dan
    # #   TAKE_PROFIT_MARKET / limit untuk take_profit, atau params khusus
    # #   exchange (mis. {"stopLossPrice": ..., "takeProfitPrice": ...}).
    # # - Pastikan SL/TP ikut terpasang SEBELUM menganggap posisi aman.
    # =========================================================================

    raise NotImplementedError(
        "live_trader.py hanyalah template. Tulis implementasi order Anda sendiri, "
        "uji menyeluruh di testnet/sandbox, dan mulai dengan nominal kecil."
    )
