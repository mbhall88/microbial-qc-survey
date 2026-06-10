# Microbial QC Survey — Design Spec

**Date:** 2026-06-10
**Status:** Approved (design), pending implementation plan

## 1. Purpose

A single-page Streamlit application that collects **community priority weights** over four
read-trimming / quality-filtering assembly metrics, captures light demographics, and shows a
**live leaderboard** that re-ranks benchmark pipelines as the participant moves the weight
sliders.

The weights establish a "community-choice baseline" for ranking pipelines in a microbial
genomics benchmarking paper. The **saved payload is demographics + the four weights**; the
leaderboard is a live engagement demo and never touches the saved data.

## 2. Scope & non-goals

In scope:
- Demographics capture (research area, sequencing depth).
- Four constant-sum weight sliders with a remaining-budget cap (always ≤ 100).
- A reactive leaderboard scoring real benchmark pipelines via a weighted geometric mean.
- Durable response capture to Google Sheets (with a local-CSV fallback for development).
- A consent/information statement gating submission.

Out of scope (documented for later, not built now):
- Analysis/reporting of collected responses.
- Zenodo/OSF deposit automation (documented as a manual archival step).
- Authentication or per-user response editing.

## 3. Decisions locked during brainstorming

| Decision | Choice |
|---|---|
| Constant-sum slider logic | **Remaining-budget cap** — each slider's max is `value + remaining_budget`; total never exceeds 100; submit enabled only when unallocated budget == 0 |
| Scoring formula | **Weighted geometric mean** over **all 4** metrics: `(∏ Sᵢ^wᵢ)^(1/Σwᵢ)` |
| Normalization | Min-max to 0–100 per metric, direction-aware, floored to `[1, 100]` to prevent zero-collapse |
| Pipeline names | Real names from the benchmark table (`<trimmer>-<basecaller>` pattern) |
| Storage | **Google Sheets** via server-side service account; **local CSV fallback** when no secrets present |
| Hosting | **Streamlit Community Cloud**, deployed from the GitHub repo |
| Consent | Information statement + "I consent" checkbox gating submission |
| Python tooling | `uv`-managed environment and dependencies |

## 4. Architecture

Modular, runs out-of-the-box locally (CSV fallback), deploys to Streamlit Community Cloud
(Sheets backend via secrets).

```
microbial-qc-survey/
├── app.py                 # Streamlit page: layout, wiring, submit handler (thin)
├── scoring.py             # normalize_metrics() + score_pipelines() — pure, swappable formula
├── data.py                # mock/real pipeline metric scores + per-metric metadata
├── storage.py             # append_response(): Google Sheets backend, CSV fallback
├── pyproject.toml         # deps: streamlit, pandas, numpy, gspread/streamlit-gsheets
├── .streamlit/
│   └── secrets.toml       # (gitignored) Google service-account creds for deployment
├── tests/
│   ├── test_scoring.py
│   └── test_storage.py
├── CITATION.md / README   # archival + DOI plan, consent text, ethics note
└── survey_responses.csv   # created on first submit when running on the CSV fallback
```

### Component responsibilities

- **`data.py`** — single source of truth for the leaderboard. Holds each pipeline's per-metric
  **0–100 normalized score** for the four survey metrics, plus per-metric metadata (display
  label, direction). The benchmark table already provides min-max normalized 0–100 per-metric
  scores, so those values are plugged in directly (no re-derivation). Exact column→metric
  mapping confirmed at wiring time (see §8).

- **`scoring.py`** — pure functions, **no Streamlit import** (independently unit-testable):
  - `normalize_metrics(df)` → min-max to 0–100 per metric, direction-aware, clamped to `[1,100]`.
    (No-op pass-through clamp if `data.py` already supplies normalized scores.)
  - `score_pipelines(normalized_df, weights)` → applies `(∏ Sᵢ^wᵢ)^(1/Σwᵢ)`, returns a DataFrame
    sorted by score descending with a `rank` column.

- **`storage.py`** — `append_response(row: dict) -> None`. If `st.secrets` contains Google
  service-account credentials, append a row to the configured Sheet; otherwise append to
  `survey_responses.csv` (writing a header row if the file is new). Immutable-style: builds a
  new row, no shared mutable state. Write wrapped in try/except surfacing a user-facing error.

- **`app.py`** — renders title/description, consent block, demographics, the four capped
  sliders, the live leaderboard, and the submit button; orchestrates the other modules. Kept
  thin — all real logic lives in `scoring.py` / `storage.py`.

## 5. Layout & form (per requirements)

1. **Title + description** — explains the "community-choice baseline" framing for ranking
   read-trimming / quality-filtering pipelines.
2. **Consent/information statement** — what is collected (research area, sequencing depth, four
   weights), that it is anonymous and voluntary and used for research, with an **"I consent"
   checkbox**.
3. **Demographics:**
   - Primary Research Area — `st.multiselect`: Clinical/AMR, Public Health, Plasmid Biology,
     Metagenomics, Industrial.
   - Target Sequencing Depth — `st.radio`: `<30x`, `30x–100x`, `>100x`.
4. **Four weight sliders** (the four core metrics):
   - Assembly Accuracy (Mismatches & Indels)
   - Assembly Contiguity (NGA50)
   - Contamination Removal (Residual Adapters/Barcodes)
   - Multi-Replicon Recovery (Missed Small Plasmids)
5. **Live leaderboard** — `st.dataframe` of pipelines re-ranked by current weights.
6. **Submit Weights to Study** button + success toast.

## 6. Slider logic — remaining-budget cap

- Four sliders initialise to **25 / 25 / 25 / 25** (valid by default; total = 100).
- Each slider's `max_value` is set dynamically to `current_value + remaining_budget`, where
  `remaining_budget = 100 - sum(all_slider_values)`. The total therefore can never exceed 100.
- A live indicator shows **"Unallocated budget: N"** — green at 0, amber otherwise.
- Submit is enabled only when `remaining_budget == 0` **and** consent is checked **and** at
  least one research area is selected.
- Slider state held in `st.session_state`; an `on_change` callback recomputes caps each rerun.

## 7. Data flow

```
sliders ──► weights {w_accuracy, w_contiguity, w_decontam, w_plasmid}
                │
                ▼ (every rerun)
   scoring.score_pipelines(data.normalized_scores, weights)
                │
                ▼
        st.dataframe leaderboard (sorted by score desc, rank column)

[Submit click] ─► assemble row:
   { timestamp, research_areas, seq_depth,
     w_accuracy, w_contiguity, w_decontam, w_plasmid }
   ─► storage.append_response(row) ─► st.toast / st.success
```

Saved schema (one row per submission):
`timestamp, research_areas, seq_depth, w_accuracy, w_contiguity, w_decontam, w_plasmid`

## 8. Open implementation detail — column→metric mapping

The benchmark table supplies real pipeline names plus several min-max normalized 0–100
per-metric columns. Before seeding `data.py`, confirm which normalized column maps to each of
the four survey metrics (accuracy, contiguity/NGA50, contamination, replicon recovery), and the
direction for any raw values used. Replicon recovery is min-max'd as **lower-missed = better**,
analogous to contaminants. This is a data-wiring detail, not an architecture change.

## 9. Scoring math (reference)

For pipeline *p* with normalized metric scores `Sᵢ ∈ [1, 100]` and user weights `wᵢ`
(summing to 100):

```
FinalScore(p) = ( ∏ᵢ Sᵢ^wᵢ ) ^ (1 / Σwᵢ)        # Σwᵢ = 100, so exponent = 1/100
```

The `[1, 100]` floor prevents a single worst-in-class metric from zeroing the whole product.
The formula is isolated in `scoring.py` so it can be swapped (e.g. to match the student's final
methodology) in one place without touching the app or storage layers.

## 10. Validation & error handling

- Submit blocked unless: `remaining_budget == 0`, consent checked, ≥1 research area selected.
- Sheets/CSV write wrapped in try/except; failures surface a clear user-facing error and do not
  crash the app.
- No secrets in the repo; service-account credentials live only in `.streamlit/secrets.toml`
  (gitignored) locally and in Streamlit Cloud's secrets manager in production.

## 11. Testing

`pytest` units on the logic-bearing modules (Streamlit layer stays thin):

- **`test_scoring.py`** — normalization direction (higher-is-better vs lower-is-better),
  `[1,100]` floor prevents zero-collapse, weighted geometric mean math against hand-computed
  values, correct re-ranking as weights change.
- **`test_storage.py`** — CSV header written exactly once, row appended with stable schema,
  graceful fallback when no Sheets credentials present.

## 12. Citability plan (documented, partly manual)

- **Durable collection** via Google Sheets (survives Streamlit Cloud restarts/redeploys).
- **Archival + DOI**: when the survey closes, deposit the anonymized response dataset **and** the
  app code to **Zenodo or OSF** to mint a DOI; cite that DOI in the paper
  ("community weighting survey, N = …, DOI:…").
- **Consent**: information statement + checkbox on the form (§5).
- **Ethics**: confirm with the institution whether an anonymous opinion survey needs an ethics
  exemption before citing — flagged, not blocking.

## 13. Dependencies & tooling

- Environment and dependencies managed with **`uv`**.
- Runtime deps: `streamlit`, `pandas`, `numpy`, and a Google Sheets client
  (`st-gsheets-connection` or `gspread` — selected at implementation).
- Dev deps: `pytest`.
