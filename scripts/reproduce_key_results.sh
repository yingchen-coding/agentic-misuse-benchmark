#!/bin/bash
# Reproduce Key Results
# ---------------------
# This script runs the maintained benchmark entry point for every bundled
# detector and writes machine-readable CSV outputs for inspection.

set -euo pipefail

echo "========================================"
echo "Agentic Misuse Benchmark - Reproduce Key Results"
echo "Benchmark Version: v1.0.0"
echo "========================================"
echo ""

# Configuration
OUTPUT_DIR="${OUTPUT_DIR:-results/reproduced_$(date +%Y%m%d_%H%M%S)}"
DETECTORS=(rules classifier intent)
CATEGORIES=(prompt_injection policy_erosion intent_drift coordinated_misuse)

mkdir -p "$OUTPUT_DIR"

echo "Output directory: $OUTPUT_DIR"
echo ""

# Step 1: Show benchmark inventory
echo "Step 1/4: Listing benchmark inventory..."
echo "----------------------------------------"
python run_benchmark.py --list-scenarios > "$OUTPUT_DIR/scenarios.txt"
python run_benchmark.py --list-detectors > "$OUTPUT_DIR/detectors.txt"
cat "$OUTPUT_DIR/detectors.txt"

echo ""

# Step 2: Run all detectors on the full curated scenario set
echo "Step 2/4: Evaluating bundled detectors..."
echo "----------------------------------------"

for detector in "${DETECTORS[@]}"; do
    echo "  Running $detector..."
    python run_benchmark.py \
        --detector "$detector" \
        --output "$OUTPUT_DIR/${detector}.csv"
done

echo ""

# Step 3: Compare detectors in one run
echo "Step 3/4: Comparing detectors..."
echo "----------------------------------------"

python run_benchmark.py \
    --compare "$(IFS=,; echo "${DETECTORS[*]}")" \
    --output "$OUTPUT_DIR/comparison.csv"

echo ""

# Step 4: Run category smoke checks for coverage
echo "Step 4/4: Evaluating rules baseline by category..."
echo "----------------------------------------"

for category in "${CATEGORIES[@]}"; do
    echo "  Running category $category..."
    python run_benchmark.py \
        --detector rules \
        --category "$category" \
        --output "$OUTPUT_DIR/rules_${category}.csv"
done

echo ""
echo "========================================"
echo "Reproduction complete."
echo "Results saved to: $OUTPUT_DIR"
echo "========================================"
echo ""
echo "To verify:"
echo "  1. Check $OUTPUT_DIR/*.csv for detector outputs"
echo "  2. Re-run with OUTPUT_DIR=/tmp/agentic-misuse-repro for clean local tests"
echo "  3. Generate plots with: python run_benchmark.py --detector rules --visualize"
