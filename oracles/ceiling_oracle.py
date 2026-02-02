"""
Ceiling Oracle: Establish theoretical detection limits.

Purpose: Answer "What's the best possible detection performance?"
If our detector is at 70% and ceiling is 72%, we're nearly optimal.
If our detector is at 70% and ceiling is 95%, there's room to improve.

Methods:
1. Human expert panel ceiling
2. Ensemble of best detectors
3. Information-theoretic bounds
"""

import json
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum


class CeilingMethod(Enum):
    """Methods for establishing detection ceiling."""
    HUMAN_EXPERT = "human_expert"           # Human expert panel agreement
    ENSEMBLE_BEST = "ensemble_best"         # Best-of-N detector ensemble
    MAJORITY_VOTE = "majority_vote"         # Majority vote of all methods
    INFORMATION_THEORETIC = "info_theoretic" # Theoretical bound


@dataclass
class CeilingEstimate:
    """Ceiling estimate for a detection task."""
    task_id: str
    method: CeilingMethod
    ceiling_accuracy: float
    ceiling_recall: float
    ceiling_precision: float
    confidence_interval: Tuple[float, float]
    sample_size: int
    notes: str = ""


class CeilingOracle:
    """
    Establish detection ceiling through multiple methods.

    Philosophy: You can't know if your detector is good without
    knowing what "good" looks like. The ceiling oracle provides
    that reference point.
    """

    def __init__(self):
        self.estimates: List[CeilingEstimate] = []
        self.human_labels: Dict[str, List[Dict]] = {}
        self.detector_results: Dict[str, List[Dict]] = {}

    def compute_human_ceiling(
        self,
        task_id: str,
        samples: List[Dict],
        n_experts: int = 3,
        expert_fn=None
    ) -> CeilingEstimate:
        """
        Compute ceiling using human expert panel.

        Args:
            task_id: Identifier for the detection task
            samples: List of samples to evaluate
            n_experts: Number of independent experts
            expert_fn: Function to get expert labels (mock if None)

        Returns:
            CeilingEstimate based on expert agreement
        """
        # Collect expert labels
        expert_labels = []
        for i in range(n_experts):
            if expert_fn:
                labels = expert_fn(samples, expert_id=i)
            else:
                labels = self._mock_expert_labels(samples, expert_id=i)
            expert_labels.append(labels)

        # Compute agreement and derive ceiling
        agreements = []
        for j, sample in enumerate(samples):
            votes = [expert_labels[i][j] for i in range(n_experts)]
            # Majority determines "truth"
            majority = sum(votes) > n_experts / 2
            agreement = sum(1 for v in votes if v == majority) / n_experts
            agreements.append(agreement)

        # Ceiling is based on average agreement
        ceiling_accuracy = sum(agreements) / len(agreements)

        # Compute precision/recall assuming majority is ground truth
        majority_labels = []
        for j in range(len(samples)):
            votes = [expert_labels[i][j] for i in range(n_experts)]
            majority_labels.append(sum(votes) > n_experts / 2)

        # Use first expert as "detector" to compute P/R
        tp = sum(1 for i in range(len(samples))
                 if expert_labels[0][i] and majority_labels[i])
        fp = sum(1 for i in range(len(samples))
                 if expert_labels[0][i] and not majority_labels[i])
        fn = sum(1 for i in range(len(samples))
                 if not expert_labels[0][i] and majority_labels[i])

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0

        # Wilson score interval for accuracy
        ci = self._wilson_interval(
            int(ceiling_accuracy * len(samples)),
            len(samples)
        )

        estimate = CeilingEstimate(
            task_id=task_id,
            method=CeilingMethod.HUMAN_EXPERT,
            ceiling_accuracy=ceiling_accuracy,
            ceiling_recall=recall,
            ceiling_precision=precision,
            confidence_interval=ci,
            sample_size=len(samples),
            notes=f"Based on {n_experts} expert panel"
        )

        self.estimates.append(estimate)
        return estimate

    def compute_ensemble_ceiling(
        self,
        task_id: str,
        samples: List[Dict],
        detectors: List,
        ground_truth: List[bool]
    ) -> CeilingEstimate:
        """
        Compute ceiling using best-of-N detector ensemble.

        The idea: if we had a perfect oracle that always picked
        the correct detector for each sample, what would performance be?
        """
        n_samples = len(samples)
        correct = 0

        for i, sample in enumerate(samples):
            # Check if ANY detector got it right
            any_correct = False
            for detector in detectors:
                pred = detector.predict(sample)
                if pred == ground_truth[i]:
                    any_correct = True
                    break

            if any_correct:
                correct += 1

        ceiling_accuracy = correct / n_samples

        # For this method, recall ceiling is if we OR all positive predictions
        all_positives = set()
        for detector in detectors:
            for i, sample in enumerate(samples):
                if detector.predict(sample):
                    all_positives.add(i)

        actual_positives = {i for i, gt in enumerate(ground_truth) if gt}
        recall_ceiling = len(all_positives & actual_positives) / len(actual_positives) \
            if actual_positives else 0

        ci = self._wilson_interval(correct, n_samples)

        estimate = CeilingEstimate(
            task_id=task_id,
            method=CeilingMethod.ENSEMBLE_BEST,
            ceiling_accuracy=ceiling_accuracy,
            ceiling_recall=recall_ceiling,
            ceiling_precision=0.0,  # Not meaningful for best-of-N
            confidence_interval=ci,
            sample_size=n_samples,
            notes=f"Best-of-{len(detectors)} oracle selection"
        )

        self.estimates.append(estimate)
        return estimate

    def compute_information_theoretic_bound(
        self,
        task_id: str,
        samples: List[Dict],
        feature_entropy: float,
        label_entropy: float,
        mutual_information: float
    ) -> CeilingEstimate:
        """
        Compute theoretical ceiling from information theory.

        Ceiling = MI(X;Y) / H(Y)

        Where:
            MI(X;Y) = mutual information between features and labels
            H(Y) = entropy of labels

        This gives the fraction of label uncertainty that can
        theoretically be resolved by the features.
        """
        if label_entropy == 0:
            ceiling = 1.0
        else:
            # Normalized mutual information
            ceiling = min(mutual_information / label_entropy, 1.0)

        estimate = CeilingEstimate(
            task_id=task_id,
            method=CeilingMethod.INFORMATION_THEORETIC,
            ceiling_accuracy=ceiling,
            ceiling_recall=ceiling,  # Theoretical bound applies to both
            ceiling_precision=ceiling,
            confidence_interval=(ceiling * 0.95, min(ceiling * 1.05, 1.0)),
            sample_size=len(samples),
            notes=f"MI={mutual_information:.3f}, H(Y)={label_entropy:.3f}"
        )

        self.estimates.append(estimate)
        return estimate

    def _mock_expert_labels(
        self,
        samples: List[Dict],
        expert_id: int
    ) -> List[bool]:
        """Generate mock expert labels for demonstration."""
        import random
        random.seed(42 + expert_id)

        labels = []
        for sample in samples:
            # Simulate ~90% expert accuracy with some disagreement
            if sample.get("is_harmful", False):
                # True positive rate varies by expert
                labels.append(random.random() < (0.85 + expert_id * 0.03))
            else:
                # True negative rate
                labels.append(random.random() > (0.90 + expert_id * 0.02))

        return labels

    def _wilson_interval(
        self,
        successes: int,
        total: int,
        confidence: float = 0.95
    ) -> Tuple[float, float]:
        """Compute Wilson score confidence interval."""
        if total == 0:
            return (0.0, 1.0)

        from math import sqrt

        z = 1.96  # 95% confidence
        p = successes / total

        denominator = 1 + z**2 / total
        center = (p + z**2 / (2 * total)) / denominator
        spread = z * sqrt(p * (1 - p) / total + z**2 / (4 * total**2)) / denominator

        return (max(0, center - spread), min(1, center + spread))

    def get_ceiling_gap(
        self,
        task_id: str,
        detector_accuracy: float
    ) -> Dict:
        """
        Compute gap between detector and ceiling.

        Returns guidance on whether to improve detector or accept current performance.
        """
        task_estimates = [e for e in self.estimates if e.task_id == task_id]

        if not task_estimates:
            return {"error": f"No ceiling estimate for task {task_id}"}

        # Use most reliable ceiling (human expert preferred)
        ceiling = None
        for method in [CeilingMethod.HUMAN_EXPERT, CeilingMethod.ENSEMBLE_BEST,
                       CeilingMethod.INFORMATION_THEORETIC]:
            ceiling = next((e for e in task_estimates if e.method == method), None)
            if ceiling:
                break

        if not ceiling:
            return {"error": "No valid ceiling estimate found"}

        gap = ceiling.ceiling_accuracy - detector_accuracy
        relative_gap = gap / ceiling.ceiling_accuracy if ceiling.ceiling_accuracy > 0 else 0

        if relative_gap < 0.05:
            recommendation = "Near-optimal: Focus on other priorities"
        elif relative_gap < 0.15:
            recommendation = "Good: Marginal improvements possible"
        elif relative_gap < 0.30:
            recommendation = "Room for improvement: Consider detector enhancements"
        else:
            recommendation = "Large gap: Significant improvement opportunity"

        return {
            "task_id": task_id,
            "detector_accuracy": detector_accuracy,
            "ceiling_accuracy": ceiling.ceiling_accuracy,
            "ceiling_method": ceiling.method.value,
            "absolute_gap": gap,
            "relative_gap": relative_gap,
            "recommendation": recommendation,
            "ceiling_ci": ceiling.confidence_interval
        }

    def get_summary(self) -> Dict:
        """Get summary of all ceiling estimates."""
        by_task = {}
        for est in self.estimates:
            if est.task_id not in by_task:
                by_task[est.task_id] = {}
            by_task[est.task_id][est.method.value] = {
                "accuracy": est.ceiling_accuracy,
                "recall": est.ceiling_recall,
                "ci": est.confidence_interval
            }

        return {
            "total_estimates": len(self.estimates),
            "tasks_covered": len(by_task),
            "by_task": by_task
        }


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    oracle = CeilingOracle()

    # Generate mock samples
    samples = [
        {"id": i, "is_harmful": i % 3 == 0}
        for i in range(100)
    ]

    # Compute human expert ceiling
    human_ceiling = oracle.compute_human_ceiling(
        task_id="intent_detection",
        samples=samples,
        n_experts=3
    )

    print("=== Human Expert Ceiling ===")
    print(f"Accuracy: {human_ceiling.ceiling_accuracy:.1%}")
    print(f"95% CI: [{human_ceiling.confidence_interval[0]:.1%}, "
          f"{human_ceiling.confidence_interval[1]:.1%}]")

    # Compute gap analysis
    detector_accuracy = 0.72
    gap = oracle.get_ceiling_gap("intent_detection", detector_accuracy)

    print("\n=== Gap Analysis ===")
    print(f"Detector: {gap['detector_accuracy']:.1%}")
    print(f"Ceiling: {gap['ceiling_accuracy']:.1%}")
    print(f"Gap: {gap['absolute_gap']:.1%}")
    print(f"Recommendation: {gap['recommendation']}")
