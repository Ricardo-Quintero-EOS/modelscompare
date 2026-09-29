from copy import deepcopy
from collections.abc import Sequence
from typing import Any

from modelscompare.models import ModelPricing
from modelscompare.preferences import Preferences
from modelscompare.terminal_ui import choose_options

EXPORT_CHOICES = {"CSV": "csv", "Excel": "xlsx"}


def run_setup_wizard(
    records: Sequence[ModelPricing],
    current: Preferences,
    *,
    input: Any = None,
    output: Any = None,
) -> Preferences | None:
    candidate = deepcopy(current)
    model_names = sorted({record.name for record in records}, key=str.casefold)
    selected_models = choose_options(
        "Quali modelli ti interessano? (nessuna selezione = tutti)",
        model_names,
        candidate.favorite_models,
        input=input,
        output=output,
    )
    if selected_models is None:
        return None
    candidate.favorite_models = selected_models

    selected_formats = choose_options(
        "Come vuoi esportare?",
        list(EXPORT_CHOICES),
        [label for label, value in EXPORT_CHOICES.items() if value in candidate.export_formats],
        input=input,
        output=output,
    )
    if selected_formats is None:
        return None
    candidate.export_formats = [EXPORT_CHOICES[label] for label in selected_formats]
    candidate.setup_completed = True
    return candidate
