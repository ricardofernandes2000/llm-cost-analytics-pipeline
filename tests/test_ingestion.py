import pytest

from functions.ingestion.main import build_row, calculate_cost_usd


def test_calculate_cost_for_supported_model() -> None:
    cost = calculate_cost_usd("gpt-4o-mini", 1000, 1000)

    assert cost == pytest.approx(0.00075)


def test_calculate_cost_with_zero_tokens() -> None:
    assert calculate_cost_usd("gpt-4o", 0, 0) == 0.0


def test_calculate_cost_is_rounded_to_eight_decimal_places() -> None:
    cost = calculate_cost_usd("gemini-2.5-pro", 1234, 567)

    assert cost == pytest.approx(0.0072125)
    assert len(str(cost).split(".")[1]) <= 8


def test_calculate_cost_rejects_unknown_model() -> None:
    with pytest.raises(KeyError):
        calculate_cost_usd("unknown-model", 100, 100)


def test_build_row_converts_numeric_fields_and_adds_cost() -> None:
    event = {
        "timestamp": "2026-09-13T12:00:00Z",
        "provider": "OpenAI",
        "model": "gpt-4o",
        "input_tokens": "1000",
        "output_tokens": "500",
        "latency_ms": "250",
        "status": "success",
    }

    row = build_row(event)

    assert row == {
        "timestamp": "2026-09-13T12:00:00Z",
        "provider": "OpenAI",
        "model": "gpt-4o",
        "input_tokens": 1000,
        "output_tokens": 500,
        "cost_usd": 0.0125,
        "latency_ms": 250,
        "status": "success",
    }


def test_build_row_rejects_missing_required_field() -> None:
    event = {
        "timestamp": "2026-09-13T12:00:00Z",
        "provider": "OpenAI",
        "model": "gpt-4o",
        "input_tokens": 1000,
        "output_tokens": 500,
        "status": "success",
    }

    with pytest.raises(KeyError):
        build_row(event)
