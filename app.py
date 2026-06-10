"""Microbial QC Survey — Streamlit app.

Collects community priority weights over four assembly-QC metrics and shows a
live leaderboard that re-ranks benchmark pipelines as the weights change. Thin
UI layer: all logic lives in data.py / scoring.py / storage.py.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
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

    # Initialize walkthrough variables
    defaults = {
        "accuracy": {"raw": 1.6, "worst": 4.0, "best": 1.5},
        "contiguity": {"raw": 0.969, "worst": 0.882, "best": 0.969},
        "decontam": {"raw": 2, "worst": 3, "best": 0},
        "replicon": {"raw": 1, "worst": 5, "best": 0},
    }
    for m_id, vals in defaults.items():
        raw_key = f"walk_raw_{m_id}"
        worst_key = f"walk_worst_{m_id}"
        best_key = f"walk_best_{m_id}"
        if raw_key not in st.session_state:
            st.session_state[raw_key] = vals["raw"]
        if worst_key not in st.session_state:
            st.session_state[worst_key] = vals["worst"]
        if best_key not in st.session_state:
            st.session_state[best_key] = vals["best"]


def _on_walk_raw_change(m_id: str, direction: str) -> None:
    raw_val = st.session_state[f"walk_raw_{m_id}"]
    worst_val = st.session_state[f"walk_worst_{m_id}"]
    best_val = st.session_state[f"walk_best_{m_id}"]

    if m_id in ("decontam", "replicon"):
        raw_val = int(raw_val)
        worst_val = int(worst_val)
        best_val = int(best_val)
        st.session_state[f"walk_raw_{m_id}"] = raw_val

    if direction == "lower":
        if raw_val < best_val:
            st.session_state[f"walk_best_{m_id}"] = raw_val
        elif raw_val > worst_val:
            st.session_state[f"walk_worst_{m_id}"] = raw_val
    else:  # direction == "higher"
        if raw_val < worst_val:
            st.session_state[f"walk_worst_{m_id}"] = raw_val
        elif raw_val > best_val:
            st.session_state[f"walk_best_{m_id}"] = raw_val


def _on_walk_worst_change(m_id: str, direction: str) -> None:
    raw_val = st.session_state[f"walk_raw_{m_id}"]
    worst_val = st.session_state[f"walk_worst_{m_id}"]
    best_val = st.session_state[f"walk_best_{m_id}"]

    if m_id in ("decontam", "replicon"):
        raw_val = int(raw_val)
        worst_val = int(worst_val)
        best_val = int(best_val)
        st.session_state[f"walk_worst_{m_id}"] = worst_val

    if direction == "lower":
        if worst_val < raw_val:
            st.session_state[f"walk_worst_{m_id}"] = raw_val
        if worst_val < best_val:
            st.session_state[f"walk_best_{m_id}"] = worst_val
    else:  # direction == "higher"
        if worst_val > raw_val:
            st.session_state[f"walk_worst_{m_id}"] = raw_val
        if worst_val > best_val:
            st.session_state[f"walk_best_{m_id}"] = best_val


def _on_walk_best_change(m_id: str, direction: str) -> None:
    raw_val = st.session_state[f"walk_raw_{m_id}"]
    worst_val = st.session_state[f"walk_worst_{m_id}"]
    best_val = st.session_state[f"walk_best_{m_id}"]

    if m_id in ("decontam", "replicon"):
        raw_val = int(raw_val)
        worst_val = int(worst_val)
        best_val = int(best_val)
        st.session_state[f"walk_best_{m_id}"] = best_val

    if direction == "lower":
        if best_val > raw_val:
            st.session_state[f"walk_best_{m_id}"] = raw_val
        if best_val > worst_val:
            st.session_state[f"walk_worst_{m_id}"] = worst_val
    else:  # direction == "higher"
        if best_val < raw_val:
            st.session_state[f"walk_best_{m_id}"] = raw_val
        if best_val < worst_val:
            st.session_state[f"walk_worst_{m_id}"] = worst_val


def _current_weights() -> dict:
    return {m["id"]: st.session_state[_weight_key(m["id"])] for m in data.METRICS}


def _on_slider_change(metric_id: str) -> None:
    """Callback to enforce that the sum of all weights never exceeds 100.

    If the user increases a slider beyond the remaining budget, clamp it.
    """
    key = _weight_key(metric_id)
    val = st.session_state[key]
    other_sum = sum(
        st.session_state[_weight_key(m["id"])]
        for m in data.METRICS
        if m["id"] != metric_id
    )
    if val + other_sum > TOTAL_BUDGET:
        st.session_state[key] = TOTAL_BUDGET - other_sum


def render_sliders() -> dict:
    """Render the four budget-capped number inputs. Returns the current weights dict."""
    weights = _current_weights()
    for metric in data.METRICS:
        metric_id = metric["id"]
        st.number_input(
            metric["label"],
            min_value=0,
            max_value=100,
            value=int(weights[metric_id]),
            step=1,
            key=_weight_key(metric_id),
            on_change=_on_slider_change,
            args=(metric_id,),
        )
    return _current_weights()


def render_calculation_walkthrough(weights: dict) -> None:
    WALK_CONFIG = {
        "accuracy": {"step": 0.1, "format": "%.2f"},
        "contiguity": {"step": 0.001, "format": "%.3f"},
        "decontam": {"step": 1, "format": "%d"},
        "replicon": {"step": 1, "format": "%d"},
    }

    st.markdown("### Interactive Score Calculator")
    st.markdown(
        """
        To illustrate how your weightings affect the final score, here is a step-by-step breakdown using a **Sample Assembly** scenario.
        
        You can customise the raw values and scale limits below to see how the normalization and scoring math updates dynamically.
        
        **Column Guide:**
        - **Scale (Worst → Best)**: The range of values observed across all pipelines in the benchmark, directed from worst possible to best possible.
        - **Normalized Score (0–100)**: Re-scales the raw value to a common 0–100 range (100 = best, 1 = worst) so different units can be compared.
        """
    )

    st.markdown("#### Customize Sample Values & Limits")

    # Render inputs in a 2x2 grid of expanders
    cols = st.columns(2)
    for i, metric in enumerate(data.METRICS):
        m_id = metric["id"]
        direction = metric["direction"]
        cfg = WALK_CONFIG[m_id]
        col_idx = i % 2

        with cols[col_idx]:
            with st.expander(f"⚙️ {metric['label'].split('(')[0].strip()}"):
                sub_cols = st.columns(3)
                with sub_cols[0]:
                    st.number_input(
                        "Raw Value",
                        step=cfg["step"],
                        format=cfg["format"],
                        key=f"walk_raw_{m_id}",
                        on_change=_on_walk_raw_change,
                        args=(m_id, direction),
                    )
                with sub_cols[1]:
                    st.number_input(
                        "Worst (Limit)",
                        step=cfg["step"],
                        format=cfg["format"],
                        key=f"walk_worst_{m_id}",
                        on_change=_on_walk_worst_change,
                        args=(m_id, direction),
                    )
                with sub_cols[2]:
                    st.number_input(
                        "Best (Limit)",
                        step=cfg["step"],
                        format=cfg["format"],
                        key=f"walk_best_{m_id}",
                        on_change=_on_walk_best_change,
                        args=(m_id, direction),
                    )

    # Build a breakdown table using custom session state values
    breakdown_data = []
    log_sum = 0.0
    weight_sum = sum(weights.values())
    norm_scores = {}

    for metric in data.METRICS:
        m_id = metric["id"]
        direction = metric["direction"]
        raw_val = st.session_state[f"walk_raw_{m_id}"]
        worst_val = st.session_state[f"walk_worst_{m_id}"]
        best_val = st.session_state[f"walk_best_{m_id}"]
        weight = weights[m_id]

        # Calculate custom normalized score
        span = abs(worst_val - best_val)
        if span == 0:
            norm_val = 100.0
        elif direction == "higher":
            norm_val = (raw_val - worst_val) / span * 100.0
        else:  # lower is better
            norm_val = (worst_val - raw_val) / span * 100.0
        norm_val = float(np.clip(norm_val, 1.0, 100.0))
        norm_scores[m_id] = norm_val

        # Log contribution
        log_contrib = weight * np.log(norm_val)
        log_sum += log_contrib

        # Format Scale (Worst -> Best)
        if direction == "lower":
            scale_str = f"{worst_val} → {best_val}"
        else:
            scale_str = f"{worst_val} → {best_val}"

        breakdown_data.append(
            {
                "Metric": metric["label"],
                "Example Raw Value": f"{raw_val}",
                "Scale (Worst → Best)": scale_str,
                "Normalized Score (0-100)": f"{norm_val:.2f}",
                "Your Weight": f"{weight}",
            }
        )

    st.dataframe(
        pd.DataFrame(breakdown_data), hide_index=True, use_container_width=True
    )

    st.markdown("#### The Maths step-by-step:")
    if weight_sum <= 0:
        st.info("Please allocate at least 1 point to calculate scores.")
        return

    weighted_log_mean = log_sum / weight_sum
    final_score = np.exp(weighted_log_mean)

    # Render with nice math notation
    terms = []
    for metric in data.METRICS:
        m_id = metric["id"]
        norm_val = norm_scores[m_id]
        weight = weights[m_id]
        if weight > 0:
            terms.append(f"{norm_val:.1f}^{{{weight}}}")

    formula_str = " \\times ".join(terms)
    if formula_str:
        st.latex(
            rf"\text{{Score}} = \left( {formula_str} \right)^{{\frac{{1}}{{{weight_sum}}}}} = {final_score:.2f}"
        )
    else:
        st.latex(r"\text{{Score}} = 0")

    st.markdown(
        f"""
        1. **Log-space sum**: Sum of `Weight * ln(Normalized Score)` = `{log_sum:.4f}`
        2. **Divide by total weight**: `{log_sum:.4f} / {weight_sum}` = `{weighted_log_mean:.4f}`
        3. **Exponentiate back**: `exp({weighted_log_mean:.4f})` = **`{final_score:.2f}`**
        """
    )


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

    st.markdown(
        '<h1 class="main-title">Microbial QC Pipeline Priorities</h1>',
        unsafe_allow_html=True,
    )
    st.caption("Responses are anonymous and used for research.")

    # Background context
    st.markdown(
        """
        ### About This Study
        We are conducting a benchmarking study to evaluate different Nanopore read trimming and quality-filtering tools (such as Dorado, Filtlong, and others) for microbial genome assembly and variant calling. 
        
        Throughout our analysis, it has become evident that no single pipeline configuration performs perfectly across all possible quality measures. For example, a tool might produce great contiguity and low mismatch errors, but its read-length targeting can aggressively filter out the short reads necessary to assemble small plasmids. 
        
        To establish a transparent, community-choice baseline for our paper's pipeline ranking, we are surveying the microbial genomics and bioinformatics community to ask how you prioritise these varying aspects of genome assembly (variant calling is much simpler to assess using F1 score). The aggregated consensus will form the default weighting baseline for the genome assembly component of our analysis.
        """
    )

    # Detailed metrics explanation in an expander
    with st.expander("Explore the Four Key Metrics in Detail"):
        st.markdown(
            """
            - **Mismatches and Indels (Assembly Errors):** Tracks the base-level accuracy of the assembly by measuring overall sequencing errors (per 100 kbp). It captures how effectively the pre-processing tools remove noisy data that would otherwise lead to assembly-level inaccuracies.
            - **Number of Contaminants:** Measures the pipeline's ability to trim or filter out barcode and adapter sequences. Some trimming and filtering pipelines allow contaminants to slip through into the final assembly, so this metric penalises those contaminants.
            - **Assembly Contiguity (NGA50):** A reference-aware version of the N50 metric, assessing the fragmentation of the assembly. It is the length of an aligned block such that all aligned blocks of at least this length cover at least 50% of the reference. NGA50 is normalized to total genome size so we can compare across samples of differing sizes.
            - **Number of Missed Contigs:** Evaluates whether the pipeline accurately captures the entire genome. We found this particularly important in the recovery of small plasmids (since highly aggressive quality-filtering tools can inadvertently cause entire small plasmids to be lost from the final assembly).
            """
        )

    st.subheader("Weight the metrics (must total 100)")
    weights = render_sliders()

    remaining = remaining_budget(weights)
    if remaining == 0:
        st.success("Unallocated budget: 0 — ready to submit.")
    else:
        st.warning(
            f"Unallocated budget: {remaining} — allocate all 100 points to submit."
        )

    st.subheader("Interactive Score Walkthrough")
    st.caption("See how your current weights affect a pipeline's final score.")
    if sum(weights.values()) > 0:
        render_calculation_walkthrough(weights)
    else:
        st.info("Please allocate at least 1 point to view the score walkthrough.")

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

    if remaining == 0:
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image("assets/arnold_submit_weights.png", use_container_width=True)


if __name__ == "__main__":
    main()
