"""Opt-in smoke test against an installed OpenClaw Gateway ACP endpoint."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.live_openclaw
LIVE = os.environ.get("DEEPRESEARCH_LIVE_OPENCLAW") == "1"


@pytest.mark.skipif(not LIVE, reason="set DEEPRESEARCH_LIVE_OPENCLAW=1")
def test_real_openclaw_quick_workflow_exports_report(tmp_path: Path) -> None:
    args = [
        sys.executable,
        "-m",
        "deepresearch_cli.cli",
        "OpenClaw ACP Harness smoke test",
        "--mode",
        "quick",
        "--report-format",
        "formal_report",
        "--harness",
        "openclaw",
        "--runs-dir",
        str(tmp_path / "runs"),
        "--output-dir",
        str(tmp_path / "output"),
        "--progress",
        "off",
        "--no-search-mcp",
        "--json",
    ]
    command = os.environ.get("DEEPRESEARCH_OPENCLAW_COMMAND")
    if command:
        args.extend(["--harness-command", command])
    profile = os.environ.get("DEEPRESEARCH_OPENCLAW_PROFILE")
    if profile:
        args.extend(["--harness-profile", profile])
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
