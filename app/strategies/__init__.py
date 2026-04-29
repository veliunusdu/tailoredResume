from app.strategies.base import ApplyStrategy
from app.strategies.greenhouse import GreenhouseStrategy
from app.strategies.lever import LeverStrategy
from app.strategies.linkedin import LinkedInEasyApplyStrategy
from app.strategies.generic import GenericStrategy

def get_strategy(platform: str) -> ApplyStrategy:
    """Factory to get the correct strategy for a job board."""
    strategies = {
        "greenhouse": GreenhouseStrategy(),
        "lever":      LeverStrategy(),
        "linkedin_easyapply": LinkedInEasyApplyStrategy(),
        "generic":    GenericStrategy(),
    }
    return strategies.get(platform, GenericStrategy())
