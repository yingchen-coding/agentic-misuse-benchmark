"""
Base classes for misuse scenario definitions.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import yaml


class MisuseCategory(Enum):
    """Categories of multi-turn misuse patterns."""
    PROMPT_INJECTION = "prompt_injection"
    POLICY_EROSION = "policy_erosion"
    INTENT_DRIFT = "intent_drift"
    COORDINATED_MISUSE = "coordinated_misuse"


class Difficulty(Enum):
    """Scenario difficulty levels."""
    EASY = "easy"      # Obvious attack patterns
    MEDIUM = "medium"  # Requires context awareness
    HARD = "hard"      # Subtle, multi-step attacks


@dataclass
class Turn:
    """A single turn in a conversation."""
    role: str  # 'user' or 'assistant'
    content: str
    is_attack: bool = False  # Ground truth: is this turn part of an attack?
    metadata: dict = field(default_factory=dict)


@dataclass
class Scenario:
    """
    A multi-turn misuse scenario.

    Each scenario defines:
    - A stated user goal (benign surface)
    - A latent misuse goal (actual attack objective)
    - A sequence of turns that execute the attack
    - Expected failure pattern for documentation
    """
    id: str
    category: MisuseCategory
    difficulty: Difficulty
    user_goal: str
    latent_misuse_goal: str
    turns: list[Turn]
    expected_failure_pattern: str
    tags: list[str] = field(default_factory=list)

    @property
    def attack_turns(self) -> list[int]:
        """Return indices of turns that are part of the attack."""
        return [i for i, t in enumerate(self.turns) if t.is_attack]

    @property
    def num_turns(self) -> int:
        return len(self.turns)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            'id': self.id,
            'category': self.category.value,
            'difficulty': self.difficulty.value,
            'user_goal': self.user_goal,
            'latent_misuse_goal': self.latent_misuse_goal,
            'turns': [
                {'role': t.role, 'content': t.content, 'is_attack': t.is_attack}
                for t in self.turns
            ],
            'expected_failure_pattern': self.expected_failure_pattern,
            'tags': self.tags
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Scenario':
        """Deserialize from dictionary."""
        return cls(
            id=data['id'],
            category=MisuseCategory(data['category']),
            difficulty=Difficulty(data.get('difficulty', 'medium')),
            user_goal=data['user_goal'],
            latent_misuse_goal=data['latent_misuse_goal'],
            turns=[
                Turn(
                    role=t['role'],
                    content=t['content'],
                    is_attack=t.get('is_attack', False)
                )
                for t in data['turns']
            ],
            expected_failure_pattern=data['expected_failure_pattern'],
            tags=data.get('tags', [])
        )


@dataclass
class ScenarioResult:
    """Result of running a scenario through a detector."""
    scenario_id: str
    category: str
    difficulty: str
    detected: bool
    detection_turn: Optional[int]  # Which turn triggered detection
    false_positive: bool
    policy_erosion_score: float
    intent_drift_score: float
    detector_name: str
    raw_scores: list[float] = field(default_factory=list)  # Per-turn scores

    def to_dict(self) -> dict:
        return {
            'scenario_id': self.scenario_id,
            'category': self.category,
            'difficulty': self.difficulty,
            'detected': int(self.detected),
            'detection_turn': self.detection_turn,
            'false_positive': int(self.false_positive),
            'policy_erosion_score': round(self.policy_erosion_score, 3),
            'intent_drift_score': round(self.intent_drift_score, 3),
            'detector_name': self.detector_name
        }


def load_scenarios_from_yaml(path: str) -> list[Scenario]:
    """Load scenarios from YAML file."""
    with open(path, 'r') as f:
        data = yaml.safe_load(f)
    return [Scenario.from_dict(s) for s in data.get('scenarios', [])]
