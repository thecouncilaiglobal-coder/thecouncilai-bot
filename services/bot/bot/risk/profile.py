from __future__ import annotations

from dataclasses import dataclass

from bot.config import RiskProfile


@dataclass(frozen=True)
class ProfileParams:
    name: RiskProfile

    # Score thresholds
    entry: int
    exit: int

    # Confirmation windows (seconds above/below threshold)
    entry_confirm_s: int
    exit_confirm_s: int

    # Position/risk limits
    max_positions: int
    max_exposure: float  # portion of equity to allocate (0..1)
    max_weight_per_pos: float

    # Rotation (optional)
    rotation_margin: int  # only rotate if new candidate beats worst by this margin
    min_hold_s: int

    # Stop/take-profit defaults (applied at entry when supported)
    stop_loss_pct: float
    take_profit_pct: float

    # Daily drawdown guard
    daily_max_drawdown_pct: float


PROFILES: dict[RiskProfile, ProfileParams] = {
    "conservative": ProfileParams(
        name="conservative",
        entry=78,
        exit=58,
        entry_confirm_s=60,
        exit_confirm_s=20,
        max_positions=3,
        max_exposure=0.75,
        max_weight_per_pos=0.35,
        rotation_margin=14,
        min_hold_s=900,
        stop_loss_pct=0.022,
        take_profit_pct=0.05,
        daily_max_drawdown_pct=0.03,
    ),
    "balanced": ProfileParams(
        name="balanced",
        entry=74,
        exit=56,
        entry_confirm_s=45,
        exit_confirm_s=15,
        max_positions=5,
        max_exposure=0.85,
        max_weight_per_pos=0.25,
        rotation_margin=12,
        min_hold_s=600,
        stop_loss_pct=0.03,
        take_profit_pct=0.065,
        daily_max_drawdown_pct=0.05,
    ),
    "aggressive": ProfileParams(
        name="aggressive",
        entry=70,
        exit=54,
        entry_confirm_s=30,
        exit_confirm_s=10,
        max_positions=7,
        max_exposure=0.95,
        max_weight_per_pos=0.20,
        rotation_margin=10,
        min_hold_s=420,
        stop_loss_pct=0.04,
        take_profit_pct=0.085,
        daily_max_drawdown_pct=0.08,
    ),
}


def params_for(profile: RiskProfile) -> ProfileParams:
    return PROFILES.get(profile, PROFILES["balanced"])
