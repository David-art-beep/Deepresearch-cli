from __future__ import annotations

import importlib.util
import sys
from types import SimpleNamespace

from deepresearch_cli.search.paths import builtin_search_dir


def _load_provider():
    providers_dir = builtin_search_dir() / "providers"
    sys.path.insert(0, str(providers_dir))
    try:
        spec = importlib.util.spec_from_file_location(
            "test_general_duckduckgo_provider",
            providers_dir / "duckduckgo.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(providers_dir))


def test_duckduckgo_provider_maps_results_and_bounds_limit(monkeypatch) -> None:
    calls: dict = {}

    class FakeDDGS:
        def __init__(self, **kwargs):
            calls["client"] = kwargs

        def text(self, **kwargs):
            calls["search"] = kwargs
            return [
                {"title": "Official report", "href": "https://example.test/report", "body": "Summary"},
                {"title": "Missing URL", "body": "ignored"},
            ]

    monkeypatch.setitem(sys.modules, "ddgs", SimpleNamespace(DDGS=FakeDDGS))
    provider = _load_provider()

    assert provider.search("test query", 100) == [
        {
            "title": "Official report",
            "url": "https://example.test/report",
            "snippet": "Summary",
        }
    ]
    assert calls == {
        "client": {"timeout": 15},
        "search": {
            "query": "test query",
            "region": "wt-wt",
            "safesearch": "moderate",
            "timelimit": None,
            "max_results": 50,
            "backend": "duckduckgo",
        },
    }
