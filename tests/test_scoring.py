# tests/test_scoring.py
import pandas as pd
import pytest

import scoring
from data import PIPELINE_COLUMN, METRIC_IDS


def _raw(rows):
    # rows: list of (pipeline, accuracy, contiguity, decontam, replicon)
    return pd.DataFrame(rows, columns=[PIPELINE_COLUMN, *METRIC_IDS])


def test_normalize_higher_is_better_for_contiguity():
    df = _raw([
        ("a", 2.0, 0.90, 1, 1),
        ("b", 2.0, 0.95, 1, 1),
    ])
    out = scoring.normalize_metrics(df)
    assert out.loc[out[PIPELINE_COLUMN] == "b", "contiguity"].iloc[0] == 100.0
    assert out.loc[out[PIPELINE_COLUMN] == "a", "contiguity"].iloc[0] == 1.0


def test_normalize_lower_is_better_for_accuracy():
    df = _raw([
        ("a", 1.5, 0.90, 1, 1),
        ("b", 3.5, 0.90, 1, 1),
    ])
    out = scoring.normalize_metrics(df)
    assert out.loc[out[PIPELINE_COLUMN] == "a", "accuracy"].iloc[0] == 100.0
    assert out.loc[out[PIPELINE_COLUMN] == "b", "accuracy"].iloc[0] == 1.0


def test_normalize_floors_worst_to_one_not_zero():
    df = _raw([
        ("best", 1.0, 0.99, 0, 0),
        ("worst", 5.0, 0.80, 5, 5),
    ])
    out = scoring.normalize_metrics(df)
    worst = out[out[PIPELINE_COLUMN] == "worst"][METRIC_IDS].to_numpy()
    assert (worst == 1.0).all()


def test_normalize_constant_column_scores_ceiling():
    df = _raw([
        ("a", 2.0, 0.90, 1, 1),
        ("b", 2.5, 0.90, 1, 1),
    ])
    out = scoring.normalize_metrics(df)
    # decontam identical for both -> both score the ceiling (no division by zero)
    assert (out["decontam"] == 100.0).all()


def test_score_pipelines_weighted_geometric_mean_math():
    # Single pipeline, known normalized scores -> hand-computed geometric mean.
    normalized = pd.DataFrame({
        PIPELINE_COLUMN: ["solo"],
        "accuracy": [90.0],
        "contiguity": [80.0],
        "decontam": [100.0],
        "replicon": [40.0],
    })
    weights = {"accuracy": 50, "contiguity": 20, "decontam": 20, "replicon": 10}
    ranked = scoring.score_pipelines(normalized, weights)
    expected = (90.0**50 * 80.0**20 * 100.0**20 * 40.0**10) ** (1 / 100)
    assert ranked.loc[0, "score"] == pytest.approx(expected, abs=0.05)


def test_score_pipelines_reranks_with_weights():
    normalized = pd.DataFrame({
        PIPELINE_COLUMN: ["accurate", "contiguous"],
        "accuracy": [100.0, 1.0],
        "contiguity": [1.0, 100.0],
        "decontam": [50.0, 50.0],
        "replicon": [50.0, 50.0],
    })
    acc_heavy = scoring.score_pipelines(
        normalized, {"accuracy": 70, "contiguity": 10, "decontam": 10, "replicon": 10}
    )
    con_heavy = scoring.score_pipelines(
        normalized, {"accuracy": 10, "contiguity": 70, "decontam": 10, "replicon": 10}
    )
    assert acc_heavy.loc[0, "pipeline"] == "accurate"
    assert con_heavy.loc[0, "pipeline"] == "contiguous"


def test_score_pipelines_rank_column_is_one_based_and_sorted():
    normalized = pd.DataFrame({
        PIPELINE_COLUMN: ["low", "high"],
        "accuracy": [10.0, 90.0],
        "contiguity": [10.0, 90.0],
        "decontam": [10.0, 90.0],
        "replicon": [10.0, 90.0],
    })
    ranked = scoring.score_pipelines(
        normalized, {"accuracy": 25, "contiguity": 25, "decontam": 25, "replicon": 25}
    )
    assert list(ranked["rank"]) == [1, 2]
    assert ranked.loc[0, "pipeline"] == "high"
    assert list(ranked.columns) == ["rank", "pipeline", "score"]

