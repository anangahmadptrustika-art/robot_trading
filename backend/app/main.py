"""Aplikasi FastAPI Smart Zone Trading Bot: webhook, admin, laporan, ekspor."""

from __future__ import annotations

import csv
import io
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import notifier, validators
from app.config import Settings, get_settings, validate_startup_settings
from app.database import (
    create_tables,
    get_db,
    init_engine,
    is_kill_switch_on,
    set_kill_switch,
    utcnow_naive,
)
from app.live_trader import execute_live_order
from app.models import PaperTrade, Signal
from app.paper_trader import (
    build_paper_report,
    close_paper_trade,
    closed_pnl_since,
    get_paper_balance,
    open_paper_trade,
)
from app.schemas import (
    HealthResponse,
    KillSwitchRequest,
    PaperCloseRequest,
    TradeSignalPayload,
    ZoneTouchPayload,
)
from app.security import (
    SlidingWindowRateLimiter,
    check_webhook_secret,
    constant_time_equals,
    get_client_ip,
    is_ip_allowed,
)

logger = logging.getLogger(__name__)

# Rate limiter global satu proses (jendela 60 detik).
rate_limiter = SlidingWindowRateLimiter(window_seconds=60.0)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Startup: validasi konfigurasi (gagal cepat), siapkan database."""
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    validate_startup_settings(settings)
    init_engine(settings.DATABASE_URL)
    create_tables()
    logger.info("Smart Zone Trading Bot siap. Mode: %s", settings.TRADING_MODE)
    yield


app = FastAPI(
    title="Smart Zone Trading Bot Backend",
    description="Backend webhook TradingView: validasi sinyal, paper trading, notifikasi.",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Util internal
# ---------------------------------------------------------------------------

def sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Salin payload TANPA field 'secret' (jangan pernah menyimpan secret)."""
    return {k: v for k, v in payload.items() if k != "secret"}


def _coerce_float(value: Any) -> Optional[float]:
    """Koersi longgar ke float untuk penyimpanan best-effort baris penolakan."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _store_signal_row(
    db: Session,
    status: str,
    reject_reason: Optional[str],
    payload: Optional[dict[str, Any]],
    parsed: Optional[TradeSignalPayload] = None,
    rr_computed: Optional[float] = None,
) -> Signal:
    """Simpan satu baris signals (best-effort untuk payload yang belum tervalidasi)."""
    data = sanitize_payload(payload) if isinstance(payload, dict) else None
    sumber: dict[str, Any] = data or {}
    row = Signal(
        received_at=utcnow_naive(),
        symbol=(parsed.symbol if parsed else (str(sumber.get("symbol")) if sumber.get("symbol") is not None else None)),
        timeframe=(parsed.timeframe if parsed else (str(sumber.get("timeframe")) if sumber.get("timeframe") is not None else None)),
        signal=(parsed.signal if parsed else (str(sumber.get("signal")) if sumber.get("signal") is not None else None)),
        entry=(parsed.entry if parsed else _coerce_float(sumber.get("entry"))),
        stop_loss=(parsed.stop_loss if parsed else _coerce_float(sumber.get("stop_loss"))),
        take_profit_1=(parsed.take_profit_1 if parsed else _coerce_float(sumber.get("take_profit_1"))),
        take_profit_2=(parsed.take_profit_2 if parsed else _coerce_float(sumber.get("take_profit_2"))),
        risk_reward_reported=(parsed.risk_reward if parsed else _coerce_float(sumber.get("risk_reward"))),
        risk_reward_computed=rr_computed,
        trend=(parsed.trend if parsed else (str(sumber.get("trend")) if sumber.get("trend") is not None else None)),
        confidence=(parsed.confidence if parsed else _coerce_float(sumber.get("confidence"))),
        signal_time=(parsed.time if parsed else (str(sumber.get("time")) if sumber.get("time") is not None else None)),
        strategy=(parsed.strategy if parsed else (str(sumber.get("strategy")) if sumber.get("strategy") is not None else None)),
        status=status,
        reject_reason=reject_reason,
        raw_payload=json.dumps(data, ensure_ascii=False, default=str) if data is not None else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _reject(
    db: Session,
    settings: Settings,
    payload: Optional[dict[str, Any]],
    reason: str,
    status_code: int,
    parsed: Optional[TradeSignalPayload] = None,
    rr_computed: Optional[float] = None,
) -> JSONResponse:
    """Catat penolakan ke tabel signals lalu balas JSON {status, reason}."""
    _store_signal_row(db, "rejected", reason, payload, parsed=parsed, rr_computed=rr_computed)
    logger.info("Sinyal ditolak: %s", reason)
    if isinstance(payload, dict):
        notifier.notify_signal_rejected(settings, sanitize_payload(payload), reason)
    return JSONResponse(status_code=status_code, content={"status": "rejected", "reason": reason})


async def _read_json_dict(request: Request) -> Optional[dict[str, Any]]:
    """Baca body sebagai dict JSON; None jika bukan JSON objek yang valid."""
    try:
        data = await request.json()
    except Exception:  # noqa: BLE001 — body bisa berupa apa saja
        return None
    return data if isinstance(data, dict) else None


def _utc_day_start_naive(now: Optional[datetime] = None) -> datetime:
    """Awal hari UTC berjalan sebagai datetime naive (cocok dengan kolom DB)."""
    now = now or datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)


def require_admin(
    x_admin_token: str = Header(default="", alias="X-Admin-Token"),
    settings: Settings = Depends(get_settings),
) -> None:
    """Dependency admin: header X-Admin-Token wajib cocok (constant-time)."""
    if not x_admin_token or not constant_time_equals(x_admin_token, settings.ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Token admin tidak valid.")


# ---------------------------------------------------------------------------
# Webhook utama
# ---------------------------------------------------------------------------

def _handle_zone_touch(
    db: Session, settings: Settings, payload: dict[str, Any]
) -> JSONResponse:
    """Tangani alert informasi ZONE_TOUCH: catat status 'info', tanpa posisi."""
    bersih = sanitize_payload(payload)
    try:
        zona = ZoneTouchPayload.model_validate(bersih)
    except ValidationError:
        return _reject(db, settings, payload, "invalid_payload", 422)
    row = Signal(
        received_at=utcnow_naive(),
        symbol=zona.symbol,
        timeframe=zona.timeframe,
        signal=zona.side,
        signal_time=zona.time,
        strategy="ZONE_TOUCH",
        status="info",
        reject_reason=None,
        raw_payload=json.dumps(bersih, ensure_ascii=False, default=str),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    notifier.notify_zone_touch(settings, bersih)
    return JSONResponse(status_code=200, content={"status": "info", "signal_id": row.id})


@app.post("/webhook/tradingview")
async def tradingview_webhook(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    """Pintu masuk alert TradingView — menjalankan rantai validasi lengkap."""
    payload = await _read_json_dict(request)
    client_ip = get_client_ip(request, settings.TRUST_PROXY_HEADERS)

    # 1a. Rate limit per IP klien.
    if not rate_limiter.allow(client_ip, settings.RATE_LIMIT_PER_MINUTE):
        return _reject(db, settings, payload, "rate_limited", 429)

    # 1b. Allowlist IP (kosong = izinkan semua).
    if not is_ip_allowed(client_ip, settings.ip_allowlist_set()):
        return _reject(db, settings, payload, "ip_not_allowed", 403)

    # 2. Kill switch.
    if is_kill_switch_on(db):
        return _reject(db, settings, payload, "kill_switch_active", 503)

    # 3. Cek secret (constant-time). Secret TIDAK pernah dicatat/log.
    provided_secret = payload.get("secret") if payload is not None else None
    if not check_webhook_secret(provided_secret, settings.WEBHOOK_SECRET):
        return _reject(db, settings, payload, "invalid_secret", 401)
    assert payload is not None  # secret valid berarti payload dict

    # Alert informasi ZONE_TOUCH: catat saja, jangan pernah buka posisi.
    if str(payload.get("type", "")).strip().upper() == "ZONE_TOUCH":
        return _handle_zone_touch(db, settings, payload)

    # 4. Skema/koersi.
    try:
        sig = TradeSignalPayload.model_validate(sanitize_payload(payload))
    except ValidationError as exc:
        logger.info("Payload tidak valid: %s", exc.error_count())
        return _reject(db, settings, payload, "invalid_payload", 422)

    # 5. Validitas bisnis: sisi sinyal, harga positif, struktur harga.
    for ok, alasan in (
        validators.check_signal_side(sig.signal),
        validators.check_prices_positive(sig.entry, sig.stop_loss, sig.take_profit_1, sig.take_profit_2),
        validators.check_price_structure(sig.signal, sig.entry, sig.stop_loss, sig.take_profit_1, sig.take_profit_2),
    ):
        if not ok:
            return _reject(db, settings, payload, alasan, 400, parsed=sig)

    # 6. Hitung ulang RR — jangan pernah percaya nilai dari payload.
    rr = validators.compute_risk_reward(sig.entry, sig.stop_loss, sig.take_profit_2)
    ok, alasan = validators.check_min_risk_reward(rr, settings.MIN_RISK_REWARD)
    if not ok:
        return _reject(db, settings, payload, alasan, 400, parsed=sig, rr_computed=rr)

    # 7. Allowlist simbol.
    ok, alasan = validators.check_symbol_allowed(sig.symbol, settings.symbol_allowlist_set())
    if not ok:
        return _reject(db, settings, payload, alasan, 400, parsed=sig, rr_computed=rr)

    # 8. Umur sinyal (waktu tak terbaca → terima, tapi catat peringatan).
    ok, alasan = validators.check_signal_age(sig.time, settings.SIGNAL_MAX_AGE_SECONDS)
    if not ok:
        return _reject(db, settings, payload, alasan, 400, parsed=sig, rr_computed=rr)
    if alasan == "unparseable_time":
        logger.warning("Waktu sinyal tidak bisa di-parse: %r — sinyal tetap diproses.", sig.time)

    # 9. Dedup: sinyal DITERIMA yang sama dalam jendela dedup.
    batas_dedup = utcnow_naive() - timedelta(seconds=settings.DEDUP_WINDOW_SECONDS)
    duplikat = db.execute(
        select(Signal.id).where(
            Signal.status == "accepted",
            Signal.symbol == sig.symbol,
            Signal.signal == sig.signal,
            Signal.timeframe == sig.timeframe,
            Signal.received_at >= batas_dedup,
        )
    ).first()
    if duplikat is not None:
        return _reject(db, settings, payload, "duplicate_signal", 409, parsed=sig, rr_computed=rr)

    # 10a. Batas jumlah sinyal diterima per hari (hari UTC).
    awal_hari = _utc_day_start_naive()
    diterima_hari_ini = db.execute(
        select(func.count(Signal.id)).where(
            Signal.status == "accepted", Signal.received_at >= awal_hari
        )
    ).scalar_one()
    if diterima_hari_ini >= settings.MAX_SIGNALS_PER_DAY:
        return _reject(db, settings, payload, "daily_signal_limit", 400, parsed=sig, rr_computed=rr)

    # 10b. Batas kerugian harian dari PnL paper yang ditutup hari ini.
    saldo = get_paper_balance(db, settings)
    pnl_hari_ini = closed_pnl_since(db, awal_hari)
    if pnl_hari_ini <= -(settings.MAX_DAILY_LOSS_PCT / 100.0) * saldo:
        return _reject(db, settings, payload, "daily_loss_limit", 400, parsed=sig, rr_computed=rr)

    # DITERIMA — simpan sinyal.
    row = _store_signal_row(db, "accepted", None, payload, parsed=sig, rr_computed=rr)

    # Eksekusi sesuai mode trading.
    paper_trade: Optional[PaperTrade] = None
    if settings.TRADING_MODE == "paper":
        paper_trade = open_paper_trade(db, row, settings)
    elif settings.TRADING_MODE == "live" and settings.ENABLE_LIVE_TRADING:
        try:
            execute_live_order(row, settings)
        except Exception:  # noqa: BLE001 — template/live error tidak boleh mematikan webhook
            logger.error("execute_live_order gagal untuk sinyal #%s.", row.id, exc_info=True)

    # Notifikasi Telegram (kegagalan ditelan di notifier).
    notifier.notify_signal_accepted(settings, row, settings.TRADING_MODE, paper_trade)

    return JSONResponse(
        status_code=200,
        content={
            "status": "accepted",
            "signal_id": row.id,
            "mode": settings.TRADING_MODE,
            "paper_trade_id": paper_trade.id if paper_trade else None,
        },
    )


# ---------------------------------------------------------------------------
# Endpoint kesehatan, daftar sinyal, laporan, ekspor
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
def health(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> HealthResponse:
    """Status layanan, mode trading, dan keadaan kill switch."""
    return HealthResponse(
        status="ok", mode=settings.TRADING_MODE, kill_switch=is_kill_switch_on(db)
    )


def _signal_to_dict(row: Signal) -> dict[str, Any]:
    """Serialisasi baris Signal (raw_payload sudah bebas secret sejak disimpan)."""
    try:
        raw = json.loads(row.raw_payload) if row.raw_payload else None
    except json.JSONDecodeError:
        raw = None
    return {
        "id": row.id,
        "received_at": row.received_at.isoformat() if row.received_at else None,
        "symbol": row.symbol,
        "timeframe": row.timeframe,
        "signal": row.signal,
        "entry": row.entry,
        "stop_loss": row.stop_loss,
        "take_profit_1": row.take_profit_1,
        "take_profit_2": row.take_profit_2,
        "risk_reward_reported": row.risk_reward_reported,
        "risk_reward_computed": row.risk_reward_computed,
        "trend": row.trend,
        "confidence": row.confidence,
        "signal_time": row.signal_time,
        "strategy": row.strategy,
        "status": row.status,
        "reject_reason": row.reject_reason,
        "raw_payload": raw,
    }


@app.get("/signals")
def list_signals(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None, pattern="^(accepted|rejected|info)$"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Daftar sinyal terbaru (payload sudah bebas secret)."""
    stmt = select(Signal).order_by(Signal.id.desc()).limit(limit).offset(offset)
    if status:
        stmt = (
            select(Signal)
            .where(Signal.status == status)
            .order_by(Signal.id.desc())
            .limit(limit)
            .offset(offset)
        )
    rows = list(db.execute(stmt).scalars())
    return {"count": len(rows), "signals": [_signal_to_dict(r) for r in rows]}


@app.get("/report/paper")
def paper_report(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> dict[str, Any]:
    """Laporan paper trading: saldo, posisi, PnL total, win rate."""
    return build_paper_report(db, settings)


_CSV_COLUMNS = [
    "id", "received_at", "symbol", "timeframe", "signal", "entry", "stop_loss",
    "take_profit_1", "take_profit_2", "risk_reward_reported", "risk_reward_computed",
    "trend", "confidence", "signal_time", "strategy", "status", "reject_reason",
]


@app.get("/export/signals.csv")
def export_signals_csv(db: Session = Depends(get_db)) -> Response:
    """Ekspor seluruh tabel signals sebagai CSV (tanpa raw_payload/secret)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_CSV_COLUMNS)
    for row in db.execute(select(Signal).order_by(Signal.id)).scalars():
        writer.writerow([
            row.id,
            row.received_at.isoformat() if row.received_at else "",
            row.symbol or "",
            row.timeframe or "",
            row.signal or "",
            row.entry if row.entry is not None else "",
            row.stop_loss if row.stop_loss is not None else "",
            row.take_profit_1 if row.take_profit_1 is not None else "",
            row.take_profit_2 if row.take_profit_2 is not None else "",
            row.risk_reward_reported if row.risk_reward_reported is not None else "",
            row.risk_reward_computed if row.risk_reward_computed is not None else "",
            row.trend or "",
            row.confidence if row.confidence is not None else "",
            row.signal_time or "",
            row.strategy or "",
            row.status,
            row.reject_reason or "",
        ])
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="signals.csv"'},
    )


# ---------------------------------------------------------------------------
# Endpoint admin (X-Admin-Token, dibandingkan constant-time)
# ---------------------------------------------------------------------------

@app.post("/admin/kill-switch", dependencies=[Depends(require_admin)])
def admin_kill_switch(
    body: KillSwitchRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Nyalakan/matikan kill switch; status disimpan persisten di kv_store."""
    set_kill_switch(db, body.enabled)
    logger.warning("Kill switch diubah menjadi: %s", body.enabled)
    return {"status": "ok", "kill_switch": body.enabled}


@app.post("/paper/close/{trade_id}", dependencies=[Depends(require_admin)])
def admin_close_paper_trade(
    trade_id: int,
    body: PaperCloseRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Tutup posisi paper secara manual dengan harga keluar tertentu."""
    trade = db.get(PaperTrade, trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="Paper trade tidak ditemukan.")
    if trade.status == "closed":
        raise HTTPException(status_code=400, detail="Paper trade sudah ditutup.")
    trade = close_paper_trade(db, trade, body.exit_price, settings)
    return {
        "status": "ok",
        "trade_id": trade.id,
        "side": trade.side,
        "entry": trade.entry,
        "exit_price": trade.exit_price,
        "qty": trade.qty,
        "pnl": trade.pnl,
        "paper_balance": get_paper_balance(db, settings),
    }
