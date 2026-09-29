from decimal import Decimal
from unittest.mock import Mock

from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from modelscompare.models import ModelPricing
from modelscompare.terminal_ui import ModelBrowser, choose_options


def _models() -> list[ModelPricing]:
    return [
        ModelPricing(
            name="Input Model",
            input_cost_credits=Decimal("100"),
            output_cost_credits=Decimal("200"),
            cached_input_cost_credits=Decimal("10"),
            cache_write_cost_credits=Decimal("20"),
            usd_per_credit=Decimal("0.01"),
            artificial_analysis_url="https://artificialanalysis.ai/models/input-model",
        ),
        ModelPricing(
            name="Output Model",
            input_cost_credits=Decimal("50"),
            output_cost_credits=Decimal("150"),
            artificial_analysis_url="https://artificialanalysis.ai/models/output-model",
        ),
    ]


def test_arrow_navigation_and_enter_open_selected_model(monkeypatch) -> None:
    opener = Mock()
    with create_pipe_input() as input_pipe:
        browser = ModelBrowser(
            _models(),
            favorites=set(),
            open_url=opener,
            input=input_pipe,
            output=DummyOutput(),
        )
        input_pipe.send_text("\x1b[B\r q")
        result = browser.run()

    assert result == "quit"
    opener.assert_called_once_with("https://artificialanalysis.ai/models/output-model")


def test_space_persists_favorite_changes() -> None:
    on_change = Mock()
    with create_pipe_input() as input_pipe:
        browser = ModelBrowser(
            _models(),
            favorites=set(),
            on_favorites_changed=on_change,
            input=input_pipe,
            output=DummyOutput(),
        )
        input_pipe.send_text(" q")
        browser.run()

    on_change.assert_called_once_with({"input model"})


def test_browser_can_switch_to_favorites_only_view() -> None:
    with create_pipe_input() as input_pipe:
        browser = ModelBrowser(
            _models(),
            favorites={"output model"},
            input=input_pipe,
            output=DummyOutput(),
        )
        assert [record.name for record in browser.visible_records] == ["Input Model", "Output Model"]
        input_pipe.send_text("aq")
        browser.run()

    assert browser.favorites_only
    assert [record.name for record in browser.visible_records] == ["Output Model"]


def test_option_picker_returns_selected_values() -> None:
    with create_pipe_input() as input_pipe:
        input_pipe.send_text("\x1b[B \r")
        result = choose_options(
            "Provider",
            ["OpenAI", "Anthropic"],
            input=input_pipe,
            output=DummyOutput(),
        )

    assert result == ["Anthropic"]


def test_browser_cost_renderer_has_no_blended_values() -> None:
    browser = ModelBrowser(_models(), favorites=set(), display_unit="usd")
    values = [browser._format_cost(browser.records[0], field) for field in (
        "input", "cached_read", "cache_write", "output",
    )]

    assert values == ["$1.0000", "$0.1000", "$0.2000", "$2.0000"]
    assert not hasattr(browser.records[0], "blended_cost_credits")


def test_browser_header_has_graphical_modelscompare_wordmark() -> None:
    browser = ModelBrowser(_models(), favorites=set())
    header = "".join(text for _style, text in browser._header())

    assert "MODELS" in header
    assert "COMPARE" in header
    assert "╭" in header or "+" in header


def test_select_models_and_compare_only_the_selection() -> None:
    with create_pipe_input() as input_pipe:
        browser = ModelBrowser(
            _models(),
            favorites=set(),
            input=input_pipe,
            output=DummyOutput(),
        )
        input_pipe.send_text("m\x1b[Bmcq")
        browser.run()

    assert browser.comparison_selection == {"input model", "output model"}
    assert browser.comparing
    assert [record.name for record in browser.visible_records] == ["Input Model", "Output Model"]
    assert "confronto" in "".join(text for _style, text in browser._header())


def test_escape_returns_from_comparison_without_clearing_selection() -> None:
    with create_pipe_input() as input_pipe:
        browser = ModelBrowser(
            _models(),
            favorites=set(),
            input=input_pipe,
            output=DummyOutput(),
        )
        input_pipe.send_text("mc\x1bq")
        browser.run()

    assert not browser.comparing
    assert browser.comparison_selection == {"input model"}
    assert [record.name for record in browser.visible_records] == ["Input Model", "Output Model"]


def test_browser_renders_context_and_reasoning_in_table_and_card() -> None:
    model = ModelPricing(
        name="GPT-6 Luna",
        input_cost_credits=Decimal("100"),
        output_cost_credits=Decimal("500"),
        threshold="≤ 272K",
        tier="Default",
        provider="OpenAI",
        is_reasoning=True,
        context_window="1M",
        artificial_analysis_url="https://artificialanalysis.ai/models/gpt-6-luna",
    )
    browser = ModelBrowser([model], favorites=set())

    assert model.context_label == "≤ 272K (Def)"
    assert model.reasoning_label == "Reasoning"

    card_text = "".join(text for _style, text in browser._detail_card())
    assert "GPT-6 Luna" in card_text
    assert "OpenAI" in card_text
    assert "≤ 272K" in card_text
    assert "Reasoning" in card_text
    assert "1M" in card_text

    header_text = "".join(text for _style, text in browser._header())
    assert "MODELS" in header_text
    assert "COMPARE" in header_text


def test_browser_distinguishes_default_and_long_context_variants() -> None:
    m_default = ModelPricing(
        name="GPT-6 Luna",
        input_cost_credits=Decimal("100"),
        output_cost_credits=Decimal("500"),
        threshold="≤ 272K",
        tier="Default",
    )
    m_long = ModelPricing(
        name="GPT-6 Luna",
        input_cost_credits=Decimal("200"),
        output_cost_credits=Decimal("750"),
        threshold="> 272K",
        tier="Long context",
    )
    assert m_default.context_label == "≤ 272K (Def)"
    assert m_long.context_label == "> 272K (Long)"
    assert m_default.context_label != m_long.context_label
