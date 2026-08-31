import json
import os
from pathlib import Path

import pytest

from deepresearch_cli.search.tool_cli import _load_context, main


def _context(path: Path, lease: Path) -> Path:
    lease.write_text("active", encoding="utf-8")
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "coordinator_url": "http://127.0.0.1:1",
                "coordinator_token": "secret",
                "namespace": "attempt-1",
                "lease_file": str(lease),
            }
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


def test_search_tool_context_requires_active_lease(tmp_path: Path) -> None:
    lease = tmp_path / "attempt.lease"
    context = _context(tmp_path / "context.json", lease)
    assert _load_context(context)["namespace"] == "attempt-1"
    lease.unlink()
    with pytest.raises(RuntimeError, match="no longer active"):
        _load_context(context)


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission contract")
def test_search_tool_context_rejects_group_readable_secret(tmp_path: Path) -> None:
    context = _context(tmp_path / "context.json", tmp_path / "attempt.lease")
    context.chmod(0o644)
    with pytest.raises(RuntimeError, match="owner-only"):
        _load_context(context)


def test_search_tool_errors_do_not_print_coordinator_token(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    context = _context(tmp_path / "context.json", tmp_path / "attempt.lease")
    status = main(["--context", str(context), "list-search-domains"])
    captured = capsys.readouterr()
    assert status == 1
    assert "secret" not in captured.out
    assert "secret" not in captured.err
