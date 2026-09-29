import json

from modelscompare.preferences import (
    Preferences,
    load_preferences,
    save_preferences,
)


def test_preferences_round_trip_keeps_user_choices(tmp_path) -> None:
    path = tmp_path / "modelscompare" / "config.json"
    preferences = Preferences.defaults()
    preferences.favorite_models = ["GPT Example"]
    preferences.providers = ["OpenAI"]
    preferences.display_unit = "credits"
    preferences.export_formats = ["xlsx"]
    preferences.setup_completed = True

    save_preferences(preferences, path)
    loaded = load_preferences(path)

    assert loaded == preferences


def test_migrates_previous_selection_json(tmp_path) -> None:
    legacy_path = tmp_path / "selection.json"
    legacy_path.write_text(json.dumps({"models": ["GPT Example", "Claude Example"]}), encoding="utf-8")

    migrated = load_preferences(tmp_path / "config.json", legacy_path)

    assert migrated.favorite_models == ["GPT Example", "Claude Example"]
    assert migrated.setup_completed


def test_preferences_defaults_have_no_blended_setting() -> None:
    preferences = Preferences.defaults()

    assert preferences.display_unit == "usd"
    assert preferences.sort_by == "input"
    assert not hasattr(preferences, "blended_cost")


def test_invalid_saved_preferences_are_rejected(tmp_path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"display_unit": "blended"}), encoding="utf-8")

    try:
        load_preferences(path)
    except ValueError as error:
        assert "display unit" in str(error)
    else:
        raise AssertionError("invalid unit preference should be rejected")
