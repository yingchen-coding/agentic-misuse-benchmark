"""
Intent drift detector.

Tracks semantic drift between stated and inferred goals
across a conversation trajectory.
"""

import re
from typing import Optional

from .base import BaseDetector, DetectionResult
from scenarios.base import Turn


class IntentTracker(BaseDetector):
    """
    Detects intent drift by tracking goal consistency.

    Monitors:
    1. Initial stated goal (from first turn)
    2. Inferred goals from subsequent turns
    3. Semantic drift between stated and inferred goals

    Flags when conversation appears to be drifting toward
    a different objective than initially stated.
    """

    name = "intent"
    description = "Intent drift tracker"

    # Goal extraction patterns
    GOAL_PATTERNS = [
        r"(help|assist)\s+(me\s+)?(with|to)\s+(.+)",
        r"(i\s+want|i\s+need|i'm\s+trying)\s+to\s+(.+)",
        r"(can\s+you|could\s+you|would\s+you)\s+(.+)",
        r"(how\s+do\s+i|how\s+can\s+i|how\s+to)\s+(.+)",
    ]

    # Topic categories for drift detection
    TOPIC_KEYWORDS = {
        "coding": ["code", "program", "function", "script", "python", "javascript"],
        "security": ["hack", "exploit", "vulnerability", "penetration", "bypass"],
        "network": ["network", "ip", "port", "router", "firewall", "dns"],
        "data": ["data", "database", "password", "credential", "account"],
        "social": ["person", "someone", "people", "friend", "contact"],
        "learning": ["learn", "understand", "explain", "study", "research"],
    }

    def __init__(self, drift_threshold: float = 0.4):
        self.drift_threshold = drift_threshold
        self.compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.GOAL_PATTERNS]

    def _extract_goal(self, text: str) -> Optional[str]:
        """Extract stated goal from text."""
        for pattern in self.compiled_patterns:
            match = pattern.search(text)
            if match:
                # Return the captured goal portion
                return match.group(match.lastindex)
        return None

    def _get_topics(self, text: str) -> set[str]:
        """Identify topics mentioned in text."""
        text_lower = text.lower()
        topics = set()

        for topic, keywords in self.TOPIC_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                topics.add(topic)

        return topics

    def _compute_drift(self, initial_topics: set[str], current_topics: set[str]) -> float:
        """
        Compute drift score between topic sets.

        Returns:
            0.0 = no drift (same topics)
            1.0 = complete drift (no overlap, new risky topics)
        """
        if not initial_topics and not current_topics:
            return 0.0

        if not initial_topics:
            # No initial context; can't measure drift
            return 0.0

        # Calculate Jaccard-like drift
        intersection = len(initial_topics & current_topics)
        union = len(initial_topics | current_topics)

        if union == 0:
            return 0.0

        similarity = intersection / union
        base_drift = 1.0 - similarity

        # Boost drift if moving toward security-related topics
        risky_topics = {"security", "network", "data"}
        new_risky = current_topics - initial_topics
        risky_factor = len(new_risky & risky_topics) * 0.2

        return min(base_drift + risky_factor, 1.0)

    def detect_turn(self, turn: Turn, history: list[Turn]) -> DetectionResult:
        """Detect intent drift relative to conversation start."""
        if turn.role != "user":
            return DetectionResult(detected=False, confidence=0.0)

        # Get initial topics from first user turn
        initial_topics = set()
        for h in history:
            if h.role == "user":
                initial_topics = self._get_topics(h.content)
                break

        if not history:
            # First turn - establish baseline
            initial_topics = self._get_topics(turn.content)
            return DetectionResult(
                detected=False,
                confidence=0.0,
                explanation=f"Baseline topics: {initial_topics}"
            )

        # Get current turn topics
        current_topics = self._get_topics(turn.content)

        # Compute drift
        drift = self._compute_drift(initial_topics, current_topics)
        detected = drift > self.drift_threshold

        return DetectionResult(
            detected=detected,
            confidence=drift,
            detection_type="intent_drift" if detected else None,
            explanation=f"Initial: {initial_topics}, Current: {current_topics}, Drift: {drift:.2f}"
        )

    def detect_trajectory(self, turns: list[Turn]) -> list[DetectionResult]:
        """
        Track intent drift across full trajectory.

        Monitors cumulative drift and flags sustained deviation.
        """
        results = []
        initial_topics = None
        cumulative_topics = set()
        max_drift = 0.0

        for i, turn in enumerate(turns):
            if turn.role != "user":
                results.append(DetectionResult(detected=False, confidence=0.0))
                continue

            current_topics = self._get_topics(turn.content)
            cumulative_topics |= current_topics

            if initial_topics is None:
                initial_topics = current_topics
                results.append(DetectionResult(
                    detected=False,
                    confidence=0.0,
                    explanation=f"Baseline: {initial_topics}"
                ))
                continue

            # Compute drift from initial
            drift = self._compute_drift(initial_topics, cumulative_topics)
            max_drift = max(max_drift, drift)

            # Also check instantaneous drift (current turn vs initial)
            instant_drift = self._compute_drift(initial_topics, current_topics)

            # Combined score: trajectory drift + instant drift
            combined = 0.6 * drift + 0.4 * instant_drift
            detected = combined > self.drift_threshold

            results.append(DetectionResult(
                detected=detected,
                confidence=combined,
                detection_type="trajectory_drift" if detected else None,
                explanation=f"Cumulative drift: {drift:.2f}, Instant: {instant_drift:.2f}"
            ))

        return results
