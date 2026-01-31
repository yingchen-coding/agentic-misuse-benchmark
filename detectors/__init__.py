"""
Misuse detectors for the benchmark.
"""

from .base import BaseDetector, DetectionResult
from .rules import RuleBasedDetector
from .classifier import EmbeddingClassifier
from .intent_tracker import IntentTracker

__all__ = [
    'BaseDetector',
    'DetectionResult',
    'RuleBasedDetector',
    'EmbeddingClassifier',
    'IntentTracker',
]

DETECTORS = {
    'rules': RuleBasedDetector,
    'classifier': EmbeddingClassifier,
    'intent': IntentTracker,
}


def get_detector(name: str) -> BaseDetector:
    """Get detector instance by name."""
    if name not in DETECTORS:
        raise ValueError(f"Unknown detector: {name}. Available: {list(DETECTORS.keys())}")
    return DETECTORS[name]()


def list_detectors() -> list[str]:
    """List available detector names."""
    return list(DETECTORS.keys())
