from __future__ import annotations

import asyncio
import os
import re
import shutil
import sys
from types import SimpleNamespace

import pytest

from deepresearch_cli.harness import AgentInvocation
from deepresearch_cli.harness.hermes_acp import HermesAcpAttemptRuntime
from deepresearch_cli.harness.protocol import HarnessError
from tests.search_test_utils import write_search_source


_SEARCH_TOOL_NAMES = (
    "list_search_domains",
    "start_domain_search",
    "get_search_batch",
    "list_search_sources",
    "batch_search",
    "search_results",
    "get_search_hit",
    "fetch_url",
)


def _invocation(workspace, *, timeout_seconds=20.0):
    return AgentInvocation(
        invocation_id="research-with-an-arbitrarily-long-instance-identity-" + "x" * 100,
        run_id="run-search-edge",
        node_instance_id="research-edge",
        node_type="research",
        attempt=1,
        workspace=workspace,
        input_artifact_refs=[],
        resolved_input_artifacts=[],
        timeout_seconds=timeout_seconds,
        agent_context={"query": "test", "language": "en"},
        prompt="research",
    )


def _tool_listing(harness, session_id, server_name):
    harness._client.messages[session_id].append(
        "\n".join(
            f"mcp__{server_name}__{tool}" for tool in _SEARCH_TOOL_NAMES
        )
    )


def test_search_tool_probe_accepts_v019_deferred_native_registration(tmp_path):
    async def exercise():
        harness = HermesAcpAttemptRuntime(tmp_path)
        server_name = "drs_0123456789abcdef0123"

        class Connection:
            async def prompt(self, **kwargs):
                # Hermes v0.19.1 /tools can omit dynamically registered tools
                # when tool_search defers them.
                return SimpleNamespace(stop_reason="end_turn", usage=None)

        harness._connection = Connection()
        harness._append_stderr(
            f"MCP server '{server_name}' (stdio): registered 8 tool(s): "
            + ", ".join(
                f"mcp__{server_name}__{tool}" for tool in _SEARCH_TOOL_NAMES
            )
        )
        tools = await harness._verify_search_tools(
            session_id="deferred-session",
            server_name=server_name,
            timeout_seconds=1.0,
        )
        assert tools == [
            f"mcp__{server_name}__{tool}" for tool in _SEARCH_TOOL_NAMES
        ]

    asyncio.run(exercise())


def test_search_tool_probe_rejects_incomplete_native_registration(tmp_path):
    async def exercise():
        harness = HermesAcpAttemptRuntime(tmp_path)
        server_name = "drs_0123456789abcdef0123"

        class Connection:
            async def prompt(self, **kwargs):
                return SimpleNamespace(stop_reason="end_turn", usage=None)

        harness._connection = Connection()
        harness._append_stderr(
            f"MCP server '{server_name}' (stdio): registered 1 tool(s): "
            f"mcp__{server_name}__list_search_sources"
        )
        with pytest.raises(HarnessError, match="did not register"):
            await harness._verify_search_tools(
                session_id="incomplete-session",
                server_name=server_name,
                timeout_seconds=1.0,
            )

    asyncio.run(exercise())


def test_search_server_names_are_short_random_and_keep_tools_under_64():
    names = {
        HermesAcpAttemptRuntime._safe_search_server_name("identity-" + "x" * 500)
        for _ in range(64)
    }

    assert len(names) == 64
    assert all(re.fullmatch(r"drs_[0-9a-f]{20}", name) for name in names)
    assert all(
        len(f"mcp__{name}__{tool}") <= 64
        for name in names
        for tool in _SEARCH_TOOL_NAMES
    )


def test_profile_home_matches_hermes_v019_profile_resolution(tmp_path, monkeypatch):
    root = tmp_path / "custom-hermes-root"
    named_home = root / "profiles" / "already-selected"

    monkeypatch.setenv("HERMES_HOME", str(named_home))
    assert HermesAcpAttemptRuntime(tmp_path, profile="default")._hermes_profile_home() == root
    assert (
        HermesAcpAttemptRuntime(tmp_path, profile="Research-Team")._hermes_profile_home()
        == root / "profiles" / "research-team"
    )
    assert HermesAcpAttemptRuntime(tmp_path)._hermes_profile_home() == named_home

    monkeypatch.setenv("HERMES_HOME", str(root))
    root.mkdir(parents=True)
    (root / "active_profile").write_text("BatchTest\n", encoding="utf-8")
    assert (
        HermesAcpAttemptRuntime(tmp_path)._hermes_profile_home()
        == root / "profiles" / "batchtest"
    )

    (root / "active_profile").write_text("default\n", encoding="utf-8")
    assert HermesAcpAttemptRuntime(tmp_path)._hermes_profile_home() == root


def test_search_preflight_rejects_non_python_executable(tmp_path):
    async def exercise():
        search_dir = tmp_path / "search"
        write_search_source(search_dir, "hackernews")
        harness = HermesAcpAttemptRuntime(
            tmp_path,
            hermes_command=shutil.which("true"),
            search_mcp_enabled=True,
            search_dir=search_dir,
            search_provider_python=shutil.which("false"),
        )
        with pytest.raises(
            HarnessError,
            match="search provider Python executable check failed",
        ):
            await harness.preflight()

    asyncio.run(exercise())


def test_search_preflight_reports_every_configured_source(tmp_path):
    async def exercise():
        search_dir = tmp_path / "search"
        write_search_source(
            search_dir,
            "hackernews",
            required_modules=[],
        )
        harness = HermesAcpAttemptRuntime(
            tmp_path,
            hermes_command=shutil.which("true"),
            search_mcp_enabled=True,
            search_dir=search_dir,
            search_provider_python=sys.executable,
        )

        report = await harness.preflight()

        assert report["search_provider_python_check"] == "ok"
        assert report["search_route_count"] == 1
        assert len(report["search_routes"]) == 1
        assert report["search_route_available_count"] == 1
        assert report["search_route_unavailable_count"] == 0
        route = next(
            item
            for item in report["search_routes"]
            if item["provider"] == "hackernews"
        )
        assert route == {
            "provider": "hackernews",
            "source_file": "hackernews.yaml",
            "script": "scripts/hackernews.py",
            "script_available": True,
            "required_modules": [],
            "missing_modules": [],
            "runtime_available": True,
            "unavailable_reason": None,
        }

    asyncio.run(exercise())


def test_search_preflight_requires_one_runtime_available_route(tmp_path):
    async def exercise():
        search_dir = tmp_path / "search"
        missing_script = write_search_source(search_dir, "hackernews")
        missing_script.unlink()
        harness = HermesAcpAttemptRuntime(
            tmp_path,
            hermes_command=shutil.which("true"),
            search_mcp_enabled=True,
            search_dir=search_dir,
            search_provider_python=sys.executable,
        )
        with pytest.raises(
            HarnessError,
            match="none of the 1 configured search sources is runtime-available",
        ):
            await harness.preflight()

    asyncio.run(exercise())


def test_research_descriptor_uses_remaining_budget_and_cleans_lease(tmp_path):
    async def exercise():
        search_dir = tmp_path / "search"
        write_search_source(search_dir, "hackernews")
        staging = tmp_path / "run" / "attempts" / "research" / "staging"
        staging.mkdir(parents=True)
        harness = HermesAcpAttemptRuntime(
            tmp_path,
            search_mcp_enabled=True,
            search_dir=search_dir,
        )

        class Connection:
            descriptor = None
            lease_file = None

            async def new_session(self, **kwargs):
                self.descriptor = kwargs["mcp_servers"][0]
                environment = {
                    item.name: item.value for item in self.descriptor.env
                }
                self.lease_file = environment["DEEPRESEARCH_SEARCH_LEASE_FILE"]
                assert os.path.isfile(self.lease_file)
                timeout = float(
                    environment["DEEPRESEARCH_SEARCH_BATCH_TIMEOUT_SECONDS"]
                )
                assert 1.0 <= timeout < 20.0
                harness._append_stderr(
                    f"MCP server '{self.descriptor.name}' (stdio): registered "
                    "8 tool(s): "
                    + ", ".join(
                        f"mcp__{self.descriptor.name}__{tool}"
                        for tool in _SEARCH_TOOL_NAMES
                    )
                )
                return SimpleNamespace(session_id="session-search-budget")

            async def prompt(self, **kwargs):
                assert kwargs["prompt"][0].text == "research"
                harness._client.messages[kwargs["session_id"]].append("done")
                return SimpleNamespace(stop_reason="end_turn", usage=None)

        connection = Connection()
        harness._started = True
        harness._connection = connection
        harness._process_instance_id = "hermes-process-search-budget"

        result = await harness.invoke(_invocation(staging))

        assert result.status == "succeeded"
        assert connection.lease_file is not None
        assert not os.path.exists(connection.lease_file)

    asyncio.run(exercise())


def test_doctor_probe_creates_default_budget_lease_then_removes_it(tmp_path):
    async def exercise():
        search_dir = tmp_path / "search"
        write_search_source(search_dir, "hackernews")
        harness = HermesAcpAttemptRuntime(
            tmp_path,
            search_mcp_enabled=True,
            search_dir=search_dir,
        )

        class Connection:
            descriptor = None
            lease_file = None

            async def new_session(self, **kwargs):
                self.descriptor = kwargs["mcp_servers"][0]
                environment = {
                    item.name: item.value for item in self.descriptor.env
                }
                self.lease_file = environment["DEEPRESEARCH_SEARCH_LEASE_FILE"]
                assert os.path.isfile(self.lease_file)
                assert (
                    float(environment["DEEPRESEARCH_SEARCH_BATCH_TIMEOUT_SECONDS"])
                    == 120.0
                )
                return SimpleNamespace(session_id="session-search-probe")

            async def prompt(self, **kwargs):
                _tool_listing(
                    harness,
                    kwargs["session_id"],
                    self.descriptor.name,
                )
                return SimpleNamespace(stop_reason="end_turn", usage=None)

        connection = Connection()
        harness._started = True
        harness._connection = connection

        report = await harness.check_search_mcp()

        assert report["search_mcp"] == "ok"
        assert connection.lease_file is not None
        assert not os.path.exists(connection.lease_file)

    asyncio.run(exercise())


def test_direct_cancel_removes_search_lease_before_acp_cancel(tmp_path):
    async def exercise():
        lease_file = tmp_path / "search.lease"
        lease_file.write_text("active\n", encoding="utf-8")
        harness = HermesAcpAttemptRuntime(tmp_path)

        class Connection:
            cancelled_session = None

            async def cancel(self, *, session_id):
                assert not lease_file.exists()
                self.cancelled_session = session_id

        connection = Connection()
        harness._connection = connection
        harness._active_sessions["invocation"] = "session"
        harness._search_lease_files["invocation"] = lease_file

        await harness.cancel("invocation")

        assert connection.cancelled_session == "session"
        assert "invocation" not in harness._search_lease_files

    asyncio.run(exercise())
