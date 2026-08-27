import errno
import json
import os

import pytest

from deepresearch_cli.search.store import (
    MAX_SEARCH_HIT_BYTES,
    MAX_SEARCH_RESULTS_BYTES,
    SearchStore,
    SearchStoreError,
)


def _hit(
    *,
    provider: str = "hackernews",
    query: str = "graph research",
    batch_id: str = "batch-1",
    target: str = "architecture",
    url: str = "https://example.test/shared",
    title: str = "Shared candidate",
    metadata=None,
):
    return {
        "batch_id": batch_id,
        "source_provider": provider,
        "provider": provider,
        "query": query,
        "evidence_target": target,
        "intent": "discover relevant source material",
        "title": title,
        "url": url,
        "snippet": "candidate snippet",
        "metadata": metadata or {},
        "raw_item": {"url": url, "title": title},
        "raw_item_truncated": False,
    }


def _encoded_size(value) -> int:
    return len(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


def test_duplicate_canonical_hit_keeps_each_discovery_and_provenance(tmp_path):
    store = SearchStore(tmp_path / "store")

    first_id, first_added = store.add_hit(_hit())
    second_id, second_added = store.add_hit(
        _hit(
            provider="reddit",
            batch_id="batch-2",
            target="user experience",
            title="Reddit-specific representation",
        )
    )

    assert first_added is True
    assert second_added is False
    assert first_id == second_id

    page = store.search_results(limit=10)
    assert page["total"] == 2
    assert page["unique_hit_count"] == 1
    assert {item["hit_id"] for item in page["items"]} == {first_id}
    assert len({item["discovery_id"] for item in page["items"]}) == 2
    assert store.search_results(provider="reddit")["total"] == 1
    assert store.search_results(batch_id="batch-1")["total"] == 1

    detail = store.get_search_hit(first_id)
    assert detail["discovery_count"] == 2
    assert detail["provenance_returned"] == 2
    assert detail["provenance_truncated"] is False
    assert {item["source_provider"] for item in detail["provenance"]} == {
        "hackernews",
        "reddit",
    }
    assert _encoded_size(detail) <= MAX_SEARCH_HIT_BYTES

    reddit_occurrence = next(
        item for item in page["items"] if item["source_provider"] == "reddit"
    )
    reddit_detail = store.get_search_hit(reddit_occurrence["discovery_id"])
    assert reddit_detail["selected_discovery_id"] == reddit_occurrence["discovery_id"]
    assert reddit_detail["source_provider"] == "reddit"
    assert reddit_detail["raw_item"]["title"] == "Reddit-specific representation"


def test_restart_rebuilds_discovery_alias_and_pair_indexes(tmp_path):
    root = tmp_path / "store"
    store = SearchStore(root)
    hit_id, _ = store.add_hit(_hit())
    # A duplicate can contribute a stronger identifier. Its dedupe alias and
    # occurrence both need to survive restart.
    store.add_hit(
        {
            **_hit(batch_id="batch-2"),
            "metadata": {"doi": "10.1000/example"},
        }
    )
    pair_key = "hackernews\u0000graph research"

    reopened = SearchStore(root)

    assert reopened.search_results()["total"] == 2
    assert reopened.get_search_hit(hit_id)["discovery_count"] == 2
    replay = reopened.hits_for_pair(pair_key)
    assert len(replay) == 1
    assert replay[0]["hit_id"] == hit_id
    # A DOI-only form now resolves to the pre-existing canonical hit.
    alias_id, added = reopened.add_hit(
        {
            **_hit(url="", title="Alternate title", batch_id="batch-3"),
            "metadata": {"doi": "10.1000/example"},
        }
    )
    assert (alias_id, added) == (hit_id, False)


def test_hits_for_pair_deduplicates_repeated_targets_by_canonical_id(tmp_path):
    store = SearchStore(tmp_path / "store")
    store.add_hit(_hit(target="target A", batch_id="batch-a"))
    store.add_hit(_hit(target="target B", batch_id="batch-b"))

    values = store.hits_for_pair("hackernews\u0000graph research")

    assert len(values) == 1
    assert values[0]["evidence_target"] == "target A"
    assert values[0]["raw_item"]["title"] == "Shared candidate"


def test_only_ok_and_empty_requests_mark_pair_complete(tmp_path):
    root = tmp_path / "store"
    pair_key = "hackernews\u0000retry me"
    store = SearchStore(root)

    for status in ("failed", "partial", "timed_out", "unavailable"):
        store.record_request({"pair_key": pair_key, "status": status})
        assert store.has_pair(pair_key) is False
    store.record_request(
        {"pair_key": pair_key, "status": "ok", "batch_id": "successful"}
    )
    assert store.has_pair(pair_key) is True
    assert store.existing_request(pair_key)["batch_id"] == "successful"

    reopened = SearchStore(root)
    assert reopened.has_pair(pair_key) is True
    assert reopened.existing_request(pair_key)["status"] == "ok"


def test_jsonl_reader_ignores_only_invalid_unterminated_tail(tmp_path):
    root = tmp_path / "recoverable"
    root.mkdir()
    requests = root / "requests.jsonl"
    requests.write_bytes(
        b'{"pair_key":"p","status":"ok"}\n{"pair_key":'
    )

    store = SearchStore(root)

    assert store.has_pair("p") is True
    store.record_request({"pair_key": "q", "status": "ok"})
    reopened = SearchStore(root)
    assert reopened.has_pair("p") is True
    assert reopened.has_pair("q") is True

    valid_unterminated_root = tmp_path / "valid-unterminated"
    valid_unterminated_root.mkdir()
    valid_requests = valid_unterminated_root / "requests.jsonl"
    valid_requests.write_bytes(b'{"pair_key":"p","status":"ok"}')
    valid_store = SearchStore(valid_unterminated_root)
    valid_store.record_request({"pair_key": "q", "status": "ok"})
    valid_reopened = SearchStore(valid_unterminated_root)
    assert valid_reopened.has_pair("p") is True
    assert valid_reopened.has_pair("q") is True

    corrupt_root = tmp_path / "corrupt"
    corrupt_root.mkdir()
    (corrupt_root / "requests.jsonl").write_bytes(
        b'{"pair_key":"p","status":"ok"}\nnot-json\n'
        b'{"pair_key":"q","status":"ok"}\n'
    )
    with pytest.raises(SearchStoreError, match=r"requests\.jsonl:2"):
        SearchStore(corrupt_root)

    committed_bad_root = tmp_path / "committed-bad-tail"
    committed_bad_root.mkdir()
    (committed_bad_root / "requests.jsonl").write_bytes(b"not-json\n")
    with pytest.raises(SearchStoreError, match=r"requests\.jsonl:1"):
        SearchStore(committed_bad_root)


def test_append_retries_short_writes_and_propagates_disk_errors(
    tmp_path, monkeypatch
):
    root = tmp_path / "short-writes"
    store = SearchStore(root)
    real_write = os.write

    def short_write(descriptor, payload):
        return real_write(descriptor, payload[:7])

    monkeypatch.setattr(os, "write", short_write)
    store.add_hit(_hit())
    assert SearchStore(root).search_results()["total"] == 1

    failing = SearchStore(tmp_path / "disk-full")

    def disk_full(_descriptor, _payload):
        raise OSError(errno.ENOSPC, "no space left on device")

    monkeypatch.setattr(os, "write", disk_full)
    with pytest.raises(SearchStoreError, match="cannot append"):
        failing.add_hit(_hit())


def test_partial_append_is_rolled_back_before_a_later_success(
    tmp_path, monkeypatch
):
    root = tmp_path / "partial-disk-full"
    store = SearchStore(root)
    real_write = os.write
    calls = 0

    def partial_then_full(_descriptor, payload):
        nonlocal calls
        calls += 1
        if calls == 1:
            return real_write(_descriptor, payload[:7])
        raise OSError(errno.ENOSPC, "no space left on device")

    monkeypatch.setattr(os, "write", partial_then_full)
    with pytest.raises(SearchStoreError, match="cannot append"):
        store.record_request({"pair_key": "broken", "status": "ok"})

    monkeypatch.setattr(os, "write", real_write)
    store.record_request({"pair_key": "healthy", "status": "ok"})

    reopened = SearchStore(root)
    assert reopened.has_pair("broken") is False
    assert reopened.has_pair("healthy") is True


def test_search_pages_are_byte_bounded_without_hiding_discoveries(tmp_path):
    store = SearchStore(tmp_path / "store")
    huge_metadata = {
        f"field-{index}": "研究资料" * 2_000 for index in range(40)
    }
    for index in range(50):
        store.add_hit(
            _hit(
                url=f"https://example.test/{index}",
                title=f"Candidate {index}",
                metadata=huge_metadata,
            )
        )

    seen: set[str] = set()
    cursor = 0
    saw_transport_truncation = False
    while True:
        page = store.search_results(cursor=cursor, limit=50)
        assert _encoded_size(page) <= MAX_SEARCH_RESULTS_BYTES
        seen.update(item["discovery_id"] for item in page["items"])
        saw_transport_truncation = saw_transport_truncation or any(
            item["metadata"].get("_truncated_for_transport") is True
            for item in page["items"]
        )
        if page["next_cursor"] is None:
            break
        assert page["items"]
        cursor = page["next_cursor"]

    assert len(seen) == 50
    assert saw_transport_truncation is True
