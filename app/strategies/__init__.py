"""Strategy factory — maps platform names to strategy instances."""
from __future__ import annotations
from app.strategies.greenhouse import GreenhouseStrategy
from app.strategies.lever import LeverStrategy
from app.strategies.linkedin import LinkedInEasyApplyStrategy
from app.strategies.generic import GenericStrategy
from app.strategies.base import ApplyStrategy

_STRATEGIES: dict[str, ApplyStrategy] = {
    "greenhouse":         GreenhouseStrategy(),
    "lever":              LeverStrategy(),
    "linkedin_easyapply": LinkedInEasyApplyStrategy(),
    "ashby":              GenericStrategy(),
    "generic":            GenericStrategy(),
}


def get_strategy(platform: str) -> ApplyStrategy:
    """Return the appropriate strategy for the given platform name."""
    return _STRATEGIES.get(platform.lower(), GenericStrategy())
