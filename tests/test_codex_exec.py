import asyncio
import io
import json
from pathlib import Path

from deepresearch_cli.cli import build_parser
from deepresearch_cli.harness import AgentInvocation
from deepresearch_cli.harness.codex_exec import (
    CodexBackendFactory,
    CodexExecAttemptRuntime,
)
from deepresearch_cli.harness.registry import PRODUCTION_BACKENDS, build_backend_factory
from deepresearch_cli.harness.search_mcp import SearchMcpLaunchSpec
from deepresearch_cli.progress import TerminalProgressReporter


def _write_fake_codex(path: Path, *, sleep: bool = False) -> Path:
    delay = "await asyncio.sleep(60)" if sleep else ""
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import asyncio, json, sys\n"
        "async def main():\n"
        "    if '--version' in sys.argv:\n"
        "        print('codex-cli test')\n"
        "        return\n"
        "    if 'login' in sys.argv and 'status' in sys.argv:\n"
        "        print('Logged in')\n"
        "        return\n"
        "    prompt = sys.stdin.read()\n"
        "    print(json.dumps({'type':'thread.started','thread_id':'thread-test'}), flush=True)\n"
        "    print(json.dumps({'type':'item.started','item':{'id':'tool-1','type':'command_execution','command':'inspect inputs','status':'in_progress'}}), flush=True)\n"
        f"    {delay}\n"
        "    print(json.dumps({'type':'item.completed','item':{'id':'tool-1','type':'command_execution','command':'inspect inputs','status':'completed'}}), flush=True)\n"
        "    print(json.dumps({'type':'item.completed','item':{'id':'message-1','type':'agent_message','text':'done: ' + str(bool(prompt))}}), flush=True)\n"
        "    print(json.dumps({'type':'turn.completed','usage':{'input_tokens':12,'output_tokens':3}}), flush=True)\n"
        "asyncio.run(main())\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _invocation(workspace: Path, *, timeout=5.0) -> AgentInvocation:
    workspace.mkdir(parents=True, exist_ok=True)
    return AgentInvocation(
        invocation_id="inv-codex-test",
        run_id="run-test",
        node_instance_id="research-test",
        node_type="research",
        attempt=1,
        workspace=workspace,
        input_artifact_refs=[],
        resolved_input_artifacts=[],
        timeout_seconds=timeout,
        agent_context={},
        prompt="write the declared output",
        allow_workspace_edits=True,
    )


def test_codex_backend_is_registered_and_cli_accepts_its_options(tmp_path):
    assert PRODUCTION_BACKENDS == (
        "hermes", "codex", "claude-code", "openclaw", "codex-exec"
    )
    parsed = build_parser().parse_args([
        "research", "topic", "--harness", "codex-exec",
        "--report-format", "formal_report",
        "--harness-command", str(tmp_path / "codex"),
        "--harness-profile", "research",
        "--harness-model", "test-model",
    ])
    assert parsed.harness == "codex-exec"
    assert parsed.harness_profile == "research"
    assert parsed.harness_model == "test-model"


def test_codex_factory_preflight_does_not_make_a_model_call(tmp_path):
    command = _write_fake_codex(tmp_path / "codex")
    factory = CodexBackendFactory(
        workspace=tmp_path,
        codex_command=str(command),
        search_mcp_enabled=False,
    )

    report = asyncio.run(factory.preflight())
    probe = asyncio.run(factory.probe())

    assert report["harness"] == "codex"
    assert report["version"] == "codex-cli test"
    assert report["authentication"] == "Logged in"
    assert probe == {"codex_exec": "ok", "model_check": "not_run"}


def test_codex_exec_maps_jsonl_to_the_common_result(tmp_path):
    command = _write_fake_codex(tmp_path / "codex")
    runtime = CodexExecAttemptRuntime(
        tmp_path,
        codex_command=str(command),
        search_mcp_enabled=False,
        expected_invocation_id="inv-codex-test",
    )

    async def exercise():
        await runtime.start()
        try:
            return await runtime.invoke(_invocation(tmp_path / "staging"))
        finally:
            await runtime.close()

    result = asyncio.run(exercise())

    assert result.status == "succeeded"
    assert result.response_text == "done: True"
    assert result.native_session_id == "thread-test"
    assert result.usage == {"input_tokens": 12, "output_tokens": 3}
    assert [event["type"] for event in result.events] == [
        "thread.started", "item.started", "item.completed",
        "item.completed", "turn.completed",
    ]


def test_codex_exec_uses_backend_neutral_progress_reporting(tmp_path):
    command = _write_fake_codex(tmp_path / "codex")
    stream = io.StringIO()
    runtime = CodexExecAttemptRuntime(
        tmp_path,
        codex_command=str(command),
        progress_reporter=TerminalProgressReporter(stream),
        search_mcp_enabled=False,
        expected_invocation_id="inv-codex-test",
    )

    async def exercise():
        await runtime.start()
        try:
            return await runtime.invoke(_invocation(tmp_path / "staging"))
        finally:
            await runtime.close()

    result = asyncio.run(exercise())
    output = stream.getvalue()

    assert result.status == "succeeded"
    assert "Codex started" in output
    assert "Codex returned" in output
    assert "terminal inspect inputs" in output


def test_codex_timeout_cancels_the_process(tmp_path):
    command = _write_fake_codex(tmp_path / "codex", sleep=True)
    runtime = CodexExecAttemptRuntime(
        tmp_path,
        codex_command=str(command),
        search_mcp_enabled=False,
        expected_invocation_id="inv-codex-test",
    )

    async def exercise():
        await runtime.start()
        try:
            return await runtime.invoke(_invocation(tmp_path / "staging", timeout=0.1))
        finally:
            await runtime.close()

    result = asyncio.run(exercise())

    assert result.status == "cancelled"
    assert result.stop_reason == "cancelled"
    assert "timed out" in result.error


def test_codex_direct_cancel_returns_cancelled(tmp_path):
    command = _write_fake_codex(tmp_path / "codex", sleep=True)
    runtime = CodexExecAttemptRuntime(
        tmp_path,
        codex_command=str(command),
        search_mcp_enabled=False,
        expected_invocation_id="inv-codex-test",
    )

    async def exercise():
        await runtime.start()
        task = asyncio.create_task(
            runtime.invoke(_invocation(tmp_path / "staging", timeout=None))
        )
        while runtime._process is None:
            await asyncio.sleep(0)
        await runtime.cancel("inv-codex-test")
        try:
            return await task
        finally:
            await runtime.close()

    result = asyncio.run(exercise())

    assert result.status == "cancelled"
    assert result.stop_reason == "cancelled"


def test_codex_mcp_secrets_are_forwarded_by_name_not_command_line(tmp_path):
    runtime = CodexExecAttemptRuntime(tmp_path, search_mcp_enabled=False)
    spec = SearchMcpLaunchSpec(
        name="drs_test",
        command="/usr/bin/python3",
        args=("-m", "deepresearch_cli.search.mcp_server"),
        env={"PRIVATE_SEARCH_TOKEN": "do-not-put-in-argv"},
        lease_file=tmp_path / "lease",
    )

    arguments, environment = runtime._mcp_arguments(spec)

    assert "do-not-put-in-argv" not in " ".join(arguments)
    assert "PRIVATE_SEARCH_TOKEN" in " ".join(arguments)
    assert environment["PRIVATE_SEARCH_TOKEN"] == "do-not-put-in-argv"


def test_registry_builds_codex_factory(tmp_path):
    factory = build_backend_factory(
        "codex-exec",
        workspace=tmp_path,
        command=str(tmp_path / "codex"),
        profile="research",
        model="test-model",
        search_mcp_enabled=False,
    )

    assert isinstance(factory, CodexBackendFactory)
    assert factory.profile == "research"
    assert factory.model == "test-model"
