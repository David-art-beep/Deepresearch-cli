"""Opt-in smoke test against the installed Codex CLI runtime."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.live_codex
LIVE = os.environ.get("DEEPRESEARCH_LIVE_CODEX") == "1"


@pytest.mark.skipif(not LIVE, reason="set DEEPRESEARCH_LIVE_CODEX=1")
def test_real_codex_quick_workflow_exports_report(tmp_path):
    args = [
        sys.executable, "-m", "deepresearch_cli.cli",
        "Codex Harness smoke test",
        "--mode", "quick",
        "--report-format", "formal_report",
        "--harness", "codex",
        "--runs-dir", str(tmp_path / "runs"),
        "--output-dir", str(tmp_path / "output"),
        "--progress", "off",
        "--no-search-mcp",
        "--json",
    ]
    profile = os.environ.get("DEEPRESEARCH_CODEX_PROFILE")
    if profile:
        args.extend(["--harness-profile", profile])
    model = os.environ.get("DEEPRESEARCH_CODEX_MODEL")
    if model:
        args.extend(["--harness-model", model])
    completed = subprocess.run(
        args,
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=float(os.environ.get("DEEPRESEARCH_LIVE_COMMAND_TIMEOUT", "1200")),
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == "completed"
    assert Path(result["result"]["path"]).is_file()
