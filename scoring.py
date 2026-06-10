"""Pure scoring logic for the leaderboard. No Streamlit imports.

normalize_metrics: raw per-metric values -> direction-aware 0–100 scores, floored to [1, 100].
score_pipelines:   weighted geometric mean of normalized scores -> ranked DataFrame.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from data import METRICS, METRIC_IDS, PIPELINE_COLUMN

# Floor applied to normalized scores so a single worst-in-class metric (which
# min-max maps to 0) cannot zero the entire geometric-mean product.
SCORE_FLOOR = 1.0
SCORE_CEILING = 100.0


def normalize_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Min-max normalize each metric column to a 0–100 'goodness' score.

    Direction-aware: 'higher' metrics use (x-min)/(max-min); 'lower' metrics use
    (max-x)/(max-min). Results are clamped to [1, 100]. When a column is constant
    (max == min) every pipeline scores the ceiling. Returns a new DataFrame with
    the pipeline column plus one normalized score column per metric.
    """
    normalized = pd.DataFrame({PIPELINE_COLUMN: df[PIPELINE_COLUMN].to_numpy()})
    for metric in METRICS:
        col = metric["id"]
        values = df[col].to_numpy(dtype=float)
        lo, hi = values.min(), values.max()
        span = hi - lo
        if span == 0:
            scores = np.full(values.shape, SCORE_CEILING)
        elif metric["direction"] == "higher":
            scores = (values - lo) / span * 100.0
        else:  # lower is better
            scores = (hi - values) / span * 100.0
        normalized[col] = np.clip(scores, SCORE_FLOOR, SCORE_CEILING)
    return normalized
