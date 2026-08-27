import importlib.util
import sys
from pathlib import Path


def _load_provider_module():
    script_dir = (
        Path(__file__).resolve().parents[1] / "search" / "providers" / "academic"
    )
    sys.path.insert(0, str(script_dir))
    try:
        spec = importlib.util.spec_from_file_location(
            "deepresearch_test_academic_provider", script_dir / "search.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(script_dir))


def test_aggregate_provider_uses_only_declared_api_routes(monkeypatch):
    module = _load_provider_module()
    monkeypatch.setattr(
        module,
        "PROVIDERS",
        {
            "arxiv": (
                "arxiv_official",
                lambda query, limit: [{"title": query, "url": "https://arxiv.org/abs/1"}],
            ),
            "semantic": (
                "semantic_scholar_official",
                lambda query, limit: [{"title": query, "url": "https://semanticscholar.org/paper/1"}],
            ),
            "openalex": (
                "openalex_official",
                lambda query, limit: [{"title": query, "url": "https://openalex.org/W1"}],
            ),
            "pubmed": (
                "pubmed_official",
                lambda query, limit: [{"title": query, "url": "https://pubmed.ncbi.nlm.nih.gov/1/"}],
            ),
        },
    )

    result = module.search(
        "graph agents",
        sources=["arxiv", "semantic", "openalex", "pubmed"],
        limit=2,
    )

    assert result["success"] is True
    assert [item["provider"] for item in result["items"]] == [
        "arxiv_official",
        "semantic_scholar_official",
        "openalex_official",
        "pubmed_official",
    ]
    assert all(len(item["attempts"]) == 1 for item in result["source_results"])


def test_aggregate_provider_rejects_removed_legacy_routes():
    module = _load_provider_module()

    for legacy_source in ("deepxiv", "all"):
        try:
            module.search("graph agents", sources=[legacy_source])
        except ValueError as exc:
            assert "unsupported academic source" in str(exc)
        else:
            raise AssertionError(
                f"removed academic route {legacy_source!r} was unexpectedly accepted"
            )
