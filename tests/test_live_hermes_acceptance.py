"""Opt-in smoke tests against the installed Hermes ACP runtime."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.live_hermes
LIVE = os.environ.get("DEEPRESEARCH_LIVE_HERMES") == "1"


def _run(args, cwd):
    completed = subprocess.run(
        [sys.executable, "-m", "deepresearch_cli.cli", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=float(os.environ.get("DEEPRESEARCH_LIVE_COMMAND_TIMEOUT", "1200")),
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


@pytest.mark.skipif(not LIVE, reason="set DEEPRESEARCH_LIVE_HERMES=1")
def test_real_hermes_quick_config_workflow_exports_report(tmp_path):
    args = [
        "Live config workflow smoke test",
        "--mode",
        "quick",
        "--harness",
        "hermes",
        "--runs-dir",
        str(tmp_path / "runs"),
        "--output-dir",
        str(tmp_path / "output"),
        "--progress",
        "off",
        "--json",
    ]
    profile = os.environ.get("DEEPRESEARCH_HERMES_PROFILE")
    if profile:
        args.extend(["--harness-profile", profile])

    result = _run(args, Path(__file__).resolve().parents[1])

    assert result["status"] == "completed"
    assert result["workflow"] == "quick"
    assert Path(result["result"]["path"]).is_file()
    manifest = json.loads(
        (tmp_path / "runs" / result["run_id"] / "run.json").read_text(encoding="utf-8")
    )
    assert manifest["schema_version"] == "2"
    assert manifest["runtime"] == "config-workflow"
