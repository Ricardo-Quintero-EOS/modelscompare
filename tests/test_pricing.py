from decimal import Decimal

import pytest

from modelscompare.pricing import parse_pricing_html


PAGE = """
<p>1 AI credit = $0.01 USD.</p>
<p>All prices are per 1 million tokens.</p>
<h3>Example Provider</h3>
<table>
  <thead>
    <tr>
      <th>Model</th><th>Release status</th><th>Category</th><th>Tier</th>
      <th>Threshold (input tokens)</th><th>Input</th><th>Cached input</th>
      <th>Cache write</th><th>Output</th>
    </tr>
  </thead>
  <tbody>
    <tr><td>Example Model</td><td>GA</td><td>Versatile</td><td>Default</td>
      <td>Not applicable</td><td>$1.00</td><td>$0.10</td><td>Not applicable</td><td>$4.00</td></tr>
  </tbody>
</table>
<table>
  <tr><th>Model</th><th>Input</th><th>Output</th></tr>
  <tr><td>Second Model</td><td>$0.25</td><td>$2.00</td></tr>
</table>
"""


def test_parses_all_pricing_tables_and_converts_usd_to_credits() -> None:
    records = parse_pricing_html(PAGE)

    assert [record.name for record in records] == ["Example Model", "Second Model"]
    first = records[0]
    assert first.input_cost_credits == Decimal("100")
    assert first.cached_input_cost_credits == Decimal("10")
    assert first.cache_write_cost_credits is None
    assert first.output_cost_credits == Decimal("400")
    assert first.input_cost_usd == Decimal("1.00")
    assert first.cached_input_cost_usd == Decimal("0.10")
    assert first.cache_write_cost_usd is None
    assert first.output_cost_usd == Decimal("4.00")
    assert first.tier == "Default"
    assert first.provider == "Example Provider"


def test_requires_live_credit_and_price_unit_metadata() -> None:
    with pytest.raises(ValueError, match="AI-credit-to-USD"):
        parse_pricing_html("<p>All prices are per 1 million tokens.</p>")


def test_ignores_tables_without_model_input_and_output_headers() -> None:
    html = PAGE.replace("<th>Output</th>", "<th>Response</th>")
    with pytest.raises(ValueError, match="No GitHub Copilot pricing tables"):
        parse_pricing_html(html)
