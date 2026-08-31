from __future__ import annotations

import json
import sys
from pathlib import Path

from deepresearch_cli.search.paths import builtin_search_dir
from deepresearch_cli.search.contracts import SearchRequest
from deepresearch_cli.search.providers import (
    ProviderRegistry,
    load_search_environment,
)
from deepresearch_cli.search.service import SearchService
from deepresearch_cli.search.store import SearchStore
from tests.search_test_utils import write_search_source


def test_bundled_search_registry_is_discovered_from_one_file_per_source() -> None:
    registry = ProviderRegistry(
        search_dir=builtin_search_dir(),
        python_executable=sys.executable,
    )

    assert len(registry.names) == 24
    assert {item.source_file.name for item in registry.definitions} == {
        f"{name}.yaml" for name in registry.names
    }
    assert {
        "academic",
        "academic_openalex",
        "academic_crossref",
        "academic_arxiv",
        "academic_semantic_scholar",
        "academic_pubmed",
        "academic_google_scholar",
        "general_duckduckgo",
        "general_wikipedia",
        "github_repositories",
        "annual_report_sec",
    } <= set(
        registry.names
    )
    assert registry.configuration_environment_names == ()
    script_paths = {
        registry.script_path(definition) for definition in registry.definitions
    }
    assert len(script_paths) == len(registry.definitions)
    for definition in registry.definitions:
        script = registry.script_path(definition)
        assert script.is_file()
        assert script.is_relative_to(builtin_search_dir())


def test_adding_one_source_file_registers_a_new_provider_without_code_changes(
    tmp_path: Path,
) -> None:
    search_dir = tmp_path / "search"
    script = write_search_source(search_dir, "custom_docs")
    registry = ProviderRegistry(
        search_dir=search_dir,
        python_executable=sys.executable,
    )

    definition, command = registry.command(
        request=SearchRequest(
            provider="custom_docs",
            query="agent runtime",
            evidence_target="registration",
            intent="verify automatic discovery",
        ),
        limit=7,
    )

    assert registry.names == ("custom_docs",)
    assert definition.source_file.name == "custom_docs.yaml"
    assert command == [
        sys.executable,
        str(script.resolve()),
        "agent runtime",
        "--limit",
        "7",
    ]


def test_registry_dotenv_resolves_script_and_supplies_only_declared_source_env(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setenv(
        "DEEPRESEARCH_SEARCH_CONFIG_HOME", str(tmp_path / "empty-user-config")
    )
    search_dir = tmp_path / "search"
    external_scripts = tmp_path / "provider-scripts"
    script = external_scripts / "private_search.py"
    captured = tmp_path / "captured-provider-env.json"
    script_text = f"""\
import json
import os
from pathlib import Path

Path({str(captured)!r}).write_text(json.dumps({{
    "CUSTOM_SEARCH_TOKEN": os.environ.get("CUSTOM_SEARCH_TOKEN"),
    "UNRELATED_SECRET": os.environ.get("UNRELATED_SECRET"),
}}))

print(json.dumps({{
    "success": True,
    "items": [{{
        "title": "configured private search",
        "url": "https://example.test/custom",
        "snippet": "provider ran",
    }}],
}}))
"""
    write_search_source(
        search_dir,
        "private_search",
        script_text=script_text,
        script_path=script,
        script="${SOURCE_SCRIPT_ROOT}/private_search.py",
        required_env=["CUSTOM_SEARCH_TOKEN"],
    )
    (search_dir / ".env").write_text(
        "\n".join(
            [
                f"SOURCE_SCRIPT_ROOT={external_scripts}",
                "CUSTOM_SEARCH_TOKEN=from-search-dotenv",
                "UNRELATED_SECRET=must-not-leak",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    environment = load_search_environment(
        search_dir,
        process_environment={},
    )
    registry = ProviderRegistry(
        search_dir=search_dir,
        python_executable=sys.executable,
        environment=environment,
    )
    service = SearchService(
        registry=registry,
        store=SearchStore(tmp_path / "store"),
        provider_env={
            name: environment[name]
            for name in registry.environment_names
            if environment.get(name)
        },
    )

    result = service.batch_search(
        [
            {
                "provider": "private_search",
                "query": "private corpus",
                "evidence_target": "configuration proof",
                "intent": "verify the registry dotenv boundary",
            }
        ]
    )
    [hit] = service.search_results()["items"]

    assert result["provider_summaries"][0]["status"] == "ok"
    assert hit["title"] == "configured private search"
    assert json.loads(captured.read_text(encoding="utf-8")) == {
        "CUSTOM_SEARCH_TOKEN": "from-search-dotenv",
        "UNRELATED_SECRET": None,
    }
