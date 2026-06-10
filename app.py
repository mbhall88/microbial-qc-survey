"""Microbial QC Survey — Streamlit app.

Collects community priority weights over four assembly-QC metrics and shows a
live leaderboard that re-ranks benchmark pipelines as the weights change. Thin
UI layer: all logic lives in data.py / scoring.py / storage.py.
"""
from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st
import numpy as np
import pandas as pd

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
    raw = data.get_pipeline_data()
    
    st.markdown("### Interactive Score Calculator")
    st.markdown(
        """
        To illustrate how your weightings affect the final score, here is a step-by-step breakdown using a **Sample Assembly** scenario.
        
        **Column Guide:**
        - **Scale (Worst → Best)**: The range of values observed across all pipelines in the benchmark, directed from worst possible to best possible.
        - **Normalized Score (0–100)**: Re-scales the raw value to a common 0–100 range (100 = best, 1 = worst) so different units can be compared.
        """
    )
    
    # Use the first row as our static toy example (chopper-porechop_abi)
    pipeline_row = raw.iloc[0]
    
    # Normalize metrics to get intermediate scores
    normalized_df = scoring.normalize_metrics(raw)
    norm_row = normalized_df.iloc[0]
    
    # Build a breakdown table
    breakdown_data = []
    log_sum = 0.0
    weight_sum = sum(weights.values())
    
    for metric in data.METRICS:
        m_id = metric["id"]
        raw_val = pipeline_row[m_id]
        norm_val = norm_row[m_id]
        weight = weights[m_id]
        
        # Get dataset min/max for scale display
        values = raw[m_id].to_numpy(dtype=float)
        lo, hi = values.min(), values.max()
        
        # Log contribution
        log_contrib = weight * np.log(norm_val)
        log_sum += log_contrib
        
        # Format Scale (Worst -> Best)
        if metric["direction"] == "lower":
            scale_str = f"{hi} → {lo}"
        else:
            scale_str = f"{lo} → {hi}"
            
        breakdown_data.append({
            "Metric": metric["label"],
            "Example Raw Value": f"{raw_val}",
            "Scale (Worst → Best)": scale_str,
            "Normalized Score (0-100)": f"{norm_val:.2f}",
            "Your Weight": f"{weight}"
        })
        
    st.dataframe(pd.DataFrame(breakdown_data), hide_index=True, use_container_width=True)
    
    st.markdown("#### The Math step-by-step:")
    if weight_sum <= 0:
        st.info("Please allocate at least 1 point to calculate scores.")
        return
        
    weighted_log_mean = log_sum / weight_sum
    final_score = np.exp(weighted_log_mean)
    
    # Render with nice math notation
    terms = []
    for metric in data.METRICS:
        m_id = metric["id"]
        norm_val = norm_row[m_id]
        weight = weights[m_id]
        if weight > 0:
            terms.append(f"{norm_val:.1f}^{{{weight}}}")
            
    formula_str = " \\times ".join(terms)
    if formula_str:
        st.latex(rf"\text{{Score}} = \left( {formula_str} \right)^{{\frac{{1}}{{{weight_sum}}}}} = {final_score:.2f}")
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

    st.markdown('<h1 class="main-title">Microbial QC Pipeline Priorities</h1>', unsafe_allow_html=True)
    st.caption("Responses are anonymous and used for research.")

    # Background context
    st.markdown(
        """
        ### About This Study
        We are conducting a benchmarking study to evaluate different Nanopore read trimming and quality-filtering tools (such as Dorado, Filtlong, and others) for microbial genome assembly. 
        
        Throughout our analysis, it has become evident that no single pipeline configuration performs perfectly across all possible quality measures. For example, a tool might produce great contiguity and low mismatch errors, but its read-length targeting can aggressively filter out the short reads necessary to assemble small plasmids. 
        
        To establish a transparent, community-choice baseline for our paper's pipeline ranking, we are surveying the microbial genomics and bioinformatics community to ask how you prioritize these varying aspects of an assembly. The aggregated consensus will form the default weighting baseline.
        """
    )

    # Detailed metrics explanation in an expander
    with st.expander("Explore the Four Key Metrics in Detail"):
        st.markdown(
            """
            - **Mismatches and Indels (Assembly Errors):** Tracks the base-level accuracy of the assembly by measuring overall sequencing errors (per 100 kbp). It captures how effectively the pre-processing tools remove noisy data that would otherwise lead to false positive/negative variant calls and assembly-level inaccuracies.
            - **Number of Contaminants:** Measures the pipeline's ability to trim or filter out barcode and adapter sequences. Some trimming and filtering pipelines allow contaminants to slip through into the final assembly while others successfully remove them.
            - **Assembly Contiguity (NGA50):** A reference-aware version of the N50 metric, assessing the fragmentation of the assembly. It is the length of an aligned block such that all aligned blocks of at least this length cover at least 50% of the reference. NGA50 is normalized to total genome size so we can compare across samples of differing sizes.
            - **Number of Missed Contigs:** Evaluates whether the pipeline accurately captures the entire genome, with a specific focus on the recovery of small plasmids (since highly aggressive quality-filtering tools can inadvertently cause entire small plasmids to be lost from the final assembly).
            """
        )

    st.subheader("Weight the metrics (must total 100)")
    weights = render_sliders()

    remaining = remaining_budget(weights)
    if remaining == 0:
        st.success("Unallocated budget: 0 — ready to submit.")
    else:
        st.warning(f"Unallocated budget: {remaining} — allocate all 100 points to submit.")

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


if __name__ == "__main__":
    main()
