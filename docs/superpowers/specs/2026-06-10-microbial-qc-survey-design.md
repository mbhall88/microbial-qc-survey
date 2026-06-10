# Microbial QC Survey — Design Spec

**Date:** 2026-06-10
**Status:** Approved (design), pending implementation plan

## 1. Purpose

A single-page Streamlit application that collects **community priority weights** over four
read-trimming / quality-filtering assembly metrics and shows a **live leaderboard** that
re-ranks benchmark pipelines as the participant moves the weight sliders.

The weights establish a "community-choice baseline" for ranking pipelines in a microbial
genomics benchmarking paper. The **saved payload is the four weights** (plus a timestamp); the
leaderboard is a live engagement demo and never touches the saved data.

## 2. Scope & non-goals

In scope:
- Four constant-sum weight sliders with a remaining-budget cap (always ≤ 100).
- A reactive leaderboard scoring benchmark pipelines via a weighted geometric mean over
  **simulated** metric values guided by real benchmark ballparks.
- Durable response capture to Google Sheets (with a local-CSV fallback for development).
- A brief, non-blocking information statement (responses anonymous, used for research).

Out of scope (documented for later, not built now):
- Demographics capture (removed — collected data is purely non-identifying opinion weights).
- Analysis/reporting of collected responses.
- Zenodo/OSF deposit automation (documented as a manual archival step).
- Authentication or per-user response editing.

## 3. Decisions locked during brainstorming

| Decision | Choice |
|---|---|
| Demographics | **None** — survey collects only the four weights |
| Constant-sum slider logic | **Remaining-budget cap** — each slider's max is `value + remaining_budget`; total never exceeds 100; submit enabled only when unallocated budget == 0 |
| Scoring formula | **Weighted geometric mean** over **all 4** metrics: `(∏ Sᵢ^wᵢ)^(1/Σwᵢ)` |
| Normalization | Min-max to 0–100 per metric, direction-aware, floored to `[1, 100]` to prevent zero-collapse |
| Leaderboard data | **Simulated raw metric values** using real benchmark names + ballparks, crafted with deliberate trade-offs so rankings are weight-sensitive |
| Storage | **Google Sheets** via server-side service account; **local CSV fallback** when no secrets present |
| Hosting | **Streamlit Community Cloud**, deployed from the GitHub repo |
| Consent | Brief info statement (non-blocking); submit gated only by budget == 0 |
| Python tooling | `uv`-managed environment and dependencies |

## 4. Architecture

Modular, runs out-of-the-box locally (CSV fallback), deploys to Streamlit Community Cloud
(Sheets backend via secrets).

```
microbial-qc-survey/
├── app.py                 # Streamlit page: layout, wiring, submit handler (thin)
├── scoring.py             # normalize_metrics() + score_pipelines() — pure, swappable formula
├── data.py                # simulated pipeline RAW metric values + per-metric metadata
├── storage.py             # append_response(): Google Sheets backend, CSV fallback
├── pyproject.toml         # deps: streamlit, pandas, numpy, gspread/streamlit-gsheets
├── .streamlit/
│   └── secrets.toml       # (gitignored) Google service-account creds for deployment
├── tests/
│   ├── test_scoring.py
│   └── test_storage.py
├── CITATION.md / README   # archival + DOI plan, info statement, ethics note
└── survey_responses.csv   # created on first submit when running on the CSV fallback
```

### Component responsibilities

- **`data.py`** — single source of truth for the leaderboard. Holds each pipeline's **raw**
  per-metric values for the four survey metrics, plus per-metric metadata (display label,
  direction: higher- or lower-is-better). Values are **simulated** using real pipeline names and
  the real benchmark ballparks (§8) as a guide, hand-crafted with trade-offs so different
  pipelines win on different metrics.

- **`scoring.py`** — pure functions, **no Streamlit import** (independently unit-testable):
  - `normalize_metrics(df)` → min-max to 0–100 per metric, direction-aware, clamped to `[1,100]`.
  - `score_pipelines(normalized_df, weights)` → applies `(∏ Sᵢ^wᵢ)^(1/Σwᵢ)`, returns a DataFrame
    sorted by score descending with a `rank` column.

- **`storage.py`** — `append_response(row: dict) -> None`. If `st.secrets` contains Google
  service-account credentials, append a row to the configured Sheet; otherwise append to
  `survey_responses.csv` (writing a header row if the file is new). Immutable-style: builds a
  new row, no shared mutable state. Write wrapped in try/except surfacing a user-facing error.

- **`app.py`** — renders title/description, brief info statement, the four capped sliders, the
  live leaderboard, and the submit button; orchestrates the other modules. Kept thin — all real
  logic lives in `scoring.py` / `storage.py`.

## 5. Layout & form (per requirements)

1. **Title + description** — explains the "community-choice baseline" framing for ranking
   read-trimming / quality-filtering pipelines.
2. **Brief info statement** — one line: responses are anonymous and used for research.
   Non-blocking (no checkbox gate).
3. **Four weight sliders** (the four core metrics):
   - Assembly Accuracy (Mismatches & Indels)
   - Assembly Contiguity (NGA50)
   - Contamination Removal (Residual Adapters/Barcodes)
   - Multi-Replicon Recovery (Missed Small Plasmids)
4. **Live leaderboard** — `st.dataframe` of pipelines re-ranked by current weights.
5. **Submit Weights to Study** button + success toast.

## 6. Slider logic — remaining-budget cap

- Four sliders initialise to **25 / 25 / 25 / 25** (valid by default; total = 100).
- Each slider's `max_value` is set dynamically to `current_value + remaining_budget`, where
  `remaining_budget = 100 - sum(all_slider_values)`. The total therefore can never exceed 100.
- A live indicator shows **"Unallocated budget: N"** — green at 0, amber otherwise.
- Submit is enabled only when `remaining_budget == 0`.
- Slider state held in `st.session_state`; an `on_change` callback recomputes caps each rerun.

## 7. Data flow

```
sliders ──► weights {w_accuracy, w_contiguity, w_decontam, w_plasmid}
                │
                ▼ (every rerun)
   normalize_metrics(data.raw) ─► score_pipelines(normalized, weights)
                │
                ▼
        st.dataframe leaderboard (sorted by score desc, rank column)

[Submit click] ─► assemble row:
   { timestamp, w_accuracy, w_contiguity, w_decontam, w_plasmid }
   ─► storage.append_response(row) ─► st.toast / st.success
```

Saved schema (one row per submission):
`timestamp, w_accuracy, w_contiguity, w_decontam, w_plasmid`

## 8. Leaderboard data — simulated values & metric mapping

The benchmark table columns are:
`rank, qc-tools-pair, model, depth, NGA50-normalised, mismatches/100kbp, indels/100kbp,
contamination-count, score-NGA50, score-mismatches, score-indels, score-err,
score-contamination, final-score`.

The four survey metrics map to raw inputs as follows (values **simulated** in the ballpark of
the real table; the literal benchmark scores are **not** reused):

| Survey metric | Raw input | Direction | Ballpark |
|---|---|---|---|
| Assembly Accuracy (Mismatches & Indels) | combined errors/100kbp (mismatches + indels) | lower = better | ~1.5–4.0 |
| Assembly Contiguity (NGA50) | NGA50-normalised | higher = better | ~0.88–0.97 |
| Contamination Removal | contamination-count | lower = better | integer 0–3 |
| Multi-Replicon Recovery (Missed Small Plasmids) | missed-plasmid-count (**simulated**, not in source table) | lower = better | single digit 0–6 |

`data.py` stores these raw values; `scoring.normalize_metrics()` converts them to 0–100
direction-aware scores at runtime. Pipeline names come from the real set
(`chopper-porechop_abi`, `fastplong-all`, `filtlong-porechop_abi`, `filtlong-untrimmed`,
`seqkit-dorado`, `unprocessed-dorado`, …). A representative subset (~6–8 pipelines) is seeded
with **deliberate trade-offs** — e.g. one strong on accuracy but worst on contamination, another
top NGA50 but missing plasmids — so changing the weights meaningfully reshuffles the ranking.

## 9. Scoring math (reference)

For pipeline *p* with normalized metric scores `Sᵢ ∈ [1, 100]` and user weights `wᵢ`
(summing to 100):

```
FinalScore(p) = ( ∏ᵢ Sᵢ^wᵢ ) ^ (1 / Σwᵢ)        # Σwᵢ = 100, so exponent = 1/100
```

Accuracy combines mismatches and indels into a single "errors" input before normalization. The
`[1, 100]` floor prevents a single worst-in-class metric from zeroing the whole product. The
formula is isolated in `scoring.py` so it can be swapped (e.g. to match the student's final
methodology) in one place without touching the app or storage layers.

## 10. Validation & error handling

- Submit blocked unless `remaining_budget == 0`.
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
- **Info statement**: brief, non-blocking line on the form (§5). No demographics are collected,
  so responses are non-identifying opinion weights.
- **Ethics**: confirm with the institution whether an anonymous opinion survey needs an ethics
  exemption before citing — flagged, not blocking.

## 13. Dependencies & tooling

- Environment and dependencies managed with **`uv`**.
- Runtime deps: `streamlit`, `pandas`, `numpy`, and a Google Sheets client
  (`st-gsheets-connection` or `gspread` — selected at implementation).
- Dev deps: `pytest`.
