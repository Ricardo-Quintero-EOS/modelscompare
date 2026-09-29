import json

from modelscompare.artificial_analysis import extract_model_links, match_model_links


def test_extracts_canonical_urls_from_embedded_json_catalog() -> None:
    model_data = {"modelsAndReleases": {"releases": [{"slug": "gpt-5-4", "name": "GPT 5.4"}]}}
    stream = "d:" + json.dumps(model_data)
    html = f"<script>self.__next_f.push({json.dumps([1, stream])})</script>"

    assert extract_model_links(html) == {
        "gpt54": "https://artificialanalysis.ai/models/gpt-5-4"
    }


def test_matches_canonical_model_path_without_manual_model_mapping() -> None:
    links = {"GPT-5.4": "https://artificialanalysis.ai/models/gpt-5-4"}

    assert match_model_links(["GPT 5.4"], links) == {
        "GPT 5.4": "https://artificialanalysis.ai/models/gpt-5-4"
    }


def test_unmatched_model_gets_search_link() -> None:
    result = match_model_links(["Unlisted Model"], {})["Unlisted Model"]

    assert result == "https://artificialanalysis.ai/models?search=Unlisted+Model"
