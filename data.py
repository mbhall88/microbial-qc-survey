"""Simulated benchmark leaderboard data and metric metadata.

Single source of truth for the live leaderboard. Holds each pipeline's RAW
per-metric values plus per-metric metadata (display label and direction).
Values are simulated using real pipeline names and real benchmark ballparks,
hand-crafted with deliberate trade-offs so different pipelines win on
different metrics.
"""
from __future__ import annotations

import pandas as pd

# Metric identifiers — used as DataFrame column names AND weight keys (w_<id>).
METRIC_ACCURACY = "accuracy"
METRIC_CONTIGUITY = "contiguity"
METRIC_DECONTAM = "decontam"
METRIC_REPLICON = "replicon"

# Per-metric metadata. direction "higher" => higher raw value is better;
# "lower" => lower raw value is better.
METRICS = [
    {"id": METRIC_ACCURACY,   "label": "Assembly Accuracy (Mismatches & Indels)",          "direction": "lower"},
    {"id": METRIC_CONTIGUITY, "label": "Assembly Contiguity (NGA50)",                       "direction": "higher"},
    {"id": METRIC_DECONTAM,   "label": "Contamination Removal (Residual Adapters/Barcodes)","direction": "lower"},
    {"id": METRIC_REPLICON,   "label": "Missed Replicons (Chromosomes & Plasmids)",         "direction": "lower"},
]

METRIC_IDS = [m["id"] for m in METRICS]

PIPELINE_COLUMN = "pipeline"

# Simulated raw per-pipeline metric values (ballparks from the real benchmark table):
#   accuracy   = combined errors per 100kbp (mismatches + indels), lower better, ~1.5–4.0
#   contiguity = NGA50-normalised,                                  higher better, ~0.88–0.97
#   decontam   = contamination count,                               lower better, integer 0–3
#   replicon   = missed replicon count (reference replicons absent  lower better, 0–5
#                from the output assembly)
# Crafted with trade-offs so the leaderboard reshuffles as the weights change.
_RAW_ROWS = [
    # pipeline,                 accuracy, contiguity, decontam, replicon
    ("chopper-porechop_abi",    1.6,      0.969,      2,        1),  # great accuracy, contaminated
    ("fastplong-all",           2.1,      0.962,      0,        2),  # clean, mid accuracy
    ("filtlong-porechop_abi",   1.5,      0.934,      0,        3),  # best accuracy + clean, misses replicons
    ("filtlong-untrimmed",      1.9,      0.953,      1,        0),  # all replicons recovered
    ("seqkit-dorado",           2.6,      0.969,      3,        1),  # top contiguity, dirtiest
    ("unprocessed-dorado",      3.1,      0.947,      2,        4),  # weak all-round
    ("seqkit-barbell",          2.3,      0.915,      1,        5),  # worst replicons
    ("unprocessed-untrimmed",   4.0,      0.882,      1,        2),  # worst accuracy & contiguity
]


def get_pipeline_data() -> pd.DataFrame:
    """Return a fresh DataFrame of raw per-pipeline metric values.

    Columns: pipeline, accuracy, contiguity, decontam, replicon. A new DataFrame
    is built on every call so callers never mutate the module-level source data.
    """
    return pd.DataFrame(_RAW_ROWS, columns=[PIPELINE_COLUMN, *METRIC_IDS])
