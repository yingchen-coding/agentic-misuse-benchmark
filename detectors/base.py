"""
Base class for misuse detectors.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from scenarios.base import Turn


@dataclass
class DetectionResult:
    """Result of running detection on a turn or trajectory."""
    detected: bool
    confidence: float  # 0.0 to 1.0
    detection_type: Optional[str] = None  # What kind of misuse was detected
    explanation: str = ""


class BaseDetector(ABC):
    """
    Abstract base class for misuse detectors.

    Detectors can operate in two modes:
    1. Per-turn: Analyze each turn independently
    2. Trajectory: Analyze the full conversation history
    """

    name: str = "base"
    description: str = "Base detector"

    @abstractmethod
    def detect_turn(self, turn: Turn, history: list[Turn]) -> DetectionResult:
        """
        Detect misuse in a single turn given conversation history.

        Args:
            turn: The current turn to analyze
            history: Previous turns in the conversation

        Returns:
            DetectionResult with detection decision and confidence
        """
        pass

    def detect_trajectory(self, turns: list[Turn]) -> list[DetectionResult]:
        """
        Detect misuse across a full trajectory.

        Default implementation runs per-turn detection with accumulating history.
        Override for trajectory-aware detection.

        Args:
            turns: Full conversation trajectory

        Returns:
            List of DetectionResult, one per turn
        """
        results = []
        history = []

        for turn in turns:
            result = self.detect_turn(turn, history)
            results.append(result)
            history.append(turn)

        return results

    def get_trajectory_decision(self, results: list[DetectionResult]) -> DetectionResult:
        """
        Aggregate per-turn results into trajectory-level decision.

        Default: Flag if any turn was detected with high confidence.
        """
        max_confidence = 0.0
        any_detected = False
        detection_types = []

        for r in results:
            if r.detected:
                any_detected = True
                if r.detection_type:
                    detection_types.append(r.detection_type)
            max_confidence = max(max_confidence, r.confidence)

        return DetectionResult(
            detected=any_detected,
            confidence=max_confidence,
            detection_type=", ".join(set(detection_types)) if detection_types else None,
            explanation=f"Aggregated from {len(results)} turns"
        )
