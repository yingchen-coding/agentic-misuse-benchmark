"""
Analysis and visualization tools for the benchmark.
"""

from .visualize import (
    plot_erosion_curve,
    plot_detection_heatmap,
    plot_category_comparison,
    plot_erosion_over_turns,
    generate_report
)

__all__ = [
    'plot_erosion_curve',
    'plot_detection_heatmap',
    'plot_category_comparison',
    'plot_erosion_over_turns',
    'generate_report'
]
