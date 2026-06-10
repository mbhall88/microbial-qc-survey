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


def score_pipelines(normalized_df: pd.DataFrame, weights: dict) -> pd.DataFrame:
    """Rank pipelines by the weighted geometric mean of their normalized scores.

    weights maps metric id -> weight (expected to sum to 100). FinalScore =
    (∏ Sᵢ^wᵢ)^(1/Σwᵢ), computed in log space for numerical stability. Returns a
    new DataFrame with columns [rank, pipeline, score], sorted by score
    descending, with a 1-based rank and score rounded to 2 decimals.
    """
    weight_values = np.array([weights[m] for m in METRIC_IDS], dtype=float)
    weight_sum = weight_values.sum()
    if weight_sum <= 0:
        raise ValueError("weights must sum to a positive value")

    score_matrix = normalized_df[METRIC_IDS].to_numpy(dtype=float)
    # (∏ Sᵢ^wᵢ)^(1/Σw) = exp( (Σ wᵢ·ln Sᵢ) / Σw )
    log_scores = np.log(score_matrix)
    final_scores = np.exp(log_scores @ weight_values / weight_sum)

    ranked = pd.DataFrame({
        "pipeline": normalized_df[PIPELINE_COLUMN].to_numpy(),
        "score": np.round(final_scores, 2),
    })
    ranked = ranked.sort_values("score", ascending=False, kind="stable").reset_index(drop=True)
    ranked.insert(0, "rank", ranked.index + 1)
    return ranked

