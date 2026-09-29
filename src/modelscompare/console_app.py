import argparse
import sys
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from pathlib import Path
import webbrowser

import requests
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

from modelscompare.artificial_analysis import (
    fetch_model_links,
    fetch_model_metadata,
    match_model_links,
    match_model_metadata,
)
from modelscompare.exporting import export_records
from modelscompare.models import ModelPricing
from modelscompare.preferences import Preferences, default_preferences_path, load_preferences, save_preferences
from modelscompare.pricing import fetch_pricing_page, parse_pricing_html
from modelscompare.setup_wizard import run_setup_wizard
from modelscompare.terminal_ui import ModelBrowser


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="modelscompare",
        description="Esplora i prezzi live GitHub Copilot con frecce e Invio.",
    )
    parser.add_argument("--setup", action="store_true", help="riapre il wizard di configurazione")
    parser.add_argument("--all-models", action="store_true", help="mostra tutti i modelli, ignorando i preferiti nella vista iniziale")
    parser.add_argument("--clear-selection", action="store_true", help="cancella i modelli preferiti salvati")
    parser.add_argument("--config-file", type=Path, help="percorso alternativo del file di configurazione")
    parser.add_argument("--selection-file", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--model", action="append", default=[], metavar="TESTO", help="filtra il nome per sottostringa; ripetibile")
    parser.add_argument("--provider", action="append", default=[], metavar="TESTO", help="filtra provider per sottostringa; ripetibile")
    parser.add_argument("--category", action="append", default=[], metavar="TESTO", help="filtra categoria per sottostringa; ripetibile")
    parser.add_argument("--tier", action="append", default=[], metavar="TESTO", help="filtra tier per sottostringa; ripetibile")
    parser.add_argument("--status", action="append", default=[], metavar="TESTO", help="filtra stato di rilascio; ripetibile")
    parser.add_argument("--threshold", action="append", default=[], metavar="TESTO", help="filtra soglia di contesto; ripetibile")
    parser.add_argument(
        "--sort",
        choices=("name", "provider", "input", "cached_read", "cached_write", "output"),
        help="ordinamento",
    )
    parser.add_argument("--unit", choices=("usd", "credits"), help="unità costi per questa esecuzione")
    parser.add_argument("--limit", type=int, help="limita il numero di modelli mostrati")
    export_group = parser.add_mutually_exclusive_group()
    export_group.add_argument("--export", action="store_true", help="esporta subito nei formati configurati")
    export_group.add_argument("--no-export", action="store_true", help="disabilita export anche dal tasto E")
    parser.add_argument("--output-prefix", default="copilot_models", help="nome base dei file in Downloads")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit deve essere almeno 1")
    return args


def _matches(value: str, preferred: list[str], overrides: list[str]) -> bool:
    folded = value.casefold()
    if preferred and folded not in {choice.casefold() for choice in preferred}:
        return False
    return not overrides or any(query.casefold() in folded for query in overrides)


def _sort_records(records: list[ModelPricing], sort_by: str, display_unit: str) -> list[ModelPricing]:
    attribute_by_sort = {
        "input": "input_cost",
        "cached_read": "cached_input_cost",
        "cached_write": "cache_write_cost",
        "output": "output_cost",
    }
    if sort_by in {"name", "provider"}:
        return sorted(records, key=lambda record: (getattr(record, sort_by).casefold(), record.name.casefold()))

    field = attribute_by_sort[sort_by]
    attribute = f"{field}_usd" if display_unit == "usd" else f"{field}_credits"
    return sorted(
        records,
        key=lambda record: (
            getattr(record, attribute) is None,
            getattr(record, attribute) if getattr(record, attribute) is not None else Decimal("Infinity"),
            record.name.casefold(),
        ),
    )


def filter_records(
    records: list[ModelPricing],
    preferences: Preferences,
    args: argparse.Namespace,
    *,
    include_saved_filters: bool = True,
) -> list[ModelPricing]:
    providers = preferences.providers if include_saved_filters else []
    categories = preferences.categories if include_saved_filters else []
    tiers = preferences.tiers if include_saved_filters else []
    statuses = preferences.release_statuses if include_saved_filters else []
    thresholds = preferences.thresholds if include_saved_filters else []
    selected = [
        record for record in records
        if _matches(record.name, [], args.model)
        and _matches(record.provider, providers, args.provider)
        and _matches(record.category, categories, args.category)
        and _matches(record.tier, tiers, args.tier)
        and _matches(record.release_status, statuses, args.status)
        and _matches(record.threshold, thresholds, args.threshold)
    ]
    sorted_records = _sort_records(selected, args.sort or preferences.sort_by, args.unit or preferences.display_unit)
    return sorted_records[:args.limit] if args.limit is not None else sorted_records


def _infer_reasoning(name: str) -> bool:
    lowered = name.casefold()
    return any(token in lowered for token in ("reasoning", "o1", "o3", "r1", "thinking", "astra", "luna", "pro", "fable 5.1", "opus 5.5", "sonnet 5.5"))


def fetch_live_records() -> list[ModelPricing]:
    records = parse_pricing_html(fetch_pricing_page())
    try:
        meta_map = match_model_metadata([record.name for record in records], fetch_model_metadata())
    except Exception:
        meta_map = {}
    return [
        replace(
            record,
            artificial_analysis_url=meta_map[record.name].url if record.name in meta_map else "",
            is_reasoning=(meta_map[record.name].is_reasoning if record.name in meta_map else False) or _infer_reasoning(record.name),
            context_window=meta_map[record.name].context_window if record.name in meta_map else "",
        )
        for record in records
    ]


def _export_with_consent(
    records: list[ModelPricing],
    preferences: Preferences,
    prefix: str,
    console: Console,
    *,
    confirmed: bool = False,
) -> list[Path]:
    if not preferences.export_formats:
        console.print("Nessun formato export selezionato. Usa S per il setup.", style="yellow")
        return []
    if not confirmed and not Confirm.ask(
        "Esportare i costi selezionati nella cartella Downloads?",
        default=False,
        console=console,
    ):
        return []
    paths = export_records(records, preferences.export_formats, prefix)
    console.print("File salvati in Downloads: " + ", ".join(path.name for path in paths), style="green")
    return paths


def _plain_output(records: list[ModelPricing], unit: str) -> None:
    console = Console()
    table = Table(title="Modelli GitHub Copilot | prezzi live", box=None, header_style="bold cyan")
    table.add_column("Modello")
    table.add_column("Contesto")
    table.add_column("Input", justify="right")
    table.add_column("Cached read", justify="right")
    table.add_column("Cached write", justify="right")
    table.add_column("Output", justify="right")

    def value(record: ModelPricing, kind: str) -> str:
        attribute = f"{kind}_cost_usd" if unit == "usd" else f"{kind}_cost_credits"
        if kind == "cached_read":
            attribute = "cached_input_cost_usd" if unit == "usd" else "cached_input_cost_credits"
        cost = getattr(record, attribute)
        if cost is None:
            return "N/D"
        return f"${cost:,.4f}" if unit == "usd" else f"{cost:,.2f} cr"

    for record in records:
        table.add_row(
            record.name,
            record.context_label,
            value(record, "input"),
            value(record, "cached_read"),
            value(record, "cache_write"),
            value(record, "output"),
        )
    console.print(table)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    console = Console()
    config_path = args.config_file or default_preferences_path()
    legacy_path = args.selection_file or config_path.with_name("selection.json")
    try:
        preferences = load_preferences(config_path, legacy_path)
    except (OSError, ValueError) as error:
        console.print(f"Configurazione non valida: {error}. Correggi il file o avvia con --setup.", style="red")
        return 2

    try:
        records = fetch_live_records()
    except (requests.RequestException, ValueError) as error:
        console.print(f"Impossibile leggere i prezzi live: {error}", style="red")
        return 1

    if args.clear_selection:
        preferences.favorite_models = []
        preferences.setup_completed = True
        save_preferences(preferences, config_path)

    if not preferences.setup_completed or args.setup:
        if not console.is_terminal or not sys.stdin.isatty():
            console.print("Il setup richiede un terminale interattivo. Avvia modelscompare in un terminale.", style="yellow")
            return 2
        configured = run_setup_wizard(records, preferences)
        if configured is None:
            console.print("Setup annullato; la configurazione esistente non è stata modificata.", style="yellow")
            return 0
        preferences = configured
        save_preferences(preferences, config_path)
        console.print(f"Configurazione salvata in {config_path}", style="green")

    preferences.favorite_models = list(dict.fromkeys(preferences.favorite_models))
    favorites = {name.casefold() for name in preferences.favorite_models}
    current_preferences = preferences
    active_unit = args.unit or preferences.display_unit
    filtered = filter_records(records, preferences, args, include_saved_filters=False)

    if not console.is_terminal or not sys.stdin.isatty():
        _plain_output(filtered, active_unit)
        if args.export:
            _export_with_consent(filtered, preferences, args.output_prefix, console, confirmed=True)
        return 0

    if args.export:
        _export_with_consent(filtered, current_preferences, args.output_prefix, console, confirmed=True)

    while True:
        browser = ModelBrowser(
            filtered,
            favorites=favorites,
            display_unit=active_unit,
            on_favorites_changed=lambda names: _persist_favorites(names, records, current_preferences, config_path),
            open_url=webbrowser.open,
        )
        browser.favorites_only = bool(favorites) and not args.all_models
        action = browser.run()
        if action == "quit":
            return 0
        if action == "setup":
            configured = run_setup_wizard(records, current_preferences)
            if configured is not None:
                current_preferences = configured
                preferences = configured
                save_preferences(preferences, config_path)
                favorites = {name.casefold() for name in preferences.favorite_models}
                active_unit = args.unit or preferences.display_unit
                filtered = filter_records(records, preferences, args, include_saved_filters=False)
            continue
        if action == "export":
            if args.no_export:
                console.print("Export disabilitato da --no-export.", style="yellow")
            else:
                _export_with_consent(filtered, current_preferences, args.output_prefix, console)
            continue
        if action == "refresh":
            try:
                records = fetch_live_records()
            except (requests.RequestException, ValueError) as error:
                console.print(f"Aggiornamento non riuscito: {error}", style="red")
                continue
            filtered = filter_records(records, current_preferences, args, include_saved_filters=False)


def _persist_favorites(
    favorite_keys: set[str],
    records: list[ModelPricing],
    preferences: Preferences,
    config_path: Path,
) -> None:
    preferences.favorite_models = [
        record.name for record in records if record.name.casefold() in favorite_keys
    ]
    save_preferences(preferences, config_path)


if __name__ == "__main__":
    raise SystemExit(main())
