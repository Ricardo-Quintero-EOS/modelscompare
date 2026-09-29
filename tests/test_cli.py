from decimal import Decimal

import pytest

from modelscompare import cli
from modelscompare import console_app
from modelscompare.models import ModelPricing
from modelscompare.preferences import Preferences, save_preferences


def test_console_script_entrypoint_uses_interactive_app() -> None:
    assert cli.main is console_app.main


def test_cli_arguments_expose_per_cost_sort_and_no_blended_flags() -> None:
    args = console_app._arguments(["--sort", "cached_write", "--unit", "credits", "--no-export"])

    assert args.sort == "cached_write"
    assert args.unit == "credits"
    assert args.no_export
    assert not hasattr(args, "min_cost")
    assert not hasattr(args, "max_cost")


def test_noninteractive_cli_prints_four_costs_without_export(monkeypatch, tmp_path, capsys) -> None:
    preferences = Preferences.defaults()
    preferences.setup_completed = True
    config_path = tmp_path / "config.json"
    save_preferences(preferences, config_path)
    record = ModelPricing(
        name="Example Model",
        input_cost_credits=Decimal("100"),
        output_cost_credits=Decimal("400"),
        cached_input_cost_credits=Decimal("10"),
        cache_write_cost_credits=Decimal("125"),
        usd_per_credit=Decimal("0.01"),
    )
    monkeypatch.setattr(console_app, "fetch_live_records", lambda: [record])

    assert console_app.main(["--config-file", str(config_path)]) == 0

    rendered = capsys.readouterr().out
    assert "Cached read" in rendered
    assert "Cached write" in rendered
    assert "$1.0000" in rendered
    assert "$0.1000" in rendered
    assert "$1.2500" in rendered
    assert "$4.0000" in rendered
    assert "blended" not in rendered.casefold()


def test_export_flag_is_explicit_consent_for_noninteractive_export(monkeypatch, tmp_path) -> None:
    preferences = Preferences.defaults()
    preferences.setup_completed = True
    preferences.export_formats = ["csv"]
    config_path = tmp_path / "config.json"
    save_preferences(preferences, config_path)
    record = ModelPricing("Example Model", Decimal("100"), Decimal("400"))
    exported = []
    monkeypatch.setattr(console_app, "fetch_live_records", lambda: [record])
    monkeypatch.setattr(console_app, "export_records", lambda records, formats, prefix: exported.append((records, formats, prefix)) or [])
    monkeypatch.setattr(console_app.Confirm, "ask", lambda *_args, **_kwargs: pytest.fail("unexpected confirmation prompt"))

    assert console_app.main(["--config-file", str(config_path), "--export"]) == 0
    assert exported == [([record], ["csv"], "copilot_models")]
