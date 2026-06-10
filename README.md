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
