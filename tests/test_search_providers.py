import json
import sys

import pytest

from deepresearch_cli.search.contracts import (
    SearchContractError,
    SearchRequest,
    validate_search_requests,
)
from deepresearch_cli.search.providers import (
    ProviderRegistry,
    canonical_hit_keys,
    normalize_search_hits,
    parse_json_output,
    provider_payload_warnings,
)
from deepresearch_cli.search.paths import builtin_search_dir


@pytest.fixture
def academic_request() -> SearchRequest:
    return SearchRequest(
        provider="academic",
        query="graph agents",
        evidence_target="paper identity",
        intent="find primary research",
    )


def test_direct_search_request_objects_receive_the_same_strict_validation() -> None:
    with pytest.raises(SearchContractError, match="query cannot be empty"):
        validate_search_requests(
            [
                SearchRequest(
                    provider="hackernews",
                    query="   ",
                    evidence_target="target",
                    intent="intent",
                )
            ],
            provider_names=["hackernews"],
        )


def test_parse_json_output_skips_non_json_bracketed_log_prefixes() -> None:
    stdout = "[INFO] provider booting\n[DEBUG] retry=1\n{\"success\": true, \"items\": []}\n"

    assert parse_json_output(stdout) == {"success": True, "items": []}


def test_academic_route_uses_actual_fallback_provider(
    academic_request: SearchRequest,
) -> None:
    payload = {
        "success": True,
        "source_results": [
            {
                "source": "arxiv",
                "provider": "openalex",
                "success": True,
                "items": [
                    {
                        "title": "A paper",
                        "url": "https://openalex.org/W1",
                        "provider": "openalex",
                    }
                ],
            }
        ],
    }

    [hit] = normalize_search_hits(
        request=academic_request,
        payload=payload,
        result_shape="academic",
    )

    assert hit["provider"] == "academic:openalex"
    assert hit["metadata"]["_academic_source"] == "arxiv"
    assert hit["metadata"]["_academic_provider"] == "openalex"


def test_academic_partial_failure_has_structured_warning() -> None:
    payload = {
        "success": True,
        "source_results": [
            {
                "source": "arxiv",
                "provider": "openalex",
                "success": True,
                "items": [{"title": "A", "url": "https://example.test/a"}],
                "attempts": [],
                "error": None,
            },
            {
                "source": "semantic",
                "provider": None,
                "success": False,
                "items": [],
                "attempts": [
                    {
                        "provider": "semantic_scholar_official",
                        "success": False,
                        "error": "HTTP 429",
                    }
                ],
                "error": "all semantic providers failed",
            },
        ],
    }

    assert provider_payload_warnings(payload) == [
        {
            "code": "provider_source_failed",
            "source": "semantic",
            "provider": None,
            "error": "all semantic providers failed",
            "attempts": [
                {
                    "provider": "semantic_scholar_official",
                    "success": False,
                    "error": "HTTP 429",
                }
            ],
        }
    ]


def test_academic_title_is_not_a_dedupe_key_when_stable_identity_exists() -> None:
    first = {
        "source_provider": "academic",
        "title": "Identical title",
        "url": "https://publisher.test/paper-a",
        "metadata": {"doi": "10.1000/a"},
    }
    second = {
        "source_provider": "academic",
        "title": "Identical title",
        "url": "https://publisher.test/paper-b",
        "metadata": {"doi": "10.1000/b"},
    }

    first_keys = set(canonical_hit_keys(first))
    second_keys = set(canonical_hit_keys(second))

    assert not any(key.startswith("academic_title:") for key in first_keys)
    assert first_keys.isdisjoint(second_keys)


def test_arxiv_versions_share_one_stable_identity_key() -> None:
    first = {
        "source_provider": "academic",
        "title": "Paper v1",
        "url": "https://arxiv.org/abs/2401.01234v1",
        "metadata": {"arxiv_id": "arXiv:2401.01234v1"},
    }
    second = {
        "source_provider": "academic",
        "title": "Paper v3",
        "url": "https://arxiv.org/pdf/2401.01234v3.pdf",
        "metadata": {"arxiv_id": "2401.01234v3"},
    }

    assert "arxiv_id:2401.01234" in canonical_hit_keys(first)
    assert set(canonical_hit_keys(first)) & set(canonical_hit_keys(second))


def test_sec_filing_title_contains_entity_form_and_date() -> None:
    request = SearchRequest(
        provider="annual_report_sec",
        query="AAPL",
        evidence_target="annual filing",
        intent="find the primary filing",
    )
    payload = {
        "data": {
            "entity_name": "Apple Inc.",
            "cik": "0000320193",
            "tickers": ["AAPL"],
            "items": [
                {
                    "form": "10-K",
                    "filing_date": "2025-10-31",
                    "report_date": "2025-09-27",
                    "document_url": "https://www.sec.gov/example.htm",
                }
            ],
        }
    }

    [hit] = normalize_search_hits(
        request=request,
        payload=payload,
        result_shape="annual_report_sec",
    )

    assert hit["title"] == "Apple Inc. 10-K 2025-09-27"
    assert hit["metadata"]["entity_name"] == "Apple Inc."
    assert hit["metadata"]["filing_date"] == "2025-10-31"


def test_interaction_and_date_metadata_is_retained() -> None:
    request = SearchRequest(
        provider="douyin",
        query="agent",
        evidence_target="user response",
        intent="find public reactions",
    )
    payload = {
        "items": [
            {
                "title": "Agent demo",
                "url": "https://www.douyin.com/video/1",
                "create_time": 1_755_000_000,
                "digg_count": 21,
                "comment_count": 8,
                "share_count": 3,
                "play_count": 100,
            }
        ]
    }

    [hit] = normalize_search_hits(request=request, payload=payload)

    assert hit["metadata"] == {
        "create_time": 1_755_000_000,
        "digg_count": 21,
        "comment_count": 8,
        "share_count": 3,
        "play_count": 100,
    }


def test_raw_item_limits_are_hard_and_truncation_is_reported() -> None:
    request = SearchRequest(
        provider="hackernews",
        query="large",
        evidence_target="stress fixture",
        intent="verify bounded output",
    )
    oversized = {
        "title": "Large result",
        "url": "https://example.test/large",
        "snippet": "s" * 9_000,
        "large_array": ["x" * 9_000 for _ in range(100)],
        **{f"field_{index}": "v" * 9_000 for index in range(100)},
    }

    [hit] = normalize_search_hits(
        request=request,
        payload={"items": [oversized]},
    )

    assert hit["raw_item_truncated"] is True
    assert len(json.dumps(hit["raw_item"], ensure_ascii=False)) <= 20_000

    def assert_hard_limits(value) -> None:
        if isinstance(value, str):
            assert len(value) <= 4_000
        elif isinstance(value, dict):
            assert len(value) <= 80
            for nested in value.values():
                assert_hard_limits(nested)
        elif isinstance(value, list):
            assert len(value) <= 80
            for nested in value:
                assert_hard_limits(nested)

    assert_hard_limits(hit["raw_item"])


def test_provider_environment_contracts_match_route_credentials() -> None:
    registry = ProviderRegistry(
        search_dir=builtin_search_dir(),
        python_executable=sys.executable,
    )
    definitions = {definition.name: definition for definition in registry.definitions}

    assert definitions["github_repositories"].environment_variables == (
        "GITHUB_TOKEN",
    )
    assert definitions["academic"].environment_variables == ()
    assert definitions["annual_report_sec"].environment_variables == (
        "YEAR_REPORT_USER_AGENT",
        "SEC_USER_AGENT",
    )
