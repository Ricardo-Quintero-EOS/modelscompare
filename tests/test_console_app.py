from decimal import Decimal

import pytest

from modelscompare.console_app import _arguments, filter_records
from modelscompare.models import ModelPricing
from modelscompare.preferences import Preferences


def _records() -> list[ModelPricing]:
    return [
        ModelPricing(
            name="Expensive input",
            input_cost_credits=Decimal("300"),
            output_cost_credits=Decimal("30"),
            cached_input_cost_credits=Decimal("50"),
            cache_write_cost_credits=Decimal("40"),
            usd_per_credit=Decimal("0.01"),
            provider="OpenAI",
            category="Powerful",
            tier="Default",
            release_status="GA",
            threshold="<= 272K",
        ),
        ModelPricing(
            name="Cheap input",
            input_cost_credits=Decimal("100"),
            output_cost_credits=Decimal("300"),
            cached_input_cost_credits=Decimal("10"),
            cache_write_cost_credits=Decimal("5"),
            usd_per_credit=Decimal("0.01"),
            provider="OpenAI",
            category="Lightweight",
            tier="Default",
            release_status="GA",
            threshold="Not applicable",
        ),
        ModelPricing(
            name="Different provider",
            input_cost_credits=Decimal("200"),
            output_cost_credits=Decimal("50"),
            cached_input_cost_credits=Decimal("15"),
            cache_write_cost_credits=Decimal("8"),
            usd_per_credit=Decimal("0.01"),
            provider="Anthropic",
            category="Powerful",
            tier="Long context",
            release_status="Preview",
            threshold="> 200K",
        ),
    ]


def test_cost_sort_uses_requested_cost_dimension_only() -> None:
    preferences = Preferences.defaults()
    preferences.sort_by = "cached_write"

    result = filter_records(_records(), preferences, _arguments([]))

    assert [record.name for record in result] == [
        "Cheap input", "Different provider", "Expensive input",
    ]


def test_setup_filters_and_command_overrides_combine() -> None:
    preferences = Preferences.defaults()
    preferences.providers = ["OpenAI"]
    preferences.categories = ["Powerful", "Lightweight"]
    preferences.release_statuses = ["GA"]
    args = _arguments(["--model", "input", "--tier", "default", "--sort", "output"])

    result = filter_records(_records(), preferences, args)

    assert [record.name for record in result] == ["Expensive input", "Cheap input"]
    assert [record.name for record in result] == sorted(
        ["Expensive input", "Cheap input"],
        key=lambda name: next(record.output_cost_usd for record in _records() if record.name == name),
    )


def test_catalog_view_ignores_legacy_saved_filters_but_keeps_explicit_cli_filters() -> None:
    preferences = Preferences.defaults()
    preferences.providers = ["OpenAI"]
    preferences.release_statuses = ["GA"]
    preferences.thresholds = ["<= 272K"]
    records = _records()

    all_records = filter_records(records, preferences, _arguments([]), include_saved_filters=False)
    explicit_filter = filter_records(
        records,
        preferences,
        _arguments(["--provider", "Anthropic"]),
        include_saved_filters=False,
    )

    assert {record.name for record in all_records} == {record.name for record in records}
    assert [record.name for record in explicit_filter] == ["Different provider"]


def test_blended_cost_cli_flags_are_removed() -> None:
    with pytest.raises(SystemExit):
        _arguments(["--max-cost", "100"])
