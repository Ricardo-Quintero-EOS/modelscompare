from dataclasses import dataclass
import json
import re
from difflib import SequenceMatcher
from urllib.parse import quote_plus, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ARTIFICIAL_ANALYSIS_MODELS_URL = "https://artificialanalysis.ai/models"


@dataclass(frozen=True, slots=True)
class ModelMetadata:
    url: str = ""
    is_reasoning: bool = False
    context_window: str = ""


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _format_context_tokens(tokens: object) -> str:
    if isinstance(tokens, (int, float)) and tokens > 0:
        if tokens >= 1_000_000:
            return f"{int(tokens // 1_000_000)}M"
        return f"{int(tokens // 1_000)}K"
    return ""


def fetch_model_metadata(timeout: float = 30) -> dict[str, ModelMetadata]:
    response = requests.get(
        ARTIFICIAL_ANALYSIS_MODELS_URL,
        headers={"User-Agent": "modelscompare/0.1"},
        timeout=timeout,
    )
    response.raise_for_status()
    return extract_model_metadata(response.text)


def extract_model_metadata(html: str) -> dict[str, ModelMetadata]:
    soup = BeautifulSoup(html, "html.parser")
    metadata: dict[str, ModelMetadata] = {}

    for anchor in soup.find_all("a", href=True):
        label = anchor.get_text(" ", strip=True)
        url = urljoin(ARTIFICIAL_ANALYSIS_MODELS_URL, anchor["href"])
        path = urlparse(url).path.rstrip("/")
        if label and urlparse(url).netloc == "artificialanalysis.ai" and re.fullmatch(r"/models/[^/]+", path):
            key = _key(label)
            metadata.setdefault(key, ModelMetadata(url=url))

    for script in soup.find_all("script"):
        script_text = script.string or script.get_text()
        match = re.search(r"self\.__next_f\.push\((\[.*\])\)", script_text, re.DOTALL)
        if match is None:
            continue
        try:
            payload = json.loads(match.group(1))
            stream = payload[1]
            root = json.loads(stream[stream.find(":") + 1 :])
        except (IndexError, TypeError, json.JSONDecodeError):
            continue

        pending = [root]
        while pending:
            item = pending.pop()
            if isinstance(item, dict):
                slug = item.get("slug")
                name = item.get("name")
                if isinstance(slug, str) and isinstance(name, str) and slug:
                    url = urljoin(ARTIFICIAL_ANALYSIS_MODELS_URL, f"/models/{slug}")
                    is_reasoning = bool(item.get("isReasoning"))
                    cw = _format_context_tokens(item.get("contextWindowTokens"))
                    entry = ModelMetadata(url=url, is_reasoning=is_reasoning, context_window=cw)
                    for key in (_key(name), _key(slug)):
                        if key not in metadata:
                            metadata[key] = entry
                        else:
                            current = metadata[key]
                            metadata[key] = ModelMetadata(
                                url=current.url or url,
                                is_reasoning=current.is_reasoning or is_reasoning,
                                context_window=current.context_window or cw,
                            )
                pending.extend(item.values())
            elif isinstance(item, list):
                pending.extend(item)
    return metadata


def fetch_model_links(timeout: float = 30) -> dict[str, str]:
    meta = fetch_model_metadata(timeout=timeout)
    return {k: v.url for k, v in meta.items()}


def extract_model_links(html: str) -> dict[str, str]:
    meta = extract_model_metadata(html)
    return {k: v.url for k, v in meta.items()}


def match_model_metadata(names: list[str], metadata: dict[str, ModelMetadata]) -> dict[str, ModelMetadata]:
    normalized = {_key(k): v for k, v in metadata.items()}
    matches: dict[str, ModelMetadata] = {}
    for name in names:
        key = _key(name)
        if key in normalized:
            matches[name] = normalized[key]
            continue

        candidates = sorted(
            ((SequenceMatcher(None, key, candidate).ratio(), meta) for candidate, meta in normalized.items()),
            reverse=True,
            key=lambda item: item[0],
        )
        if candidates and candidates[0][0] >= 0.92 and (
            len(candidates) == 1 or candidates[0][0] > candidates[1][0]
        ):
            matches[name] = candidates[0][1]
        else:
            search_url = f"{ARTIFICIAL_ANALYSIS_MODELS_URL}?search={quote_plus(name)}"
            matches[name] = ModelMetadata(url=search_url)
    return matches


def match_model_links(names: list[str], links: dict[str, str]) -> dict[str, str]:
    meta_dict = {k: ModelMetadata(url=v) for k, v in links.items()}
    matched = match_model_metadata(names, meta_dict)
    return {k: v.url for k, v in matched.items()}
