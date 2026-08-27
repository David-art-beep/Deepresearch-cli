import io
import json

from deepresearch_cli.cli import _emit
from deepresearch_cli.harness import AgentInvocation
from deepresearch_cli.progress import TerminalProgressReporter


def _invocation(tmp_path):
    return AgentInvocation(
        invocation_id="inv-progress",
        run_id="run-progress",
        node_instance_id="research-d1",
        node_type="Research",
        attempt=2,
        workspace=tmp_path,
        input_artifact_refs=[],
        resolved_input_artifacts=[],
        timeout_seconds=30,
        agent_context={"dimension_id": "d1"},
        prompt="test",
    )


def test_terminal_progress_correlates_tool_updates_without_printing_content(tmp_path):
    stream = io.StringIO()
    reporter = TerminalProgressReporter(stream=stream)
    invocation = _invocation(tmp_path)

    reporter.invocation_started(invocation)
    reporter.acp_event(
        invocation,
        {
            "sessionUpdate": "tool_call",
            "toolCallId": "tool-1",
            "kind": "fetch",
            "title": "web search:\nPython 3.14 release date",
            "content": [{"text": "SECRET START BODY"}],
        },
    )
    reporter.acp_event(
        invocation,
        {
            "sessionUpdate": "tool_call_update",
            "toolCallId": "tool-1",
            "status": "completed",
            "content": [{"text": "SECRET RESULT BODY"}],
        },
    )
    reporter.acp_event(
        invocation,
        {
            "sessionUpdate": "agent_message_chunk",
            "content": {"type": "text", "text": "SECRET AGENT MESSAGE"},
        },
    )
    reporter.invocation_finished(invocation, "succeeded")

    output = stream.getvalue()
    assert "[Research:d1#2] Hermes started" in output
    assert "→ fetch web search: Python 3.14 release date" in output
    assert "✓ fetch completed · web search: Python 3.14 release date" in output
    assert "[Research:d1#2] Hermes returned" in output
    assert "SECRET" not in output


def test_terminal_progress_separates_harness_return_from_node_validation(tmp_path):
    stream = io.StringIO()
    reporter = TerminalProgressReporter(stream=stream)
    invocation = _invocation(tmp_path)

    reporter.invocation_started(invocation)
    reporter.invocation_finished(invocation, "succeeded")
    reporter.node_attempt_finished(
        "Research",
        {"dimension_id": "d1"},
        2,
        "repairable",
        "Artifact validation failed: V003 headline is missing",
    )

    output = stream.getvalue()
    assert "[Research:d1#2] Hermes returned" in output
    assert "[Research:d1#2] Node needs artifact repair" in output
    assert "V003" in output
    assert "Node succeeded" not in output


def test_terminal_progress_reports_validation_warning_before_success(tmp_path):
    stream = io.StringIO()
    reporter = TerminalProgressReporter(stream=stream)

    reporter.validation_warning(
        "Research",
        {"dimension_id": "d1"},
        1,
        {
            "rule": "V040",
            "severity": "warning",
            "message": "factual claim has only tertiary evidence",
        },
    )
    reporter.node_attempt_finished(
        "Research", {"dimension_id": "d1"}, 1, "succeeded", None
    )

    output = stream.getvalue()
    assert "Validation warning V040" in output
    assert "only tertiary evidence" in output
    assert "Node succeeded" in output


def test_terminal_progress_does_not_repeat_kind_prefix(tmp_path):
    stream = io.StringIO()
    reporter = TerminalProgressReporter(stream=stream)
    invocation = _invocation(tmp_path)

    reporter.acp_event(
        invocation,
        {
            "sessionUpdate": "tool_call",
            "toolCallId": "tool-read",
            "kind": "read",
            "title": "read: sub_reports/d1.evidence.json",
        },
    )

    assert "→ read sub_reports/d1.evidence.json" in stream.getvalue()
    assert "read read:" not in stream.getvalue()


def test_terminal_progress_handles_failed_update_without_a_start_event(tmp_path):
    stream = io.StringIO()
    reporter = TerminalProgressReporter(stream=stream)
    invocation = _invocation(tmp_path)

    reporter.acp_event(
        invocation,
        {
            "sessionUpdate": "tool_call_update",
            "toolCallId": "unknown",
            "kind": "execute",
            "status": "failed",
        },
    )

    assert "✗ execute failed" in stream.getvalue()


def test_progress_stays_on_stderr_while_json_stays_parseable_on_stdout(
    tmp_path, capsys
):
    reporter = TerminalProgressReporter()
    reporter.invocation_started(_invocation(tmp_path))
    _emit({"ok": True}, as_json=True)

    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"ok": True}
    assert "Hermes started" in captured.err
    assert "Hermes started" not in captured.out


def test_terminal_progress_renders_and_deduplicates_heavy_snapshot():
    stream = io.StringIO()
    reporter = TerminalProgressReporter(stream=stream)
    snapshot = {
        "percent": 63,
        "phase": "report-writer",
        "phase_label": "分章节写作",
        "completed_units": 3,
        "total_units": 7,
        "active_items": ["u4", "u5"],
    }

    reporter.workflow_progress(snapshot)
    reporter.workflow_progress(snapshot)

    output = stream.getvalue()
    assert output.count("[heavy]") == 1
    assert "63% · 分章节写作 3/7" in output
    assert "正在处理 u4, u5" in output


def test_plain_summary_prints_the_exported_result_path(capsys):
    _emit(
        {
            "run_id": "run-warning",
            "run_dir": "/tmp/run-warning",
            "status": "completed",
            "completed_nodes": ["Research", "ReportWriter", "Render"],
            "ready_nodes": [],
            "failed_nodes": [],
            "unexecuted_nodes": [],
            "artifact_count": 3,
            "result": {
                "type": "report",
                "path": "/tmp/output/run-warning/report.md",
                "artifact_ref": {
                    "path": "artifacts/render-1/attempt-1/report.md",
                    "sha256": "sha256:" + "0" * 64,
                    "media_type": "text/markdown",
                },
            },
            "validation_warning_count": 1,
            "validation_warnings": [
                {
                    "node_id": "Research",
                    "scope": {"dimension_id": "d1"},
                    "rule": "V040",
                    "message": "factual claim has only tertiary evidence",
                }
            ],
        },
        as_json=False,
    )

    output = capsys.readouterr().out
    assert "status: completed" in output
    assert "result_type: report" in output
    assert "result_path: /tmp/output/run-warning/report.md" in output
