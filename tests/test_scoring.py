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
