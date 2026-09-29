import re
from decimal import Decimal, InvalidOperation

import requests
from bs4 import BeautifulSoup, Tag

from modelscompare.models import ModelPricing

PRICING_URL = "https://docs.github.com/copilot/reference/copilot-billing/models-and-pricing"


def fetch_pricing_page(timeout: float = 30) -> str:
    response = requests.get(
        PRICING_URL,
        headers={"User-Agent": "modelscompare/0.1 (+https://docs.github.com/)"},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.text


def _normalize_header(value: str) -> str:
    return " ".join(value.casefold().replace("_", " ").split())


def _column_index(headers: list[str], kind: str) -> int | None:
    normalized = [_normalize_header(header) for header in headers]
    if kind == "model":
        matches = [i for i, value in enumerate(normalized) if value == "model" or value.startswith("model ")]
    elif kind == "input":
        matches = [
            i for i, value in enumerate(normalized)
            if "input" in value
            and "cached" not in value
            and "cache write" not in value
            and "threshold" not in value
        ]
    elif kind == "cached_input":
        matches = [i for i, value in enumerate(normalized) if "cached" in value and "input" in value]
    elif kind == "cache_write":
        matches = [i for i, value in enumerate(normalized) if "cache write" in value]
    elif kind == "output":
        matches = [
            i for i, value in enumerate(normalized)
            if "output" in value and "cached" not in value
        ]
    else:
        raise ValueError(f"Unsupported pricing column: {kind}")
    return matches[0] if matches else None


def _cell_text(cell: Tag) -> str:
    return cell.get_text(" ", strip=True)


def _parse_price(value: str) -> Decimal | None:
    if not value or "not applicable" in value.casefold():
        return None
    match = re.search(r"(?<![\w.])-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", value)
    if match is None:
        return None
    try:
        return Decimal(match.group(0).replace(",", ""))
    except InvalidOperation:
        return None


def _pricing_metadata(page_text: str) -> tuple[Decimal, bool]:
    credit_match = re.search(
        r"1\s+AI\s+credit\s*=\s*\$?\s*(\d+(?:\.\d+)?)\s*USD",
        page_text,
        re.IGNORECASE,
    )
    if credit_match is None:
        raise ValueError("Could not find the AI-credit-to-USD conversion in GitHub's pricing page.")
    usd_per_credit = Decimal(credit_match.group(1))
    if usd_per_credit <= 0:
        raise ValueError("GitHub's published AI credit conversion is not positive.")

    per_million_tokens = bool(
        re.search(r"per\s+(?:1\s+)?million\s+tokens", page_text, re.IGNORECASE)
        or re.search(r"per\s+1\s*M\s+tokens", page_text, re.IGNORECASE)
    )
    if not per_million_tokens:
        raise ValueError("Could not verify the pricing table's per-million-token unit.")
    return usd_per_credit, per_million_tokens


def parse_pricing_html(html: str) -> list[ModelPricing]:
    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text(" ", strip=True)
    usd_per_credit, _ = _pricing_metadata(page_text)
    records: list[ModelPricing] = []

    for table in soup.find_all("table"):
        header_row = table.find("thead")
        header_row = header_row.find("tr") if header_row else None
        if header_row is None:
            header_row = next(
                (row for row in table.find_all("tr") if row.find_all("th", recursive=False)),
                None,
            )
        if header_row is None:
            continue

        header_cells = header_row.find_all(["th", "td"], recursive=False)
        headers = [_cell_text(cell) for cell in header_cells]
        model_index = _column_index(headers, "model")
        input_index = _column_index(headers, "input")
        output_index = _column_index(headers, "output")
        if model_index is None or input_index is None or output_index is None:
            continue

        cached_input_index = _column_index(headers, "cached_input")
        cache_write_index = _column_index(headers, "cache_write")
        normalized_headers = [_normalize_header(header) for header in headers]
        optional_columns = {
            field_name: next(
                (
                    i for i, value in enumerate(normalized_headers)
                    if value == field_name.replace("_", " ")
                    or (field_name == "threshold" and value.startswith("threshold "))
                ),
                None,
            )
            for field_name in ("release_status", "category", "tier", "threshold")
        }

        provider_heading = table.find_previous(["h2", "h3", "h4"])
        provider = _cell_text(provider_heading) if provider_heading else ""
        for row in table.find_all("tr"):
            if row is header_row:
                continue
            cells = row.find_all(["td", "th"], recursive=False)
            if len(cells) <= max(model_index, input_index, output_index):
                continue
            name = _cell_text(cells[model_index])
            if not name or name.casefold() == "model":
                continue

            def cell_at(index: int | None) -> str:
                return _cell_text(cells[index]) if index is not None and index < len(cells) else ""

            def credits_at(index: int | None) -> Decimal | None:
                usd_per_million = _parse_price(cell_at(index))
                return usd_per_million / usd_per_credit if usd_per_million is not None else None

            records.append(
                ModelPricing(
                    name=name,
                    input_cost_credits=credits_at(input_index),
                    output_cost_credits=credits_at(output_index),
                    cached_input_cost_credits=credits_at(cached_input_index),
                    cache_write_cost_credits=credits_at(cache_write_index),
                    release_status=cell_at(optional_columns["release_status"]),
                    category=cell_at(optional_columns["category"]),
                    tier=cell_at(optional_columns["tier"]),
                    threshold=cell_at(optional_columns["threshold"]),
                    provider=provider,
                    usd_per_credit=usd_per_credit,
                )
            )

    if not records:
        raise ValueError("No GitHub Copilot pricing tables with Model, Input, and Output columns were found.")
    return records
