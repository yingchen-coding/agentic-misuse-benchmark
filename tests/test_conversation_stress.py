import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from analysis.conversation_stress import benign_turn_fpr, build_conditions, run
from analysis.hard_negative_audit import load_traces
from detectors.base import BaseDetector, DetectionResult
from scenarios import get_all_scenarios
from scenarios.base import Difficulty, MisuseCategory, Scenario, Turn
from scenarios.perturbations import (
    TOOL_RELAY_REQUEST,
    extend_conversation,
    relay_through_tool,
    shift_topic,
)


def _scenario(turns):
    return Scenario(id="S", category=MisuseCategory.PROMPT_INJECTION, difficulty=Difficulty.EASY,
                    user_goal="g", latent_misuse_goal="m", turns=turns,
                    expected_failure_pattern="p")


BASE = _scenario([Turn("user", "opener"), Turn("user", "attack one", is_attack=True),
                  Turn("user", "attack two", is_attack=True)])
FILLER = [Turn("user", "f1"), Turn("assistant", "a1"), Turn("user", "f2"), Turn("assistant", "a2"),
          Turn("user", "f3", is_attack=True)]


def _attack_contents(scenario):
    return [scenario.turns[i].content for i in scenario.attack_turns]


def test_extend_inserts_exchanges_before_first_attack_and_keeps_labels():
    extended = extend_conversation(BASE, FILLER, 2)
    assert [t.content for t in extended.turns] == ["opener", "f1", "a1", "f2", "a2",
                                                   "attack one", "attack two"]
    assert _attack_contents(extended) == _attack_contents(BASE)
    assert extended.id == "S+extend2"


def test_extend_forces_inserted_turns_benign_even_if_source_was_labeled():
    extended = extend_conversation(BASE, FILLER, 3)
    assert _attack_contents(extended) == ["attack one", "attack two"]


def test_extend_zero_is_identity_and_too_many_fails_loudly():
    assert extend_conversation(BASE, FILLER, 0).turns == BASE.turns
    with pytest.raises(ValueError):
        extend_conversation(BASE, FILLER, 4)


def test_shift_topic_prepends_prior_conversation():
    shifted = shift_topic(BASE, FILLER[:4], "cooking")
    assert [t.content for t in shifted.turns[:4]] == ["f1", "a1", "f2", "a2"]
    assert shifted.turns[4:] == BASE.turns
    assert _attack_contents(shifted) == _attack_contents(BASE)


def test_tool_relay_moves_each_attack_into_tool_output_behind_a_benign_request():
    relayed = relay_through_tool(BASE)
    assert [(t.role, t.content, t.is_attack) for t in relayed.turns] == [
        ("user", "opener", False),
        ("user", TOOL_RELAY_REQUEST, False), ("tool", "attack one", True),
        ("user", TOOL_RELAY_REQUEST, False), ("tool", "attack two", True),
    ]


def test_perturbing_a_scenario_without_attacks_fails_loudly():
    benign = _scenario([Turn("user", "hello")])
    for perturb in (lambda s: extend_conversation(s, FILLER, 1),
                    lambda s: shift_topic(s, FILLER, "x"), relay_through_tool):
        with pytest.raises(ValueError):
            perturb(benign)


class _FlagsContent(BaseDetector):
    name = "flags"

    def detect_turn(self, turn, history):
        return DetectionResult(detected=turn.content == "f2", confidence=1.0)


def test_benign_turn_fpr_ignores_assistant_and_attack_turns():
    scenario = extend_conversation(BASE, FILLER, 2)
    assert benign_turn_fpr(_FlagsContent(), [scenario]) == pytest.approx(1 / 3)


def test_every_condition_preserves_the_attack_turns_of_all_scenarios():
    scenarios = get_all_scenarios()
    for condition, perturbed in build_conditions(scenarios, load_traces()).items():
        assert len(perturbed) == len(scenarios), condition
        for original, changed in zip(scenarios, perturbed):
            assert _attack_contents(changed) == _attack_contents(original), condition


def test_report_has_a_row_per_condition_and_baseline_has_no_drop():
    report = run(["rules"])
    rows = report["detectors"]["rules"]["conditions"]
    assert set(rows) == set(report["conditions"])
    assert rows["baseline"]["detection_drop"] == 0.0
