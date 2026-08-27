from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import yaml

from deepresearch_cli.search.paths import builtin_search_dir
from deepresearch_cli.search.registry import DomainRegistry, ProviderRegistry
from deepresearch_cli.search.service import SearchService
from deepresearch_cli.search.store import SearchStore
from tests.search_test_utils import write_search_source


def _write_domain(search_dir: Path, name: str, sources: list[str]) -> None:
    path = search_dir / "domains" / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "name": name,
                "description": f"{name} test domain",
                "default_operation": "discovery",
                "operations": {
                    "discovery": {
                        "description": "fan out to test sources",
                        "sources": sources,
                    }
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _service(tmp_path: Path) -> tuple[SearchService, Path]:
    search_dir = tmp_path / "search"
    call_log = tmp_path / "calls.jsonl"
    for source in ("source_a", "source_b"):
        write_search_source(
            search_dir,
            source,
            script_text=f"""\
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('query')
parser.add_argument('--limit')
args = parser.parse_args()
with Path({str(call_log)!r}).open('a', encoding='utf-8') as stream:
    stream.write(json.dumps({{'source': {source!r}, 'query': args.query}}) + '\\n')
print(json.dumps({{'success': True, 'items': [{{
    'title': {source!r} + ' result',
    'url': 'https://example.test/{source}',
}}]}}))
""",
        )
    _write_domain(search_dir, "test_domain", ["source_a", "source_b"])
    sources = ProviderRegistry(search_dir=search_dir, python_executable=sys.executable)
    domains = DomainRegistry(search_dir=search_dir, source_registry=sources)
    return (
        SearchService(
            registry=sources,
            domain_registry=domains,
            store=SearchStore(tmp_path / "store"),
        ),
        call_log,
    )


def test_builtin_registry_exposes_eight_domains() -> None:
    sources = ProviderRegistry(
        search_dir=builtin_search_dir(), python_executable=sys.executable
    )
    domains = DomainRegistry(
        search_dir=builtin_search_dir(), source_registry=sources
    )

    assert set(domains.names) == {
        "academic",
        "financial_market",
        "corporate_disclosure",
        "software_engineering",
        "ai_model_ecosystem",
        "social_community",
        "video_media",
        "general_web",
    }
    _, literature = domains.resolve("academic", "literature_search")
    assert literature.sources == (
        "academic_openalex",
        "academic_crossref",
        "academic_arxiv",
        "academic_semantic_scholar",
    )
    general_domain, web_search = domains.resolve("general_web", None)
    assert general_domain.default_operation == "web_search"
    assert web_search.sources == ("general_duckduckgo", "general_wikipedia")


def test_custom_registry_without_domains_keeps_source_search_compatible(
    tmp_path: Path,
) -> None:
    search_dir = tmp_path / "search"
    write_search_source(search_dir, "custom")
    sources = ProviderRegistry(search_dir=search_dir, python_executable=sys.executable)
    domains = DomainRegistry(search_dir=search_dir, source_registry=sources)

    assert domains.names == ()


def test_domain_search_fans_out_and_keeps_domain_provenance(tmp_path: Path) -> None:
    service, call_log = _service(tmp_path)

    result = service.domain_search(
        [
            {
                "domain": "test_domain",
                "operation": "discovery",
                "query": "shared query",
                "source_queries": {"source_b": "specific query"},
                "evidence_target": "target",
                "intent": "test fan-out",
            }
        ]
    )

    calls = [json.loads(line) for line in call_log.read_text().splitlines()]
    assert {(item["source"], item["query"]) for item in calls} == {
        ("source_a", "shared query"),
        ("source_b", "specific query"),
    }
    assert result["domain_status"] == "succeeded"
    page = service.search_results(batch_id=result["batch_id"])
    assert page["total"] == 2
    assert {item["domain"] for item in page["items"]} == {"test_domain"}
    assert {item["operation"] for item in page["items"]} == {"discovery"}


def test_async_domain_search_returns_batch_before_completion(tmp_path: Path) -> None:
    service, _ = _service(tmp_path)
    started = service.start_domain_search(
        [
            {
                "domain": "test_domain",
                "query": "async query",
                "evidence_target": "target",
                "intent": "test background batch",
            }
        ]
    )

    assert started["status"] == "running"
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        status = service.get_search_batch(started["batch_id"])
        if status["status"] != "running":
            break
        time.sleep(0.02)
    assert status["status"] == "succeeded"
    assert service.search_results(batch_id=started["batch_id"])["total"] == 2
