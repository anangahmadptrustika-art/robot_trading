"""Skema request/response pydantic v2 dengan koersi string yang toleran."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _ke_str(v: Any) -> Optional[str]:
    """Koersi nilai apa pun menjadi string yang sudah di-strip (None dibiarkan)."""
    if v is None:
        return None
    return str(v).strip()


class TradeSignalPayload(BaseModel):
    """Payload sinyal trading dari Pine Script (semua nilai bisa berupa string)."""

    model_config = ConfigDict(extra="ignore")

    symbol: str
    timeframe: str
    signal: str
    entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    risk_reward: Optional[float] = None
    trend: Optional[str] = None
    confidence: Optional[float] = None
    position_size: Optional[float] = None  # hanya informasi, tidak dipakai hitung qty
    time: Optional[str] = None
    strategy: Optional[str] = None

    @field_validator("symbol", "timeframe", "signal", "trend", "time", "strategy", mode="before")
    @classmethod
    def _koersi_string(cls, v: Any) -> Optional[str]:
        return _ke_str(v)

    @field_validator("symbol", "signal", "trend")
    @classmethod
    def _huruf_besar(cls, v: Optional[str]) -> Optional[str]:
        return v.upper() if v else v


class ZoneTouchPayload(BaseModel):
    """Alert informasi ZONE_TOUCH — tidak pernah membuka posisi."""

    model_config = ConfigDict(extra="ignore")

    type: str
    side: Optional[str] = None
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    zone_top: Optional[float] = None
    zone_bottom: Optional[float] = None
    time: Optional[str] = None

    @field_validator("type", "side", "symbol", "timeframe", "time", mode="before")
    @classmethod
    def _koersi_string(cls, v: Any) -> Optional[str]:
        return _ke_str(v)

    @field_validator("type", "side", "symbol")
    @classmethod
    def _huruf_besar(cls, v: Optional[str]) -> Optional[str]:
        return v.upper() if v else v


class KillSwitchRequest(BaseModel):
    """Body untuk POST /admin/kill-switch."""

    enabled: bool


class PaperCloseRequest(BaseModel):
    """Body untuk POST /paper/close/{trade_id}."""

    exit_price: float = Field(gt=0, description="Harga keluar; harus > 0")


class HealthResponse(BaseModel):
    """Respons GET /health."""

    status: str
    mode: str
    kill_switch: bool
