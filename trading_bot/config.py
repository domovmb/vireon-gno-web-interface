from dataclasses import dataclass, field
from typing import Tuple

@dataclass(frozen=True)
class SurvivalLimits:
    risk_per_trade: float = 0.005
    max_notional_leverage: float = 2.0
    daily_loss_limit: float = 0.03
    hard_drawdown: float = 0.20
    cooldown_losses: int = 3
    cooldown_minutes: int = 60

@dataclass(frozen=True)
class StrategyParams:
    ema_fast: int = 20
    ema_slow: int = 50
    rsi_period: int = 14
    atr_period: int = 14
    rsi_trigger: float = 50.0
    sl_atr: float = 1.5
    tp_atr: float = 2.25

@dataclass(frozen=True)
class Config:
    coin: str = "xyz:EURUSD"
    interval: str = "15m"
    initial_equity: float = 100.0
    fee_rate: float = 0.0005
    slippage_bps: float = 2.0
    limits: SurvivalLimits = field(default_factory=SurvivalLimits)
    params: StrategyParams = field(default_factory=StrategyParams)
    allowed_param_ranges: Tuple[Tuple[str, float, float, float], ...] = (
        ("ema_fast", 8, 40, 2), ("ema_slow", 30, 120, 5),
        ("rsi_trigger", 45, 55, 1), ("sl_atr", 1.0, 2.5, 0.25),
        ("tp_atr", 1.5, 4.0, 0.25),
    )
