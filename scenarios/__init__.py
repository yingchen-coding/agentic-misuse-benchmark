"""
Misuse scenario definitions and generators.
"""

from .base import (
    Scenario,
    ScenarioResult,
    Turn,
    MisuseCategory,
    Difficulty,
    load_scenarios_from_yaml
)
from .prompt_injection import PromptInjectionScenarios
from .policy_erosion import PolicyErosionScenarios
from .intent_drift import IntentDriftScenarios
from .coordinated_misuse import CoordinatedMisuseScenarios

__all__ = [
    'Scenario',
    'ScenarioResult',
    'Turn',
    'MisuseCategory',
    'Difficulty',
    'load_scenarios_from_yaml',
    'PromptInjectionScenarios',
    'PolicyErosionScenarios',
    'IntentDriftScenarios',
    'CoordinatedMisuseScenarios',
]


def get_all_scenarios() -> list[Scenario]:
    """Get all built-in scenarios."""
    scenarios = []
    scenarios.extend(PromptInjectionScenarios.get_scenarios())
    scenarios.extend(PolicyErosionScenarios.get_scenarios())
    scenarios.extend(IntentDriftScenarios.get_scenarios())
    scenarios.extend(CoordinatedMisuseScenarios.get_scenarios())
    return scenarios


def get_scenarios_by_category(category: MisuseCategory) -> list[Scenario]:
    """Get scenarios filtered by category."""
    generators = {
        MisuseCategory.PROMPT_INJECTION: PromptInjectionScenarios,
        MisuseCategory.POLICY_EROSION: PolicyErosionScenarios,
        MisuseCategory.INTENT_DRIFT: IntentDriftScenarios,
        MisuseCategory.COORDINATED_MISUSE: CoordinatedMisuseScenarios,
    }
    return generators[category].get_scenarios()
