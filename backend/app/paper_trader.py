"""Buku besar paper trading: saldo, buka/tutup posisi simulasi, dan agregat."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import KV_PAPER_BALANCE, get_kv, set_kv, utcnow_naive
from app.models import PaperTrade, Signal

logger = logging.getLogger(__name__)


def get_paper_balance(db: Session, settings: Settings) -> float:
    """Saldo paper saat ini; diinisialisasi dari PAPER_START_BALANCE bila belum ada."""
    raw = get_kv(db, KV_PAPER_BALANCE)
    if raw is None:
        set_kv(db, KV_PAPER_BALANCE, repr(float(settings.PAPER_START_BALANCE)))
        return float(settings.PAPER_START_BALANCE)
    try:
        return float(raw)
    except ValueError:
        logger.error("Nilai paper_balance rusak (%r); reset ke saldo awal.", raw)
        set_kv(db, KV_PAPER_BALANCE, repr(float(settings.PAPER_START_BALANCE)))
        return float(settings.PAPER_START_BALANCE)


def set_paper_balance(db: Session, value: float) -> None:
    """Simpan saldo paper secara persisten."""
    set_kv(db, KV_PAPER_BALANCE, repr(float(value)))


def open_paper_trade(db: Session, signal: Signal, settings: Settings) -> PaperTrade:
    """Buka posisi paper dari sinyal yang sudah tervalidasi.

    qty = risk_amount / |entry - stop_loss|;
    risk_amount = saldo * RISK_PER_TRADE_PCT / 100.
    Pemanggil menjamin |entry - stop_loss| > 0 (validasi struktur harga).
    """
    saldo = get_paper_balance(db, settings)
    risk_amount = saldo * settings.RISK_PER_TRADE_PCT / 100.0
    per_unit = abs(float(signal.entry) - float(signal.stop_loss))
    qty = risk_amount / per_unit
    trade = PaperTrade(
        signal_id=signal.id,
        symbol=signal.symbol or "",
        side=signal.signal or "",
        entry=float(signal.entry),
        stop_loss=float(signal.stop_loss),
        take_profit_1=float(signal.take_profit_1),
        take_profit_2=float(signal.take_profit_2),
        qty=qty,
        risk_amount=risk_amount,
        status="open",
        opened_at=utcnow_naive(),
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    logger.info("Paper trade #%s dibuka: %s %s qty=%.8f", trade.id, trade.side, trade.symbol, qty)
    return trade


def close_paper_trade(
    db: Session, trade: PaperTrade, exit_price: float, settings: Settings
) -> PaperTrade:
    """Tutup posisi paper, hitung PnL, dan perbarui saldo.

    PnL BUY = (exit - entry) * qty; PnL SELL = (entry - exit) * qty.
    """
    if trade.side == "SELL":
        pnl = (trade.entry - exit_price) * trade.qty
    else:
        pnl = (exit_price - trade.entry) * trade.qty
    trade.exit_price = float(exit_price)
    trade.pnl = pnl
    trade.status = "closed"
    trade.closed_at = utcnow_naive()
    saldo_baru = get_paper_balance(db, settings) + pnl
    set_paper_balance(db, saldo_baru)
    db.commit()
    db.refresh(trade)
    logger.info("Paper trade #%s ditutup: pnl=%.4f saldo=%.4f", trade.id, pnl, saldo_baru)
    return trade


def closed_pnl_since(db: Session, since: datetime) -> float:
    """Total PnL posisi paper yang DITUTUP sejak `since` (naive UTC)."""
    total = db.execute(
        select(func.coalesce(func.sum(PaperTrade.pnl), 0.0)).where(
            PaperTrade.status == "closed",
            PaperTrade.closed_at.is_not(None),
            PaperTrade.closed_at >= since,
        )
    ).scalar_one()
    return float(total)


def build_paper_report(db: Session, settings: Settings) -> dict:
    """Ringkasan laporan paper trading untuk GET /report/paper."""
    trades = list(db.execute(select(PaperTrade).order_by(PaperTrade.id)).scalars())
    closed = [t for t in trades if t.status == "closed"]
    open_trades = [t for t in trades if t.status == "open"]
    total_pnl = sum(t.pnl or 0.0 for t in closed)
    wins = sum(1 for t in closed if (t.pnl or 0.0) > 0)
    win_rate = round(wins / len(closed) * 100.0, 2) if closed else None
    return {
        "paper_balance": get_paper_balance(db, settings),
        "open_trades_count": len(open_trades),
        "closed_trades_count": len(closed),
        "total_pnl": total_pnl,
        "win_rate_pct": win_rate,
        "trades": [
            {
                "id": t.id,
                "signal_id": t.signal_id,
                "symbol": t.symbol,
                "side": t.side,
                "entry": t.entry,
                "stop_loss": t.stop_loss,
                "take_profit_1": t.take_profit_1,
                "take_profit_2": t.take_profit_2,
                "qty": t.qty,
                "risk_amount": t.risk_amount,
                "status": t.status,
                "exit_price": t.exit_price,
                "pnl": t.pnl,
                "opened_at": t.opened_at.isoformat() if t.opened_at else None,
                "closed_at": t.closed_at.isoformat() if t.closed_at else None,
            }
            for t in trades
        ],
    }
