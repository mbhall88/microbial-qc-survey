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


def inject_custom_css() -> None:
    """Inject custom CSS to enhance the visual appeal of the Streamlit application."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');

        /* Update base font family */
        html, body, [class*="css"], .stMarkdown {
            font-family: 'Outfit', sans-serif;
        }

        /* Gradient header */
        .main-title {
            background: linear-gradient(135deg, #FF4B4B 0%, #FF8F8F 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800;
            font-size: 2.8rem;
            margin-bottom: 0.2rem;
            padding-top: 1rem;
        }

        .subtitle {
            font-size: 1.1rem;
            color: #555555;
            margin-bottom: 2rem;
            line-height: 1.6;
        }

        @media (prefers-color-scheme: dark) {
            .subtitle {
                color: #CCCCCC;
            }
        }

        /* Beautiful primary buttons */
        div.stButton > button:first-child {
            background: linear-gradient(135deg, #FF4B4B 0%, #FF6B6B 100%);
            color: white;
            border: none;
            border-radius: 8px;
            padding: 12px 24px;
            font-weight: 600;
            box-shadow: 0 4px 15px rgba(255, 75, 75, 0.3);
            transition: all 0.3s ease;
        }

        div.stButton > button:first-child:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(255, 75, 75, 0.4);
            background: linear-gradient(135deg, #FF6B6B 0%, #FF8F8F 100%);
            border: none;
        }

        div.stButton > button:first-child:active {
            transform: translateY(0);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="Microbial QC Survey", layout="centered")
    inject_custom_css()
    _init_state()

    st.markdown('<h1 class="main-title">Microbial QC Pipeline Priorities</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="subtitle">Set how much each assembly-QC metric should matter. '
        'Your weights help establish a <b>community-choice baseline</b> for ranking '
        'read-trimming and quality-filtering pipelines in an upcoming microbial '
        'genomics benchmark.</p>',
        unsafe_allow_html=True,
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
