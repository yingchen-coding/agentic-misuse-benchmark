"""
Embedding-based classifier for misuse detection.

A simple ML baseline using sentence embeddings and logistic regression.
"""

import numpy as np
from typing import Optional

from .base import BaseDetector, DetectionResult
from scenarios.base import Turn


class EmbeddingClassifier(BaseDetector):
    """
    Embedding-based misuse classifier.

    Uses a simple architecture:
    1. Encode turns using sentence embeddings
    2. Mean pool over sliding window
    3. Linear classifier for misuse probability

    This is a lightweight baseline. Production systems would use
    more sophisticated architectures.
    """

    name = "classifier"
    description = "Embedding-based trajectory classifier"

    # Simulated weights (in practice, these would be trained)
    # These capture intuitions about suspicious patterns
    SUSPICIOUS_KEYWORDS = {
        "ignore": 0.3, "override": 0.4, "disregard": 0.3,
        "hack": 0.5, "exploit": 0.4, "bypass": 0.3,
        "password": 0.2, "credential": 0.3, "secret": 0.2,
        "pretend": 0.3, "roleplay": 0.2, "hypothetically": 0.2,
        "just this once": 0.3, "please just": 0.2,
        "system prompt": 0.5, "instructions": 0.2,
    }

    def __init__(self, window_size: int = 3):
        self.window_size = window_size
        self._model_loaded = False

    def _simple_embedding_score(self, text: str) -> float:
        """
        Simple keyword-based scoring as embedding proxy.

        In production, this would use actual embeddings from
        a sentence transformer model.
        """
        text_lower = text.lower()
        score = 0.0

        for keyword, weight in self.SUSPICIOUS_KEYWORDS.items():
            if keyword in text_lower:
                score += weight

        # Normalize to 0-1 range
        return min(score / 2.0, 1.0)

    def _trajectory_features(self, turns: list[Turn], current_idx: int) -> np.ndarray:
        """
        Extract features from trajectory window.

        Returns feature vector capturing:
        - Current turn suspiciousness
        - Window average suspiciousness
        - Suspiciousness trend
        """
        # Get window of turns up to current
        start_idx = max(0, current_idx - self.window_size + 1)
        window = turns[start_idx:current_idx + 1]

        # Score each turn in window
        scores = [
            self._simple_embedding_score(t.content)
            for t in window if t.role == "user"
        ]

        if not scores:
            return np.array([0.0, 0.0, 0.0])

        current_score = scores[-1] if scores else 0.0
        avg_score = np.mean(scores)

        # Trend: are scores increasing?
        if len(scores) >= 2:
            trend = scores[-1] - scores[0]
        else:
            trend = 0.0

        return np.array([current_score, avg_score, trend])

    def detect_turn(self, turn: Turn, history: list[Turn]) -> DetectionResult:
        """Detect misuse using embedding-based scoring."""
        if turn.role != "user":
            return DetectionResult(detected=False, confidence=0.0)

        # Build trajectory for feature extraction
        trajectory = history + [turn]
        features = self._trajectory_features(trajectory, len(trajectory) - 1)

        # Simple linear combination (simulating trained weights)
        weights = np.array([0.5, 0.3, 0.2])
        raw_score = np.dot(features, weights)

        # Apply sigmoid-like transformation
        confidence = 1.0 / (1.0 + np.exp(-3 * (raw_score - 0.3)))

        detected = confidence > 0.5

        return DetectionResult(
            detected=detected,
            confidence=float(confidence),
            detection_type="embedding_classifier" if detected else None,
            explanation=f"Features: current={features[0]:.2f}, avg={features[1]:.2f}, trend={features[2]:.2f}"
        )

    def detect_trajectory(self, turns: list[Turn]) -> list[DetectionResult]:
        """
        Trajectory-aware detection with full context.

        Uses sliding window over entire trajectory.
        """
        results = []

        for i, turn in enumerate(turns):
            if turn.role != "user":
                results.append(DetectionResult(detected=False, confidence=0.0))
                continue

            features = self._trajectory_features(turns, i)

            # Trajectory-aware weighting (later turns get more context)
            position_factor = min(1.0, (i + 1) / 3)  # Ramp up over first 3 turns

            weights = np.array([0.4, 0.35, 0.25])
            raw_score = np.dot(features, weights) * (0.7 + 0.3 * position_factor)

            confidence = 1.0 / (1.0 + np.exp(-3 * (raw_score - 0.25)))
            detected = confidence > 0.5

            results.append(DetectionResult(
                detected=detected,
                confidence=float(confidence),
                detection_type="trajectory_classifier" if detected else None,
                explanation=f"Turn {i+1}: score={raw_score:.2f}, position_factor={position_factor:.2f}"
            ))

        return results
