"""
Distribution Shift Protocol: Manage train/test/holdout splits with temporal awareness.

Key insight: Safety evaluation data has temporal structure. Attacks evolve,
and a detector trained on 2023 attacks may fail on 2024 attacks.

This module implements:
1. Temporal splits (train on old, test on new)
2. Stratified splits (preserve attack type distribution)
3. Holdout management (golden test sets never touched during development)
4. Shift detection (monitor for distribution drift)
"""

import json
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from datetime import datetime
from enum import Enum


class SplitType(Enum):
    """Types of data splits."""
    TEMPORAL = "temporal"       # Train on past, test on future
    RANDOM = "random"           # Random assignment
    STRATIFIED = "stratified"   # Preserve class distribution
    ADVERSARIAL = "adversarial" # Deliberately OOD test set


class SplitRole(Enum):
    """Role of a data split."""
    TRAIN = "train"             # Model development
    VALIDATION = "validation"   # Hyperparameter tuning
    TEST = "test"               # Final evaluation
    HOLDOUT = "holdout"         # Golden set, never touch during dev


@dataclass
class DataSplit:
    """A data split with metadata."""
    split_id: str
    role: SplitRole
    sample_ids: List[str]
    created_at: str
    split_type: SplitType
    metadata: Dict = field(default_factory=dict)

    # Access tracking
    access_count: int = 0
    last_accessed: Optional[str] = None
    accessed_by: List[str] = field(default_factory=list)


@dataclass
class Sample:
    """A sample with temporal and category metadata."""
    sample_id: str
    timestamp: str
    category: str
    subcategory: str
    content_hash: str
    is_harmful: bool
    metadata: Dict = field(default_factory=dict)


class DistributionShiftManager:
    """
    Manage data splits with distribution shift awareness.

    Philosophy: Train/test contamination is a silent killer of
    evaluation validity. This manager enforces strict separation
    and tracks all access for audit.
    """

    def __init__(self, holdout_fraction: float = 0.1):
        self.samples: Dict[str, Sample] = {}
        self.splits: Dict[str, DataSplit] = {}
        self.holdout_fraction = holdout_fraction
        self.access_log: List[Dict] = []

    def add_sample(self, sample: Sample):
        """Add a sample to the pool."""
        self.samples[sample.sample_id] = sample

    def create_temporal_split(
        self,
        split_date: str,
        train_before: bool = True
    ) -> Dict[str, DataSplit]:
        """
        Create temporal train/test split.

        Args:
            split_date: ISO date string for split point
            train_before: If True, train on data before split_date

        Returns:
            Dict with 'train' and 'test' DataSplit objects
        """
        split_dt = datetime.fromisoformat(split_date.replace('Z', '+00:00'))

        train_ids = []
        test_ids = []

        for sample_id, sample in self.samples.items():
            sample_dt = datetime.fromisoformat(
                sample.timestamp.replace('Z', '+00:00')
            )

            if train_before:
                if sample_dt < split_dt:
                    train_ids.append(sample_id)
                else:
                    test_ids.append(sample_id)
            else:
                if sample_dt >= split_dt:
                    train_ids.append(sample_id)
                else:
                    test_ids.append(sample_id)

        now = datetime.now().isoformat()

        train_split = DataSplit(
            split_id=f"temporal_train_{split_date}",
            role=SplitRole.TRAIN,
            sample_ids=train_ids,
            created_at=now,
            split_type=SplitType.TEMPORAL,
            metadata={"split_date": split_date, "direction": "before" if train_before else "after"}
        )

        test_split = DataSplit(
            split_id=f"temporal_test_{split_date}",
            role=SplitRole.TEST,
            sample_ids=test_ids,
            created_at=now,
            split_type=SplitType.TEMPORAL,
            metadata={"split_date": split_date, "direction": "after" if train_before else "before"}
        )

        self.splits[train_split.split_id] = train_split
        self.splits[test_split.split_id] = test_split

        return {"train": train_split, "test": test_split}

    def create_stratified_split(
        self,
        train_fraction: float = 0.7,
        stratify_by: str = "category"
    ) -> Dict[str, DataSplit]:
        """
        Create stratified split preserving category distribution.

        Args:
            train_fraction: Fraction of data for training
            stratify_by: Field to stratify on ('category' or 'subcategory')
        """
        # Group by stratification key
        groups: Dict[str, List[str]] = {}
        for sample_id, sample in self.samples.items():
            key = getattr(sample, stratify_by, "unknown")
            if key not in groups:
                groups[key] = []
            groups[key].append(sample_id)

        train_ids = []
        test_ids = []

        # Split each group proportionally
        for key, ids in groups.items():
            # Deterministic shuffle using hash
            sorted_ids = sorted(ids, key=lambda x: hashlib.md5(x.encode()).hexdigest())
            split_point = int(len(sorted_ids) * train_fraction)
            train_ids.extend(sorted_ids[:split_point])
            test_ids.extend(sorted_ids[split_point:])

        now = datetime.now().isoformat()

        train_split = DataSplit(
            split_id=f"stratified_train_{stratify_by}",
            role=SplitRole.TRAIN,
            sample_ids=train_ids,
            created_at=now,
            split_type=SplitType.STRATIFIED,
            metadata={"stratify_by": stratify_by, "fraction": train_fraction}
        )

        test_split = DataSplit(
            split_id=f"stratified_test_{stratify_by}",
            role=SplitRole.TEST,
            sample_ids=test_ids,
            created_at=now,
            split_type=SplitType.STRATIFIED,
            metadata={"stratify_by": stratify_by, "fraction": 1 - train_fraction}
        )

        self.splits[train_split.split_id] = train_split
        self.splits[test_split.split_id] = test_split

        return {"train": train_split, "test": test_split}

    def create_holdout(
        self,
        holdout_id: str,
        sample_ids: Optional[List[str]] = None
    ) -> DataSplit:
        """
        Create a holdout set that should never be accessed during development.

        If sample_ids not provided, randomly selects holdout_fraction of data.
        """
        if sample_ids is None:
            # Random selection
            all_ids = list(self.samples.keys())
            sorted_ids = sorted(all_ids, key=lambda x: hashlib.md5(x.encode()).hexdigest())
            n_holdout = int(len(sorted_ids) * self.holdout_fraction)
            sample_ids = sorted_ids[:n_holdout]

        holdout = DataSplit(
            split_id=holdout_id,
            role=SplitRole.HOLDOUT,
            sample_ids=sample_ids,
            created_at=datetime.now().isoformat(),
            split_type=SplitType.RANDOM,
            metadata={"warning": "HOLDOUT - DO NOT ACCESS DURING DEVELOPMENT"}
        )

        self.splits[holdout_id] = holdout
        return holdout

    def access_split(
        self,
        split_id: str,
        accessor: str,
        purpose: str
    ) -> Optional[List[Sample]]:
        """
        Access a split with logging. Warns on holdout access.

        Args:
            split_id: ID of split to access
            accessor: Identifier of who/what is accessing
            purpose: Why the access is happening
        """
        if split_id not in self.splits:
            return None

        split = self.splits[split_id]

        # Log access
        self.access_log.append({
            "split_id": split_id,
            "accessor": accessor,
            "purpose": purpose,
            "timestamp": datetime.now().isoformat(),
            "role": split.role.value
        })

        # Update split metadata
        split.access_count += 1
        split.last_accessed = datetime.now().isoformat()
        if accessor not in split.accessed_by:
            split.accessed_by.append(accessor)

        # Warn on holdout access
        if split.role == SplitRole.HOLDOUT:
            print(f"WARNING: Accessing holdout set '{split_id}'!")
            print(f"  Accessor: {accessor}")
            print(f"  Purpose: {purpose}")
            print(f"  This access has been logged for audit.")

        # Return samples
        return [self.samples[sid] for sid in split.sample_ids if sid in self.samples]

    def detect_distribution_shift(
        self,
        split_a_id: str,
        split_b_id: str
    ) -> Dict:
        """
        Detect distribution shift between two splits.

        Useful for checking if test set has drifted from train set.
        """
        if split_a_id not in self.splits or split_b_id not in self.splits:
            return {"error": "Split not found"}

        split_a = self.splits[split_a_id]
        split_b = self.splits[split_b_id]

        samples_a = [self.samples[sid] for sid in split_a.sample_ids if sid in self.samples]
        samples_b = [self.samples[sid] for sid in split_b.sample_ids if sid in self.samples]

        # Compare category distributions
        dist_a = self._compute_distribution(samples_a, "category")
        dist_b = self._compute_distribution(samples_b, "category")

        # Compute JS divergence
        js_div = self._js_divergence(dist_a, dist_b)

        # Compare temporal distributions
        time_a = self._compute_time_stats(samples_a)
        time_b = self._compute_time_stats(samples_b)

        # Compare harm rate
        harm_a = sum(1 for s in samples_a if s.is_harmful) / len(samples_a) if samples_a else 0
        harm_b = sum(1 for s in samples_b if s.is_harmful) / len(samples_b) if samples_b else 0

        shift_detected = js_div > 0.1 or abs(harm_a - harm_b) > 0.15

        return {
            "split_a": split_a_id,
            "split_b": split_b_id,
            "category_js_divergence": js_div,
            "category_dist_a": dist_a,
            "category_dist_b": dist_b,
            "time_stats_a": time_a,
            "time_stats_b": time_b,
            "harm_rate_a": harm_a,
            "harm_rate_b": harm_b,
            "harm_rate_diff": abs(harm_a - harm_b),
            "shift_detected": shift_detected,
            "recommendation": (
                "CAUTION: Significant distribution shift detected"
                if shift_detected else "Distribution shift within acceptable bounds"
            )
        }

    def _compute_distribution(
        self,
        samples: List[Sample],
        field: str
    ) -> Dict[str, float]:
        """Compute distribution over a categorical field."""
        counts: Dict[str, int] = {}
        for sample in samples:
            val = getattr(sample, field, "unknown")
            counts[val] = counts.get(val, 0) + 1

        total = sum(counts.values())
        return {k: v / total for k, v in counts.items()} if total > 0 else {}

    def _compute_time_stats(self, samples: List[Sample]) -> Dict:
        """Compute temporal statistics."""
        if not samples:
            return {"min": None, "max": None, "median": None}

        timestamps = sorted([s.timestamp for s in samples])
        return {
            "min": timestamps[0],
            "max": timestamps[-1],
            "median": timestamps[len(timestamps) // 2],
            "count": len(timestamps)
        }

    def _js_divergence(
        self,
        p: Dict[str, float],
        q: Dict[str, float]
    ) -> float:
        """Compute Jensen-Shannon divergence between distributions."""
        import math

        # Get all keys
        keys = set(p.keys()) | set(q.keys())

        # Add smoothing
        eps = 1e-10
        p_smooth = {k: p.get(k, eps) for k in keys}
        q_smooth = {k: q.get(k, eps) for k in keys}

        # Compute M = (P + Q) / 2
        m = {k: (p_smooth[k] + q_smooth[k]) / 2 for k in keys}

        # KL(P||M)
        kl_pm = sum(p_smooth[k] * math.log(p_smooth[k] / m[k]) for k in keys)

        # KL(Q||M)
        kl_qm = sum(q_smooth[k] * math.log(q_smooth[k] / m[k]) for k in keys)

        return (kl_pm + kl_qm) / 2

    def get_audit_report(self) -> Dict:
        """Generate audit report of all split accesses."""
        holdout_accesses = [
            log for log in self.access_log
            if log["role"] == "holdout"
        ]

        return {
            "total_accesses": len(self.access_log),
            "holdout_accesses": len(holdout_accesses),
            "holdout_access_details": holdout_accesses,
            "splits_summary": {
                split_id: {
                    "role": split.role.value,
                    "access_count": split.access_count,
                    "accessed_by": split.accessed_by
                }
                for split_id, split in self.splits.items()
            },
            "contamination_risk": (
                "HIGH" if len(holdout_accesses) > 0 else "LOW"
            )
        }

    def get_lifecycle_status(self) -> Dict:
        """Get lifecycle status of all data splits."""
        return {
            "total_samples": len(self.samples),
            "total_splits": len(self.splits),
            "by_role": {
                role.value: len([s for s in self.splits.values() if s.role == role])
                for role in SplitRole
            },
            "by_type": {
                stype.value: len([s for s in self.splits.values() if s.split_type == stype])
                for stype in SplitType
            }
        }


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    manager = DistributionShiftManager(holdout_fraction=0.1)

    # Add mock samples
    categories = ["prompt_injection", "jailbreak", "social_engineering", "benign"]
    for i in range(200):
        sample = Sample(
            sample_id=f"sample_{i:04d}",
            timestamp=f"2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}T12:00:00Z",
            category=categories[i % len(categories)],
            subcategory=f"sub_{i % 3}",
            content_hash=hashlib.md5(f"content_{i}".encode()).hexdigest(),
            is_harmful=i % 3 != 3  # 75% harmful
        )
        manager.add_sample(sample)

    # Create temporal split
    print("=== Temporal Split ===")
    temporal = manager.create_temporal_split("2024-06-01")
    print(f"Train: {len(temporal['train'].sample_ids)} samples")
    print(f"Test: {len(temporal['test'].sample_ids)} samples")

    # Create stratified split
    print("\n=== Stratified Split ===")
    stratified = manager.create_stratified_split(train_fraction=0.7)
    print(f"Train: {len(stratified['train'].sample_ids)} samples")
    print(f"Test: {len(stratified['test'].sample_ids)} samples")

    # Create holdout
    print("\n=== Holdout Set ===")
    holdout = manager.create_holdout("golden_holdout_v1")
    print(f"Holdout: {len(holdout.sample_ids)} samples")

    # Detect distribution shift
    print("\n=== Distribution Shift ===")
    shift = manager.detect_distribution_shift(
        temporal['train'].split_id,
        temporal['test'].split_id
    )
    print(f"JS Divergence: {shift['category_js_divergence']:.3f}")
    print(f"Shift Detected: {shift['shift_detected']}")

    # Access with logging
    print("\n=== Access Audit ===")
    manager.access_split(temporal['train'].split_id, "trainer_v1", "model training")
    manager.access_split(holdout.split_id, "researcher", "final evaluation")

    audit = manager.get_audit_report()
    print(f"Total Accesses: {audit['total_accesses']}")
    print(f"Holdout Accesses: {audit['holdout_accesses']}")
    print(f"Contamination Risk: {audit['contamination_risk']}")
