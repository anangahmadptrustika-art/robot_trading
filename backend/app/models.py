"""Model SQLAlchemy: signals, paper_trades, kv_store."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, utcnow_naive


class Signal(Base):
    """Catatan setiap alert yang masuk (diterima, ditolak, maupun info)."""

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, index=True)
    symbol: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    timeframe: Mapped[Optional[str]] = mapped_column(String(16))
    signal: Mapped[Optional[str]] = mapped_column(String(32))
    entry: Mapped[Optional[float]] = mapped_column(Float)
    stop_loss: Mapped[Optional[float]] = mapped_column(Float)
    take_profit_1: Mapped[Optional[float]] = mapped_column(Float)
    take_profit_2: Mapped[Optional[float]] = mapped_column(Float)
    risk_reward_reported: Mapped[Optional[float]] = mapped_column(Float)
    risk_reward_computed: Mapped[Optional[float]] = mapped_column(Float)
    trend: Mapped[Optional[str]] = mapped_column(String(32))
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    signal_time: Mapped[Optional[str]] = mapped_column(String(64))  # string mentah dari payload
    strategy: Mapped[Optional[str]] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), index=True)  # accepted | rejected | info
    reject_reason: Mapped[Optional[str]] = mapped_column(String(64))
    raw_payload: Mapped[Optional[str]] = mapped_column(Text)  # JSON tanpa field secret


class PaperTrade(Base):
    """Buku besar paper trading (simulasi, bukan order sungguhan)."""

    __tablename__ = "paper_trades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    signal_id: Mapped[Optional[int]] = mapped_column(ForeignKey("signals.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(64))
    side: Mapped[str] = mapped_column(String(8))  # BUY | SELL
    entry: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    take_profit_1: Mapped[float] = mapped_column(Float)
    take_profit_2: Mapped[float] = mapped_column(Float)
    qty: Mapped[float] = mapped_column(Float)
    risk_amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(8), index=True)  # open | closed
    exit_price: Mapped[Optional[float]] = mapped_column(Float)
    pnl: Mapped[Optional[float]] = mapped_column(Float)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class KVStore(Base):
    """Penyimpanan key-value sederhana (saldo paper, kill switch)."""

    __tablename__ = "kv_store"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
