from decimal import Decimal

from modelscompare.models import ModelPricing
from modelscompare.preferences import Preferences
from modelscompare import setup_wizard


def _records() -> list[ModelPricing]:
    return [
        ModelPricing(
            name="GPT Example",
            input_cost_credits=Decimal("100"),
            output_cost_credits=Decimal("200"),
            provider="OpenAI",
            category="Powerful",
            tier="Default",
            release_status="GA",
            threshold="<= 272K",
        ),
        ModelPricing(
            name="Claude Example",
            input_cost_credits=Decimal("80"),
            output_cost_credits=Decimal("150"),
            provider="Anthropic",
            category="Versatile",
            tier="Long context",
            release_status="Preview",
            threshold="> 200K",
        ),
    ]


def test_setup_asks_only_for_models_and_export_formats(monkeypatch) -> None:
    choices = iter([["GPT Example", "Claude Example"], ["Excel"]])
    calls = []

    def choose(title, options, selected=(), **kwargs):
        calls.append((title, options))
        return next(choices)

    monkeypatch.setattr(setup_wizard, "choose_options", choose)
    original = Preferences.defaults()

    configured = setup_wizard.run_setup_wizard(_records(), original)

    assert configured is not None
    assert configured.favorite_models == ["GPT Example", "Claude Example"]
    assert configured.providers == []
    assert configured.categories == []
    assert configured.display_unit == "usd"
    assert configured.sort_by == "input"
    assert configured.export_formats == ["xlsx"]
    assert configured.setup_completed
    assert original == Preferences.defaults()
    assert "GPT Example" in calls[0][1]
    assert len(calls) == 2
    assert "Come vuoi esportare?" == calls[1][0]


def test_setup_cancel_does_not_return_partial_changes(monkeypatch) -> None:
    monkeypatch.setattr(setup_wizard, "choose_options", lambda *_args, **_kwargs: None)
    original = Preferences.defaults()

    assert setup_wizard.run_setup_wizard(_records(), original) is None
    assert original == Preferences.defaults()
