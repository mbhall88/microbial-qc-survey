# Microbial QC Survey Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Streamlit app that collects community priority weights over four assembly-QC metrics (constant-sum to 100) and shows a live leaderboard re-ranking benchmark pipelines, persisting each submission to Google Sheets with a local-CSV fallback.

**Architecture:** Thin Streamlit UI (`app.py`) over three pure/low-dependency modules: `data.py` (simulated raw leaderboard values + metric metadata), `scoring.py` (direction-aware min-max normalization + weighted geometric mean ranking, no Streamlit import), and `storage.py` (`append_response` → Google Sheets when credentials exist, else CSV). All real logic lives in the testable modules; the UI orchestrates them.

**Tech Stack:** Python 3.12, `uv` for env/deps, Streamlit, pandas, numpy, gspread + google-auth (Sheets backend), pytest.

---

## File Structure

| File | Responsibility |
|---|---|
| `pyproject.toml` | Project metadata, deps, pytest config (`pythonpath = ["."]`) |
| `data.py` | Metric metadata (id, label, direction) + simulated raw per-pipeline values; `get_pipeline_data()` |
| `scoring.py` | `normalize_metrics()` (0–100, direction-aware, `[1,100]` floor) + `score_pipelines()` (weighted geometric mean → ranked DataFrame) |
| `storage.py` | `append_response(row)` → Sheets or CSV fallback; `RESPONSE_FIELDS` schema |
| `app.py` | Streamlit page: title, info line, 4 budget-capped sliders, live leaderboard, submit. Pure helpers `remaining_budget()` / `slider_cap()` |
| `.streamlit/secrets.toml.example` | Template for the Google service-account credentials |
| `README.md` | Run/deploy instructions + citability/archival notes |
| `tests/test_data.py` | Shape/columns of `get_pipeline_data()` |
| `tests/test_scoring.py` | Normalization direction, floor, geometric-mean math, re-ranking |
| `tests/test_storage.py` | CSV header-once, append, stable schema, fallback |
| `tests/test_app.py` | Pure budget helpers |

`.gitignore` already exists and ignores `.streamlit/secrets.toml`, `survey_responses.csv`, `.venv/`, `__pycache__/`.

---

## Task 0: Project scaffold & dependencies

**Files:**
- Create: `pyproject.toml`
- Create: `tests/__init__.py` (empty, marks tests dir)

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "microbial-qc-survey"
version = "0.1.0"
description = "Streamlit survey collecting community priority weights for a microbial genomics benchmark."
requires-python = ">=3.10"
dependencies = [
    "streamlit>=1.40",
    "pandas>=2.0",
    "numpy>=1.26",
    "gspread>=6.0",
    "google-auth>=2.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
]

[tool.uv]
package = false

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 2: Create empty `tests/__init__.py`**

```python
```

(Write an empty file.)

- [ ] **Step 3: Create the environment and install dependencies**

Run: `uv sync`
Expected: creates `.venv/` and `uv.lock`, installs streamlit, pandas, numpy, gspread, google-auth, pytest. Ends with a summary like `Installed N packages`.

- [ ] **Step 4: Verify pytest runs (no tests yet)**

Run: `uv run pytest -q`
Expected: exits 0 with "no tests ran" (collected 0 items).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock tests/__init__.py
git commit -m "chore: scaffold uv project with deps and pytest config"
```

---

## Task 1: `data.py` — metric metadata & simulated leaderboard values

**Files:**
- Create: `data.py`
- Test: `tests/test_data.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_data.py
import data


def test_metric_ids_and_metadata_are_consistent():
    assert data.METRIC_IDS == ["accuracy", "contiguity", "decontam", "replicon"]
    directions = {m["id"]: m["direction"] for m in data.METRICS}
    assert directions == {
        "accuracy": "lower",
        "contiguity": "higher",
        "decontam": "lower",
        "replicon": "lower",
    }
    # Every metric has a non-empty human label.
    assert all(m["label"] for m in data.METRICS)


def test_get_pipeline_data_shape_and_columns():
    df = data.get_pipeline_data()
    assert list(df.columns) == [data.PIPELINE_COLUMN, *data.METRIC_IDS]
    assert len(df) >= 6  # representative subset of pipelines
    assert df[data.PIPELINE_COLUMN].is_unique


def test_get_pipeline_data_returns_fresh_copy():
    first = data.get_pipeline_data()
    first.loc[0, "accuracy"] = 999.0
    second = data.get_pipeline_data()
    assert second.loc[0, "accuracy"] != 999.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_data.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'data'`.

- [ ] **Step 3: Write `data.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_data.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add data.py tests/test_data.py
git commit -m "feat: add metric metadata and simulated leaderboard data"
```

---

## Task 2: `scoring.normalize_metrics` — direction-aware 0–100 with floor

**Files:**
- Create: `scoring.py`
- Test: `tests/test_scoring.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_scoring.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scoring'`.

- [ ] **Step 3: Write `scoring.py` (normalize only for now)**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_scoring.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add scoring.py tests/test_scoring.py
git commit -m "feat: add direction-aware min-max normalization with floor"
```

---

## Task 3: `scoring.score_pipelines` — weighted geometric mean & ranking

**Files:**
- Modify: `scoring.py` (add `score_pipelines`)
- Modify: `tests/test_scoring.py` (add tests)

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_scoring.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scoring.py -v`
Expected: FAIL with `AttributeError: module 'scoring' has no attribute 'score_pipelines'`.

- [ ] **Step 3: Add `score_pipelines` to `scoring.py`**

Append to `scoring.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scoring.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add scoring.py tests/test_scoring.py
git commit -m "feat: add weighted geometric mean scoring and ranking"
```

---

## Task 4: `storage.append_response` — CSV fallback + Sheets backend

**Files:**
- Create: `storage.py`
- Test: `tests/test_storage.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storage.py
import csv

import storage


def test_append_writes_header_once_and_appends_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "_sheets_configured", lambda: False)
    csv_path = tmp_path / "responses.csv"
    row1 = {"timestamp": "t1", "w_accuracy": 40, "w_contiguity": 30, "w_decontam": 20, "w_replicon": 10}
    row2 = {"timestamp": "t2", "w_accuracy": 25, "w_contiguity": 25, "w_decontam": 25, "w_replicon": 25}

    backend1 = storage.append_response(row1, csv_path=csv_path)
    backend2 = storage.append_response(row2, csv_path=csv_path)

    assert backend1 == "csv" and backend2 == "csv"
    with csv_path.open(newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == storage.RESPONSE_FIELDS          # one header
    assert len(rows) == 3                               # header + two data rows
    assert rows[1] == ["t1", "40", "30", "20", "10"]


def test_append_uses_stable_schema_ignoring_extra_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "_sheets_configured", lambda: False)
    csv_path = tmp_path / "responses.csv"
    row = {"timestamp": "t", "w_accuracy": 25, "w_contiguity": 25, "w_decontam": 25,
           "w_replicon": 25, "unexpected": "x"}
    storage.append_response(row, csv_path=csv_path)
    with csv_path.open(newline="") as handle:
        header = next(csv.reader(handle))
    assert header == storage.RESPONSE_FIELDS            # no 'unexpected' column


def test_falls_back_to_csv_when_sheets_not_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "_sheets_configured", lambda: False)
    csv_path = tmp_path / "responses.csv"
    backend = storage.append_response(
        {"timestamp": "t", "w_accuracy": 25, "w_contiguity": 25, "w_decontam": 25, "w_replicon": 25},
        csv_path=csv_path,
    )
    assert backend == "csv"
    assert csv_path.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_storage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'storage'`.

- [ ] **Step 3: Write `storage.py`**

```python
"""Response persistence with a Google Sheets backend and a local CSV fallback.

append_response(row) writes one survey response. If Google service-account
credentials are present in st.secrets, the row is appended to the configured
Google Sheet; otherwise it is appended to a local CSV (header written once).
"""
from __future__ import annotations

import csv
from pathlib import Path

CSV_PATH = Path("survey_responses.csv")

# Column order for the persisted response row (the saved schema).
RESPONSE_FIELDS = [
    "timestamp",
    "w_accuracy",
    "w_contiguity",
    "w_decontam",
    "w_replicon",
]


def append_response(row: dict, csv_path: Path = CSV_PATH) -> str:
    """Append one response row to durable storage. Returns the backend used.

    Uses Google Sheets when credentials are configured; otherwise falls back to a
    local CSV at csv_path (writing a header row if the file does not yet exist).
    Raises on write failure so the caller can surface an error to the user.
    """
    if _sheets_configured():
        _append_to_sheet(row)
        return "sheets"
    _append_to_csv(row, csv_path)
    return "csv"


def _append_to_csv(row: dict, csv_path: Path) -> None:
    ordered = {field: row.get(field, "") for field in RESPONSE_FIELDS}
    write_header = not csv_path.exists()
    with csv_path.open("a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESPONSE_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(ordered)


def _sheets_configured() -> bool:
    """True when Google service-account creds are available in Streamlit secrets."""
    try:
        import streamlit as st
    except ModuleNotFoundError:
        return False
    try:
        return "gcp_service_account" in st.secrets
    except Exception:
        # st.secrets access raises if no secrets.toml exists; treat as unconfigured.
        return False


def _append_to_sheet(row: dict) -> None:
    import gspread
    import streamlit as st
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), scopes=scopes
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_key(st.secrets["sheet_id"]).sheet1
    sheet.append_row([row.get(field, "") for field in RESPONSE_FIELDS])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_storage.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add storage.py tests/test_storage.py
git commit -m "feat: add response storage with Sheets backend and CSV fallback"
```

---

## Task 5: `app.py` — Streamlit UI with budget-capped sliders & live leaderboard

**Files:**
- Create: `app.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Write the failing test (pure budget helpers)**

```python
# tests/test_app.py
import app


def test_remaining_budget_full_allocation_is_zero():
    weights = {"accuracy": 25, "contiguity": 25, "decontam": 25, "replicon": 25}
    assert app.remaining_budget(weights) == 0


def test_remaining_budget_underallocated():
    weights = {"accuracy": 10, "contiguity": 20, "decontam": 5, "replicon": 5}
    assert app.remaining_budget(weights) == 60


def test_slider_cap_is_value_plus_unallocated():
    weights = {"accuracy": 10, "contiguity": 20, "decontam": 5, "replicon": 5}
    # remaining = 60; cap for accuracy = 10 + 60 = 70
    assert app.slider_cap("accuracy", weights) == 70


def test_slider_cap_locks_at_current_value_when_fully_allocated():
    weights = {"accuracy": 25, "contiguity": 25, "decontam": 25, "replicon": 25}
    # remaining 0 -> cap equals current value (slider can only go down)
    assert app.slider_cap("contiguity", weights) == 25
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_app.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app'`.

- [ ] **Step 3: Write `app.py`**

```python
"""Microbial QC Survey — Streamlit app.

Collects community priority weights over four assembly-QC metrics and shows a
live leaderboard that re-ranks benchmark pipelines as the weights change. Thin
UI layer: all logic lives in data.py / scoring.py / storage.py.
"""
from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

import data
import scoring
import storage

TOTAL_BUDGET = 100
DEFAULT_WEIGHT = 25  # 4 sliders × 25 = 100, valid by default


def _weight_key(metric_id: str) -> str:
    return f"w_{metric_id}"


def remaining_budget(weights: dict) -> int:
    """Unallocated points: 100 minus the sum of all current weights."""
    return TOTAL_BUDGET - sum(weights.values())


def slider_cap(metric_id: str, weights: dict) -> int:
    """Max a slider may reach: its current value plus the unallocated budget.

    Guarantees the four weights can never sum above 100.
    """
    return weights[metric_id] + remaining_budget(weights)


def _init_state() -> None:
    for metric in data.METRICS:
        key = _weight_key(metric["id"])
        if key not in st.session_state:
            st.session_state[key] = DEFAULT_WEIGHT


def _current_weights() -> dict:
    return {m["id"]: st.session_state[_weight_key(m["id"])] for m in data.METRICS}


def render_sliders() -> dict:
    """Render the four budget-capped sliders. Returns the current weights dict."""
    weights = _current_weights()
    for metric in data.METRICS:
        metric_id = metric["id"]
        st.slider(
            metric["label"],
            min_value=0,
            max_value=int(slider_cap(metric_id, weights)),
            key=_weight_key(metric_id),
        )
    return _current_weights()


def render_leaderboard(weights: dict) -> None:
    raw = data.get_pipeline_data()
    normalized = scoring.normalize_metrics(raw)
    ranked = scoring.score_pipelines(normalized, weights)
    st.dataframe(ranked, hide_index=True, use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="Microbial QC Survey", layout="centered")
    _init_state()

    st.title("Microbial QC Pipeline Priorities")
    st.write(
        "Set how much each assembly-QC metric should matter. Your weights help "
        "establish a **community-choice baseline** for ranking read-trimming and "
        "quality-filtering pipelines in an upcoming microbial genomics benchmark."
    )
    st.caption("Responses are anonymous and used for research.")

    st.subheader("Weight the metrics (must total 100)")
    weights = render_sliders()

    remaining = remaining_budget(weights)
    if remaining == 0:
        st.success("Unallocated budget: 0 — ready to submit.")
    else:
        st.warning(f"Unallocated budget: {remaining} — allocate all 100 points to submit.")

    st.subheader("Live leaderboard")
    st.caption("Re-ranks instantly as you move the sliders.")
    render_leaderboard(weights)

    if st.button("Submit Weights to Study", type="primary", disabled=remaining != 0):
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "w_accuracy": weights["accuracy"],
            "w_contiguity": weights["contiguity"],
            "w_decontam": weights["decontam"],
            "w_replicon": weights["replicon"],
        }
        try:
            backend = storage.append_response(row)
        except Exception as exc:  # surface, never crash the app
            st.error(f"Could not save your response: {exc}")
        else:
            st.toast("Thanks! Your weights were recorded.", icon="✅")
            st.success(f"Response saved ({backend}).")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_app.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS (all tests across data/scoring/storage/app — 17 passed).

- [ ] **Step 6: Manual smoke test of the running app**

Run: `uv run streamlit run app.py`
Expected: app opens in the browser. Verify:
- Four sliders start at 25 and "Unallocated budget: 0 — ready to submit." shows.
- Lower one slider; budget warning appears and Submit disables; raise another to spend the budget back to 0; Submit re-enables.
- Leaderboard reorders when you shift weight heavily onto one metric.
- Click Submit → success toast + "Response saved (csv)."; `survey_responses.csv` appears with a header and one row.
Then stop the server (Ctrl+C).

- [ ] **Step 7: Commit**

```bash
git add app.py tests/test_app.py
git commit -m "feat: add Streamlit UI with budget-capped sliders and live leaderboard"
```

---

## Task 6: Secrets template, README, final verification

**Files:**
- Create: `.streamlit/secrets.toml.example`
- Create: `README.md`

- [ ] **Step 1: Write `.streamlit/secrets.toml.example`**

```toml
# Copy this file to .streamlit/secrets.toml and fill it in to enable the Google
# Sheets backend. Without it, the app falls back to writing survey_responses.csv.
# .streamlit/secrets.toml is gitignored — never commit real credentials.

sheet_id = "your-google-sheet-id"

[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "survey-writer@your-project.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

- [ ] **Step 2: Write `README.md`**

````markdown
# Microbial QC Survey

A standalone Streamlit app that collects community priority weights over four
assembly-QC metrics and shows a live leaderboard re-ranking benchmark pipelines.
Weights establish a "community-choice baseline" for a microbial genomics
benchmarking paper. The saved payload is the four weights plus a timestamp; the
leaderboard is a live engagement demo only.

## Run locally

```bash
uv sync
uv run streamlit run app.py
```

With no Google credentials configured, responses append to a local
`survey_responses.csv` (created on first submit).

## Tests

```bash
uv run pytest
```

## Metrics

| Metric | Meaning | Better |
|---|---|---|
| Assembly Accuracy (Mismatches & Indels) | combined errors per 100 kbp | lower |
| Assembly Contiguity (NGA50) | normalised NGA50 | higher |
| Contamination Removal | residual adapter/barcode count | lower |
| Missed Replicons (Chromosomes & Plasmids) | reference replicons absent from the output assembly | lower |

Scoring: each metric is min-max normalised to 0–100 (direction-aware, floored to
`[1, 100]`), then combined with the user weights via a weighted geometric mean
`(∏ Sᵢ^wᵢ)^(1/Σwᵢ)`. The formula lives in `scoring.py` and can be swapped in one
place. Leaderboard values in `data.py` are simulated in the ballpark of the real
benchmark; they are not the literal published scores.

## Deploy (Streamlit Community Cloud)

1. Push this repo to GitHub.
2. Create the app at https://share.streamlit.io pointing at `app.py`.
3. Add the Google service-account credentials under the app's **Secrets**
   (same structure as `.streamlit/secrets.toml.example`). The app then writes
   durably to the configured Google Sheet instead of the local CSV.

## Citability

- **Durable collection** via Google Sheets (survives redeploys/restarts).
- **Archival + DOI:** when the survey closes, deposit the anonymised responses
  and this app code to Zenodo or OSF for a DOI, and cite that DOI in the paper.
- No demographics are collected — responses are non-identifying opinion weights.
````

- [ ] **Step 3: Confirm secrets are not tracked**

Run: `git status --porcelain`
Expected: shows `.streamlit/secrets.toml.example` and `README.md` as untracked, but NOT `.streamlit/secrets.toml` or `survey_responses.csv` (both gitignored). If `survey_responses.csv` appears, it was created by the manual smoke test — confirm it is listed in `.gitignore` and remains ignored.

- [ ] **Step 4: Run the full suite one more time**

Run: `uv run pytest -q`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add README.md .streamlit/secrets.toml.example
git commit -m "docs: add README and Google Sheets secrets template"
```

---

## Definition of Done

- `uv run pytest` passes (data, scoring, storage, app helpers).
- `uv run streamlit run app.py` shows four budget-capped sliders that always total ≤ 100, a live-reranking leaderboard, and a Submit button gated on budget == 0.
- Submitting appends a row to `survey_responses.csv` locally (or Google Sheets when credentials are present).
- No secrets committed; `.streamlit/secrets.toml.example` documents the Sheets setup.
- README documents local run, tests, deploy, and citability.
