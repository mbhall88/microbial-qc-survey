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
