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
