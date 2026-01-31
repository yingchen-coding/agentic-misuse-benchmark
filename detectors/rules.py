"""
Rule-based misuse detector.

A simple baseline that uses pattern matching to detect known
injection and attack signatures.
"""

import re
from typing import Optional

from .base import BaseDetector, DetectionResult
from scenarios.base import Turn


class RuleBasedDetector(BaseDetector):
    """
    Rule-based detector using regex patterns.

    This is intentionally simple to serve as a baseline.
    It demonstrates the limitations of pattern matching for
    subtle multi-turn attacks.
    """

    name = "rules"
    description = "Pattern-matching baseline detector"

    # Prompt injection patterns
    INJECTION_PATTERNS = [
        (r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", "instruction_override"),
        (r"disregard\s+(the\s+|your\s+)?(instructions|guidelines|rules)", "instruction_override"),
        (r"new\s+instructions?\s*:", "instruction_injection"),
        (r"system\s*prompt\s*:", "system_prompt_probe"),
        (r"you\s+are\s+now\s+", "persona_injection"),
        (r"pretend\s+(you\s+are|to\s+be)", "roleplay_injection"),
        (r"admin(istrator)?\s+override", "authority_claim"),
        (r"---\s*end\s*(of)?\s*(text|input|document)", "delimiter_injection"),
    ]

    # Policy erosion patterns
    EROSION_PATTERNS = [
        (r"(just|only)\s+this\s+once", "exception_request"),
        (r"(other|different)\s+AIs?\s+(can|would|do)", "comparison_pressure"),
        (r"come\s+on|please\s+just", "persistence"),
        (r"i\s+(promise|won'?t|will\s+not)", "false_assurance"),
        (r"for\s+(educational|research|testing)\s+purposes?", "pretext_claim"),
    ]

    # Dangerous content patterns
    DANGEROUS_PATTERNS = [
        (r"how\s+to\s+(hack|exploit|attack|breach)", "attack_request"),
        (r"(password|credential)\s+(cracking|stuffing|spraying)", "credential_attack"),
        (r"(malware|virus|trojan|keylogger)", "malware_reference"),
        (r"(ddos|denial\s+of\s+service)", "dos_reference"),
        (r"(phishing|spear\s*phishing)", "phishing_reference"),
    ]

    def __init__(self):
        # Compile all patterns for efficiency
        self.all_patterns = []
        for pattern, label in (self.INJECTION_PATTERNS +
                               self.EROSION_PATTERNS +
                               self.DANGEROUS_PATTERNS):
            self.all_patterns.append((re.compile(pattern, re.IGNORECASE), label))

    def detect_turn(self, turn: Turn, history: list[Turn]) -> DetectionResult:
        """Detect misuse patterns in a single turn."""
        if turn.role != "user":
            return DetectionResult(detected=False, confidence=0.0)

        text = turn.content.lower()
        matches = []

        for pattern, label in self.all_patterns:
            if pattern.search(text):
                matches.append(label)

        if matches:
            # More matches = higher confidence
            confidence = min(0.5 + 0.1 * len(matches), 0.95)
            return DetectionResult(
                detected=True,
                confidence=confidence,
                detection_type=matches[0],  # Primary match
                explanation=f"Matched patterns: {', '.join(matches)}"
            )

        return DetectionResult(
            detected=False,
            confidence=0.1,  # Low baseline confidence
            explanation="No patterns matched"
        )

    def detect_trajectory(self, turns: list[Turn]) -> list[DetectionResult]:
        """
        Detect with trajectory awareness.

        Looks for escalation patterns across turns.
        """
        results = []
        history = []
        escalation_score = 0.0

        for turn in turns:
            result = self.detect_turn(turn, history)

            # Track escalation across turns
            if result.detected:
                escalation_score += 0.2
            else:
                escalation_score = max(0, escalation_score - 0.1)

            # Boost confidence if we're seeing sustained suspicious activity
            if escalation_score > 0.3 and result.confidence > 0:
                result = DetectionResult(
                    detected=result.detected or escalation_score > 0.5,
                    confidence=min(result.confidence + escalation_score * 0.3, 0.95),
                    detection_type=result.detection_type or "escalation",
                    explanation=result.explanation + f" (escalation: {escalation_score:.2f})"
                )

            results.append(result)
            history.append(turn)

        return results
