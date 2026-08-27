from __future__ import annotations

import json
from pathlib import Path

from deepresearch_cli.search.metrics import build_search_metrics
from deepresearch_cli.search.sqlite_store import SQLiteSearchStore


def _telemetry(event_type: str, **values):
    return {
        "event_type": event_type,
        "recorded_at": "2026-08-20T00:00:00Z",
        **values,
    }


def test_search_metrics_projects_domain_source_and_conversion_funnel(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-test"
    store = SQLiteSearchStore(run_dir / "search" / "search.sqlite3")
    store.record_telemetry(_telemetry(
        "domain_planned", batch_id="b1", namespace="d1", domain="academic",
        operation="papers", status="running", planned_sources=["arxiv", "openalex"],
    ))
    store.record_telemetry(_telemetry(
        "source_started", batch_id="b1", namespace="d1", domain="academic",
        operation="papers", provider="arxiv", pair_key="arxiv\0q", status="running",
    ))
    store.record_telemetry(_telemetry(
        "source_finished", batch_id="b1", namespace="d1", domain="academic",
        operation="papers", provider="arxiv", pair_key="arxiv\0q", status="ok",
        elapsed_seconds=2.5, raw_count=3, process_started=True,
    ))
    store.record_telemetry(_telemetry(
        "source_reused", batch_id="b1", namespace="d1", domain="academic",
        operation="papers", provider="openalex", pair_key="openalex\0q",
        status="reused_completed", raw_count=1, cache_reused=1,
    ))
    store.record_telemetry(_telemetry(
        "domain_finished", batch_id="b1", namespace="d1", domain="academic",
        operation="papers", status="succeeded",
    ))
    hit = {
        "title": "Paper", "url": "https://example.test/paper", "batch_id": "b1",
        "source_provider": "arxiv", "provider": "arxiv", "query": "q",
        "evidence_target": "target", "intent": "intent", "domain": "academic",
        "operation": "papers", "namespace": "d1", "pair_key": "arxiv\0q",
    }
    store.add_hit(hit)
    store.add_hit({**hit, "source_provider": "openalex", "provider": "openalex"})
    store.close()

    event_path = run_dir / "attempts" / "research-d1" / "attempt-1" / "acp-events.jsonl"
    event_path.parent.mkdir(parents=True)
    event_path.write_text("\n".join([
        json.dumps({"sessionUpdate": "tool_call", "toolCallId": "f1", "kind": "fetch", "title": "fetch https://example.test/paper"}),
        json.dumps({"sessionUpdate": "tool_call_update", "toolCallId": "f1", "status": "completed"}),
    ]) + "\n", encoding="utf-8")

    value = build_search_metrics(
        run_dir, evidence_urls=["https://example.test/paper#section"]
    )

    assert value["api_calls"] == 1
    assert value["cache_reused"] == 1
    assert value["funnel"] == {
        "raw": 3,
        "unique": 1,
        "fetched": 1,
        "evidence": 1,
        "rates": {"deduplicated": 33.3, "fetched": 100.0, "evidence": 100.0},
    }
    assert value["domains"] == [{
        "domain": "academic", "operations": ["papers"], "status": "done",
        "planned": 2, "completed": 2, "running": 0, "failed": 0,
        "progress_percent": 100, "raw": 3, "unique": 1,
        "api_calls": 1, "cache_reused": 1,
    }]
    arxiv = next(item for item in value["sources"] if item["provider"] == "arxiv")
    assert arxiv["calls"] == 1
    assert arxiv["average_seconds"] == 2.5
    assert arxiv["total_seconds"] == 2.5


def test_search_metrics_tolerates_run_without_search_database(tmp_path: Path) -> None:
    value = build_search_metrics(tmp_path / "run", evidence_urls=[])
    assert value["status"] == "idle"
    assert value["funnel"]["raw"] == 0
