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
