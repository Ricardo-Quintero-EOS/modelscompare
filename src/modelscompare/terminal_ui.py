import webbrowser
from collections.abc import Callable, Sequence
from decimal import Decimal
from typing import Any

from prompt_toolkit import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style

from modelscompare.models import ModelPricing


class ModelBrowser:
    def __init__(
        self,
        records: Sequence[ModelPricing],
        favorites: set[str],
        display_unit: str = "usd",
        on_favorites_changed: Callable[[set[str]], None] | None = None,
        open_url: Callable[[str], Any] = webbrowser.open,
        input: Any = None,
        output: Any = None,
    ) -> None:
        self.records = list(records)
        self.favorites = {name.casefold() for name in favorites}
        self.display_unit = display_unit
        self.on_favorites_changed = on_favorites_changed or (lambda _favorites: None)
        self.open_url = open_url
        self.input = input
        self.output = output
        self.index = 0
        self.favorites_only = False
        self.comparison_selection: set[str] = set()
        self.comparing = False
        self.result: str | None = None

    @property
    def visible_records(self) -> list[ModelPricing]:
        if self.comparing:
            return [
                record for record in self.records
                if record.name.casefold() in self.comparison_selection
            ]
        if not self.favorites_only:
            return self.records
        return [record for record in self.records if record.name.casefold() in self.favorites]

    @property
    def selected_record(self) -> ModelPricing | None:
        visible = self.visible_records
        if not visible:
            return None
        self.index = min(max(0, self.index), len(visible) - 1)
        return visible[self.index]

    def _format_cost(self, record: ModelPricing, field: str) -> str:
        attribute = f"{field}_cost_credits" if field != "cached_read" else "cached_input_cost_credits"
        usd_attribute = f"{field}_cost_usd" if field != "cached_read" else "cached_input_cost_usd"
        value = getattr(record, usd_attribute if self.display_unit == "usd" else attribute)
        if value is None:
            return "N/A"
        if self.display_unit == "usd":
            return f"${value:,.4f}"
        return f"{value:,.2f} cr"

    def _header(self) -> FormattedText:
        visible = self.visible_records
        count = len(visible)
        selected_count = len(self.comparison_selection)
        unit = "USD / 1M token" if self.display_unit == "usd" else "crediti AI / 1M token"

        fragments: list[tuple[str, str]] = [
            ("class:banner.frame", " ╭────────────────────────────────────────────────────────────────────────────────────────╮\n"),
            ("class:banner.frame", " │ "),
            ("class:banner.brand", "⚡ MODELS"),
            ("class:banner.brand", " "),
            ("class:banner.logoaccent", "COMPARE"),
            ("class:banner.title", "  •  GitHub Copilot Live Pricing & Model Intelligence            "),
            ("class:banner.frame", "│\n"),
            ("class:banner.frame", " │ "),
            ("class:badge.live", " ● LIVE "),
            ("class:banner.title", f" {count} modelli  •  "),
            ("class:badge.unit", f" {unit} "),
            ("class:banner.title", "  •  "),
        ]
        if self.comparing:
            fragments.extend([
                ("class:badge.compare", f" confronto ({selected_count} modelli) "),
                ("class:banner.title", " [Esc per tornare alla lista] "),
            ])
        elif self.favorites_only:
            fragments.extend([
                ("class:badge.mode", f" PREFERITI ({count}) "),
                ("class:banner.title", "                                      "),
            ])
        else:
            fragments.extend([
                ("class:badge.mode", " TUTTI I MODELLI "),
                ("class:banner.title", "                                       "),
            ])
        fragments.extend([
            ("class:banner.frame", "│\n"),
            ("class:banner.frame", " ╰────────────────────────────────────────────────────────────────────────────────────────╯\n"),
        ])
        return FormattedText(fragments)

    def _row_fragments(self) -> FormattedText:
        visible = self.visible_records
        if not visible:
            if self.comparing:
                return FormattedText([("class:muted", "\n Nessun modello selezionato per il confronto. Premi Esc per tornare all'elenco completo.\n")])
            return FormattedText([("class:muted", "\n Nessun preferito salvato. Premi A per tornare all'elenco di tutti i modelli.\n")])

        size = get_app().output.get_size()
        width, height = size.columns, size.rows

        ctx_w = 14
        type_w = 13
        cost_w = 10
        cached_w = 11
        model_w = max(14, min(26, width - 74))
        table_width = model_w + 68

        fragments: list[tuple[str, str]] = []

        header = (
            f"   › ★ ✓  {'MODELLO':<{model_w}}  {'CONTESTO':<{ctx_w}}  "
            f"{'TIPO':<{type_w}}  {'INPUT':>{cost_w}}  {'CACHED-R':>{cached_w}}  "
            f"{'CACHED-W':>{cached_w}}  {'OUTPUT':>{cost_w}}\n"
        )
        fragments.append(("class:table.header", header))
        fragments.append(("class:table.divider", f"  {'─' * table_width}\n"))

        display_height = max(1, height - 13)
        start = max(0, min(self.index - display_height // 2, len(visible) - display_height))
        stop = min(len(visible), start + display_height)

        for row_index in range(start, stop):
            record = visible[row_index]
            selected = row_index == self.index
            favorite = record.name.casefold() in self.favorites
            in_compare = record.name.casefold() in self.comparison_selection

            cursor = "›" if selected else " "
            star = "★" if favorite else "·"
            check = "✓" if in_compare else "·"

            name = record.name
            if len(name) > model_w:
                name = name[: model_w - 3] + "..."

            ctx = record.context_label
            if len(ctx) > ctx_w:
                ctx = ctx[: ctx_w - 2] + ".."

            type_label = "🧠 Reasoning" if record.is_reasoning else "Standard"

            input_val = self._format_cost(record, "input")
            cached_r_val = self._format_cost(record, "cached_read")
            cached_w_val = self._format_cost(record, "cache_write")
            output_val = self._format_cost(record, "output")

            if selected:
                row_str = (
                    f"  {cursor} {star} {check}  {name:<{model_w}}  {ctx:<{ctx_w}}  "
                    f"{type_label:<{type_w}}  {input_val:>{cost_w}}  {cached_r_val:>{cached_w}}  "
                    f"{cached_w_val:>{cached_w}}  {output_val:>{cost_w}}\n"
                )
                fragments.append(("class:selected", row_str))
            else:
                fragments.extend([
                    ("class:row.cursor", f"  {cursor} "),
                    ("class:row.star_active" if favorite else "class:row.star_inactive", f"{star} "),
                    ("class:row.check_active" if in_compare else "class:row.check_inactive", f"{check}  "),
                    ("class:row.name", f"{name:<{model_w}}  "),
                    ("class:row.context_long" if "long" in ctx.casefold() else "class:row.context_def", f"{ctx:<{ctx_w}}  "),
                    ("class:row.reasoning_on" if record.is_reasoning else "class:row.reasoning_off", f"{type_label:<{type_w}}  "),
                    ("class:row.cost_input", f"{input_val:>{cost_w}}  "),
                    ("class:row.cost_cached", f"{cached_r_val:>{cached_w}}  "),
                    ("class:row.cost_na" if cached_w_val == "N/A" else "class:row.cost_write", f"{cached_w_val:>{cached_w}}  "),
                    ("class:row.cost_output", f"{output_val:>{cost_w}}\n"),
                ])

        return FormattedText(fragments)

    def _detail_card(self) -> FormattedText:
        record = self.selected_record
        size = get_app().output.get_size()
        width = max(80, size.columns - 4)
        box_width = min(width, 102)
        inner_width = box_width - 4

        if record is None:
            return FormattedText([
                ("class:card.frame", f" ╭─ Dettagli {'─' * (inner_width - 9)}╮\n"),
                ("class:card.frame", " │ "), ("class:muted", "Nessun modello disponibile".ljust(inner_width)), ("class:card.frame", " │\n"),
                ("class:card.frame", " │ "), ("class:muted", "".ljust(inner_width)), ("class:card.frame", " │\n"),
                ("class:card.frame", f" ╰{'─' * (inner_width + 2)}╯"),
            ])

        title_str = f" Dettagli Modello: {record.name} "
        if len(title_str) > inner_width - 4:
            title_str = title_str[:inner_width - 7] + "... "
        top_dashes = inner_width - len(title_str)

        line1_items = [
            f"Provider: {record.provider or 'N/D'}",
            f"Tier: {record.tier or 'Default'}",
            f"Soglia: {record.threshold or 'N/A'}",
        ]
        if record.category:
            line1_items.append(f"Cat: {record.category}")
        line1_str = "   •   ".join(line1_items)
        if len(line1_str) > inner_width:
            line1_str = line1_str[:inner_width - 3] + "..."
        line1_pad = inner_width - len(line1_str)

        reasoning_str = "🧠 Reasoning" if record.is_reasoning else "Standard"
        ctx_win = record.context_window or ("≤ 272K" if record.threshold else "Standard")
        aa_url = record.artificial_analysis_url or "N/D"
        line2_str = f"Tipo: {reasoning_str}   •   Finestra: {ctx_win}   •   AA: {aa_url}"
        if len(line2_str) > inner_width:
            line2_str = line2_str[:inner_width - 3] + "..."
        line2_pad = inner_width - len(line2_str)

        return FormattedText([
            ("class:card.frame", " ╭─"), ("class:card.title", title_str), ("class:card.frame", f"{'─' * max(0, top_dashes)}╮\n"),
            ("class:card.frame", " │ "), ("class:card.value", line1_str), ("class:card.value", " " * max(0, line1_pad)), ("class:card.frame", " │\n"),
            ("class:card.frame", " │ "), ("class:card.value", line2_str), ("class:card.value", " " * max(0, line2_pad)), ("class:card.frame", " │\n"),
            ("class:card.frame", f" ╰{'─' * (inner_width + 2)}╯"),
        ])

    def _footer(self) -> FormattedText:
        sel_count = len(self.comparison_selection)
        return FormattedText([
            ("class:keys.cap", " [↑/↓] "), ("class:keys.desc", "Naviga  "),
            ("class:keys.cap", " [M] "), ("class:keys.desc", "Seleziona  "),
            ("class:keys.cap", " [C] "), ("class:keys.desc", f"Confronta ({sel_count})  "),
            ("class:keys.cap", " [Space] "), ("class:keys.desc", "Preferito  "),
            ("class:keys.cap", " [Enter] "), ("class:keys.desc", "Scheda AA  "),
            ("class:keys.cap", " [A] "), ("class:keys.desc", "Tutti/Pref  "),
            ("class:keys.cap", " [S] "), ("class:keys.desc", "Setup  "),
            ("class:keys.cap", " [E] "), ("class:keys.desc", "Export  "),
            ("class:keys.cap", " [R] "), ("class:keys.desc", "Ricarica  "),
            ("class:keys.cap", " [Esc] "), ("class:keys.desc", "Reset  "),
            ("class:keys.cap", " [Q] "), ("class:keys.desc", "Esci"),
        ])

    def create_application(self) -> Application[str]:
        bindings = KeyBindings()

        def move(amount: int) -> None:
            count = len(self.visible_records)
            if count:
                self.index = min(max(self.index + amount, 0), count - 1)

        @bindings.add("up")
        def _up(event) -> None:
            move(-1)
            event.app.invalidate()

        @bindings.add("down")
        def _down(event) -> None:
            move(1)
            event.app.invalidate()

        @bindings.add("home")
        def _home(event) -> None:
            self.index = 0
            event.app.invalidate()

        @bindings.add("end")
        def _end(event) -> None:
            self.index = max(0, len(self.visible_records) - 1)
            event.app.invalidate()

        @bindings.add("pageup")
        def _page_up(event) -> None:
            move(-10)
            event.app.invalidate()

        @bindings.add("pagedown")
        def _page_down(event) -> None:
            move(10)
            event.app.invalidate()

        @bindings.add("enter")
        def _open_selected(event) -> None:
            record = self.selected_record
            if record and record.artificial_analysis_url:
                self.open_url(record.artificial_analysis_url)

        @bindings.add(" ")
        def _toggle_favorite(event) -> None:
            record = self.selected_record
            if record is None:
                return
            key = record.name.casefold()
            if key in self.favorites:
                self.favorites.remove(key)
            else:
                self.favorites.add(key)
            self.on_favorites_changed(set(self.favorites))
            if self.favorites_only and key not in self.favorites:
                self.index = min(self.index, max(0, len(self.visible_records) - 1))
            event.app.invalidate()

        @bindings.add("a")
        def _toggle_view(event) -> None:
            self.favorites_only = not self.favorites_only
            self.index = min(self.index, max(0, len(self.visible_records) - 1))
            event.app.invalidate()

        @bindings.add("m")
        def _toggle_comparison_selection(event) -> None:
            record = self.selected_record
            if record is None:
                return
            key = record.name.casefold()
            if key in self.comparison_selection:
                self.comparison_selection.remove(key)
            else:
                self.comparison_selection.add(key)
            event.app.invalidate()

        @bindings.add("c")
        def _toggle_comparison_view(event) -> None:
            if self.comparing:
                self.comparing = False
                self.index = 0
            elif self.comparison_selection:
                self.comparing = True
                self.index = 0
            event.app.invalidate()

        @bindings.add("escape")
        def _return_to_list(event) -> None:
            if self.comparing:
                self.comparing = False
                self.index = 0
                event.app.invalidate()

        @bindings.add("s")
        def _setup(event) -> None:
            event.app.exit(result="setup")

        @bindings.add("e")
        def _export(event) -> None:
            event.app.exit(result="export")

        @bindings.add("r")
        def _refresh(event) -> None:
            event.app.exit(result="refresh")

        @bindings.add("q")
        @bindings.add("c-c")
        def _quit(event) -> None:
            event.app.exit(result="quit")

        style = Style.from_dict({
            "banner.frame": "#2A454D",
            "banner.brand": "bold #5CE1E6",
            "banner.logoaccent": "bold #E0B76A",
            "banner.title": "#9AB2B8",
            "badge.live": "bold bg:#123528 #4ECCA3",
            "badge.unit": "bold bg:#332912 #F5CE69",
            "badge.mode": "bold bg:#162E3B #7AD2E6",
            "badge.compare": "bold bg:#3B1E32 #FF80AB",
            "keys.cap": "bold #5CE1E6",
            "keys.desc": "#8EA6AC",
            "table.header": "bold #7BE0AD",
            "table.divider": "#2A454D",
            "row.cursor": "bold #5CE1E6",
            "row.star_active": "bold #F9D423",
            "row.star_inactive": "#3A5056",
            "row.check_active": "bold #4ECCA3",
            "row.check_inactive": "#3A5056",
            "row.name": "#E3ECEB",
            "row.context_def": "#80CBC4",
            "row.context_long": "bold #FFB74D",
            "row.context_std": "#78909C",
            "row.reasoning_on": "bold #CE93D8",
            "row.reasoning_off": "#607D8B",
            "row.cost_input": "#B2DFDB",
            "row.cost_cached": "#80DEEA",
            "row.cost_write": "#FFE082",
            "row.cost_output": "#A7FFEB",
            "row.cost_na": "#4A6369",
            "selected": "bold bg:#163A42 #FFFFFF",
            "card.frame": "#2A454D",
            "card.title": "bold #7BE0AD",
            "card.label": "#7A959B",
            "card.value": "#E0EBEA",
            "muted": "#7A959B",
        })

        layout = Layout(HSplit([
            Window(FormattedTextControl(self._header), height=5, always_hide_cursor=True),
            Window(FormattedTextControl(self._row_fragments), wrap_lines=False, always_hide_cursor=True),
            Window(FormattedTextControl(self._detail_card), height=4, always_hide_cursor=True),
            Window(FormattedTextControl(self._footer), height=1, always_hide_cursor=True),
        ]))

        return Application(
            layout=layout,
            key_bindings=bindings,
            full_screen=True,
            mouse_support=False,
            style=style,
            input=self.input,
            output=self.output,
        )

    def run(self) -> str:
        return self.create_application().run()


def choose_options(
    title: str,
    options: Sequence[str],
    selected: Sequence[str] = (),
    *,
    multiple: bool = True,
    input: Any = None,
    output: Any = None,
) -> list[str] | None:
    choices = list(dict.fromkeys(options))
    selected_keys = {value.casefold() for value in selected}
    if not choices:
        return [] if multiple else None
    index = next((i for i, value in enumerate(choices) if value.casefold() in selected_keys), 0)
    checked = {i for i, value in enumerate(choices) if value.casefold() in selected_keys}
    outcome: list[str] | None = None
    bindings = KeyBindings()

    def finish(event) -> None:
        nonlocal outcome
        outcome = [choices[i] for i in sorted(checked)] if multiple else [choices[index]]
        event.app.exit()

    @bindings.add("up")
    def _up(event) -> None:
        nonlocal index
        index = max(0, index - 1)
        event.app.invalidate()

    @bindings.add("down")
    def _down(event) -> None:
        nonlocal index
        index = min(len(choices) - 1, index + 1)
        event.app.invalidate()

    @bindings.add("home")
    def _home(event) -> None:
        nonlocal index
        index = 0
        event.app.invalidate()

    @bindings.add("end")
    def _end(event) -> None:
        nonlocal index
        index = len(choices) - 1
        event.app.invalidate()

    @bindings.add(" ")
    def _toggle(event) -> None:
        nonlocal index
        if not multiple:
            checked.clear()
            checked.add(index)
        elif index in checked:
            checked.remove(index)
        else:
            checked.add(index)
        event.app.invalidate()

    @bindings.add("a")
    def _toggle_all(event) -> None:
        if not multiple:
            return
        if len(checked) == len(choices):
            checked.clear()
        else:
            checked.update(range(len(choices)))
        event.app.invalidate()

    @bindings.add("enter")
    def _enter(event) -> None:
        finish(event)

    @bindings.add("escape")
    @bindings.add("c-c")
    def _cancel(event) -> None:
        event.app.exit()

    def render_choices() -> FormattedText:
        fragments: list[tuple[str, str]] = [
            ("class:box", " ╭────────────────────────────────────────────────────────╮\n"),
            ("class:title", f" │  {title:<52}│\n"),
            ("class:help", " │  Frecce sposta • Spazio seleziona • Invio conferma     │\n"),
            ("class:box", " ╰────────────────────────────────────────────────────────╯\n\n"),
        ]
        for choice_index, value in enumerate(choices):
            marker = "›" if choice_index == index else " "
            checkmark = "[✓]" if choice_index in checked else "[ ]"
            if choice_index == index:
                fragments.append(("class:selected", f"  {marker} {checkmark} {value} \n"))
            else:
                fragments.append(("class:row", f"  {marker} {checkmark} {value}\n"))
        return FormattedText(fragments)

    style = Style.from_dict({
        "box": "#2A454D",
        "title": "bold #5CE1E6",
        "help": "#8FA3A8",
        "row": "#D0DDDC",
        "selected": "bold bg:#163A42 #FFFFFF",
    })
    app = Application(
        layout=Layout(Window(FormattedTextControl(render_choices), always_hide_cursor=True, wrap_lines=False)),
        key_bindings=bindings,
        full_screen=True,
        mouse_support=False,
        style=style,
        input=input,
        output=output,
    )
    app.run()
    return outcome
