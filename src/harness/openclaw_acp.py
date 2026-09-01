"""OpenClaw production backend using its Gateway-backed ACP server."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from acp.schema import AllowedOutcome, RequestPermissionResponse

from deepresearch_cli.progress import ProgressReporter
from deepresearch_cli.search.registry import ProviderRegistry, ProviderRegistryError, load_search_environment

from .acp.launch import AcpLaunchSpec
from .acp.client import RecordingAcpClient
from .camofox_fallback import CamofoxFallbackSupport
from .acp_agent import AcpAgentAttemptRuntime, _shielded_runtime_close
from .protocol import AgentInvocation, HarnessError
from .search_mcp import SearchMcpSupport


_SEARCH_BRIDGE_OPERATIONS = {
    "list-search-domains",
    "list-search-sources",
    "start-domain-search",
    "get-search-batch",
    "batch-search",
    "search-results",
    "get-search-hit",
    "fetch-url",
}


def _tool_call_value(tool_call: Any, name: str) -> Any:
    if isinstance(tool_call, Mapping):
        return tool_call.get(name)
    return getattr(tool_call, name, None)


class _OpenClawAcpClient(RecordingAcpClient):
    """Allow only the exact per-attempt Search bridge exec command."""

    def __init__(self, *, allowed_contexts: Mapping[str, Path], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._allowed_contexts = allowed_contexts

    def _authorized(self, tool_call: Any) -> bool:
        if _tool_call_value(tool_call, "kind") != "execute":
            return False
        raw = _tool_call_value(tool_call, "raw_input")
        if raw is None:
            raw = _tool_call_value(tool_call, "rawInput")
        command = raw.get("command") if isinstance(raw, Mapping) else None
        if not isinstance(command, str):
            return False
        if any(marker in command for marker in ("\n", "\r", ";", "|", "&", "`", "$(", ">", "<")):
            return False
        try:
            argv = shlex.split(command, posix=os.name != "nt")
        except ValueError:
            return False
        prefix = [os.path.abspath(sys.executable), "-m", "deepresearch_cli.search.tool_cli", "--context"]
        if argv[:4] != prefix or len(argv) < 6:
            return False
        try:
            supplied_context = Path(argv[4]).expanduser().resolve()
        except OSError:
            return False
        allowed = {path.resolve() for path in self._allowed_contexts.values()}
        return supplied_context in allowed and argv[5] in _SEARCH_BRIDGE_OPERATIONS

    async def request_permission(
        self,
        options: list[Any],
        session_id: str,
        tool_call: Any,
        **kwargs: Any,
    ) -> RequestPermissionResponse:
        del kwargs
        if self._authorized(tool_call):
            selected = next(
                (option for option in options if option.kind == "allow_once"), None
            )
            if selected is not None:
                return RequestPermissionResponse(
                    outcome=AllowedOutcome(
                        outcome="selected", option_id=selected.option_id
                    )
                )
        return await super().request_permission(
            options=options, session_id=session_id, tool_call=tool_call
        )


class OpenClawAcpAttemptRuntime(AcpAgentAttemptRuntime):
    """One OpenClaw ACP session, backed by an existing OpenClaw Gateway."""

    backend_name = "OpenClaw"

    def __init__(
        self,
        workspace: Path,
        *,
        openclaw_command: Optional[str] = None,
        profile: Optional[str] = None,
        model: Optional[str] = None,
        startup_timeout_seconds: float = 30.0,
        progress_reporter: Optional[ProgressReporter] = None,
        search_mcp_enabled: bool = False,
        search_dir: Optional[Path] = None,
        search_provider_python: Optional[str] = None,
        search_provider_limit: int = 20,
        search_support: Optional[SearchMcpSupport] = None,
        camofox_fallback_enabled: bool = False,
        camofox_home: Optional[Path] = None,
        camofox_base_url: Optional[str] = None,
        expected_invocation_id: Optional[str] = None,
    ) -> None:
        if model:
            raise HarnessError(
                "OpenClaw ACP does not expose a per-session model override; "
                "select the model in the OpenClaw agent configuration"
            )
        supplied = openclaw_command or shutil.which("openclaw") or "openclaw"
        resolved = shutil.which(supplied) or (
            supplied if Path(supplied).expanduser().is_file() else None
        )
        self.openclaw_command = (
            str(Path(resolved).expanduser().resolve()) if resolved else supplied
        )
        self.openclaw_profile = profile
        self._search_contexts: dict[str, Path] = {}
        super().__init__(
            workspace,
            acp_command=self.openclaw_command,
            launch_backend="openclaw",
            process_prefix="openclaw-acp-process",
            profile=None,
            startup_timeout_seconds=startup_timeout_seconds,
            progress_reporter=progress_reporter,
            search_mcp_enabled=search_mcp_enabled,
            search_dir=search_dir,
            search_provider_python=search_provider_python,
            search_provider_limit=search_provider_limit,
            search_support=search_support,
            camofox_fallback_enabled=camofox_fallback_enabled,
            camofox_home=camofox_home,
            camofox_base_url=camofox_base_url,
            expected_invocation_id=expected_invocation_id,
        )
        self._client = _OpenClawAcpClient(
            allowed_contexts=self._search_contexts,
            raw_observer_enabled=True,
            event_observer=self._observe_session_event,
        )
        self.launch_spec = AcpLaunchSpec(
            backend="openclaw",
            command=self.openclaw_command,
            cwd=self.workspace,
            environment=self._acp_environment(),
            process_prefix="openclaw-acp-process",
        )

    def _acp_args(self, *tail: str) -> tuple[str, ...]:
        return ("acp", *tail)

    def _acp_environment(self) -> dict[str, str]:
        environment = dict(os.environ)
        if self.openclaw_profile:
            environment["OPENCLAW_PROFILE"] = self.openclaw_profile
        return environment

    def _supports_session_mcp(self) -> bool:
        return False

    def _supports_session_edit_mode(self) -> bool:
        # OpenClaw owns tool policy and workspace access at the Gateway/agent
        # layer; its ACP endpoint has no portable DeepResearch edit mode.
        return False

    def _search_mcp_server(
        self,
        *,
        identity: str,
        store_dir: Path,
        batch_timeout_seconds: Optional[float] = None,
        lease_file: Optional[Path] = None,
    ) -> tuple[str, None, Path]:
        support = self.search_support or SearchMcpSupport(
            search_dir=self.search_dir,
            provider_python=self.search_provider_python,
            provider_limit=self.search_provider_limit,
            camofox_fallback_enabled=self.camofox_fallback_enabled,
            camofox_base_url=self.camofox_base_url,
        )
        spec = support.build(
            identity=identity,
            store_dir=store_dir,
            batch_timeout_seconds=batch_timeout_seconds or 120.0,
            lease_file=lease_file,
        )
        url = spec.env.get("DEEPRESEARCH_SEARCH_COORDINATOR_URL")
        token = spec.env.get("DEEPRESEARCH_SEARCH_COORDINATOR_TOKEN")
        namespace = spec.env.get("DEEPRESEARCH_SEARCH_NAMESPACE")
        if not url or not token or not namespace:
            raise HarnessError(
                "OpenClaw search requires the run-scoped Search Coordinator"
            )
        context_path = (store_dir.parent / f".{spec.name}.openclaw.json").resolve()
        payload = {
            "schema_version": 1,
            "coordinator_url": url,
            "coordinator_token": token,
            "namespace": namespace,
            "lease_file": str(spec.lease_file),
            "camofox_enabled": self.camofox_fallback_enabled,
            "camofox_base_url": self.camofox_base_url or "http://127.0.0.1:9377",
        }
        descriptor = os.open(
            context_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        try:
            os.write(descriptor, json.dumps(payload).encode("utf-8"))
        finally:
            os.close(descriptor)
        self._search_contexts[identity] = context_path
        return spec.name, None, spec.lease_file

    def _prompt_text(self, invocation: AgentInvocation) -> str:
        context = self._search_contexts.get(invocation.invocation_id)
        if context is None:
            return invocation.prompt
        base_argv = [
            os.path.abspath(sys.executable),
            "-m",
            "deepresearch_cli.search.tool_cli",
            "--context",
            str(context),
        ]
        command = (
            subprocess.list2cmdline(base_argv)
            if os.name == "nt"
            else shlex.join(base_argv)
        )
        instructions = f"""

## OpenClaw Search bridge
This Research attempt has no session-scoped MCP support. Use the native exec tool
to run the deterministic DeepResearch search bridge below. Do not use unrelated
browser/search tools. Every command emits JSON.

Base command:
`{command}`

Operations:
- `list-search-domains`
- `list-search-sources`
- `start-domain-search --searches '<JSON array>'`
- `get-search-batch <batch_id>`
- `batch-search --searches '<JSON array>'`
- `search-results --cursor 0 --limit 20 [--batch-id ID] [--provider NAME]`
- `get-search-hit <hit_id>`
- `fetch-url <public-http-url>`

Search results and snippets are discovery material. Call `fetch-url` for selected
HTML pages before treating them as evidence. If fetch reports Camofox unavailable,
switch to another source instead of retrying or blocking the workflow.
""".strip()
        return invocation.prompt + "\n\n" + instructions

    async def close(self) -> None:
        try:
            await super().close()
        finally:
            for path in self._search_contexts.values():
                with contextlib.suppress(OSError):
                    path.unlink()
            self._search_contexts.clear()


@dataclass(frozen=True)
class OpenClawAcpBackendFactory:
    workspace: Path
    openclaw_command: Optional[str] = None
    profile: Optional[str] = None
    model: Optional[str] = None
    startup_timeout_seconds: float = 30.0
    progress_reporter: Optional[ProgressReporter] = None
    search_mcp_enabled: bool = False
    search_dir: Optional[Path] = None
    search_provider_python: Optional[str] = None
    search_provider_limit: int = 20
    search_coordinator: Optional[object] = None
    camofox_fallback_enabled: bool = False
    camofox_home: Optional[Path] = None
    camofox_base_url: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "workspace", self.workspace.expanduser().resolve())

    def _runtime(self, expected_invocation_id: Optional[str] = None) -> OpenClawAcpAttemptRuntime:
        return OpenClawAcpAttemptRuntime(
            self.workspace,
            openclaw_command=self.openclaw_command,
            profile=self.profile,
            model=self.model,
            startup_timeout_seconds=self.startup_timeout_seconds,
            progress_reporter=self.progress_reporter,
            search_mcp_enabled=self.search_mcp_enabled,
            search_dir=self.search_dir,
            search_provider_python=self.search_provider_python,
            search_provider_limit=self.search_provider_limit,
            search_support=(
                SearchMcpSupport(
                    search_dir=self.search_dir,
                    provider_python=self.search_provider_python,
                    provider_limit=self.search_provider_limit,
                    coordinator=self.search_coordinator,
                    camofox_fallback_enabled=self.camofox_fallback_enabled,
                    camofox_base_url=self.camofox_base_url,
                )
                if expected_invocation_id is not None and self.search_coordinator is not None
                else None
            ),
            camofox_fallback_enabled=self.camofox_fallback_enabled,
            camofox_home=self.camofox_home,
            camofox_base_url=self.camofox_base_url,
            expected_invocation_id=expected_invocation_id,
        )

    async def _run(self, *args: str) -> tuple[int, str, str]:
        runtime = self._runtime()
        command = shutil.which(runtime.openclaw_command) or (
            runtime.openclaw_command if Path(runtime.openclaw_command).is_file() else None
        )
        if command is None:
            raise HarnessError(f"OpenClaw executable not found: {runtime.openclaw_command}")
        process = await asyncio.create_subprocess_exec(
            command,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=runtime._acp_environment(),
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
        return int(process.returncode or 0), stdout.decode(errors="replace"), stderr.decode(errors="replace")

    async def preflight(self) -> Mapping[str, Any]:
        version_code, version_out, version_err = await self._run("--version")
        if version_code:
            raise HarnessError(version_err or version_out or "openclaw --version failed")
        status_code, status_out, status_err = await self._run("status", "--json")
        if status_code:
            raise HarnessError(
                status_err or status_out or "OpenClaw Gateway status check failed"
            )
        report: dict[str, Any] = {
            "harness": "openclaw",
            "transport": "acp",
            "bridge": "openclaw-gateway",
            "version": (version_out or version_err).strip(),
            "gateway_status": (status_out or status_err).strip(),
            "profile": self.profile,
            "model": "configured-by-openclaw-agent",
            "ok": True,
        }
        if self.search_mcp_enabled:
            support = SearchMcpSupport(
                search_dir=self.search_dir,
                provider_python=self.search_provider_python,
                provider_limit=self.search_provider_limit,
            )
            search_dir = support.resolved_search_dir()
            provider_python = support.resolved_provider_python()
            registry = ProviderRegistry(
                search_dir=search_dir,
                python_executable=provider_python,
                environment=load_search_environment(search_dir),
            )
            available = 0
            for definition in registry.definitions:
                try:
                    usable = registry.script_path(definition).is_file() and not registry.missing_modules(definition)
                except ProviderRegistryError:
                    usable = False
                available += int(usable)
            if available == 0:
                raise HarnessError("no configured search provider is runtime-available")
            report.update({
                "search_mcp": "openclaw-exec-bridge",
                "search_dir": str(search_dir),
                "search_provider_python": provider_python,
                "search_route_count": len(registry.definitions),
                "search_route_available_count": available,
            })
        else:
            report["search_mcp"] = "disabled"
        report.update(CamofoxFallbackSupport(
            enabled=self.camofox_fallback_enabled,
            home=self.camofox_home,
            base_url=self.camofox_base_url,
        ).report())
        return report

    async def probe(self) -> Mapping[str, Any]:
        runtime = self._runtime()
        try:
            await runtime.start()
            return {
                "acp_initialize": "ok",
                "model_check": "not_run",
                "search_mcp": (
                    "openclaw-exec-bridge" if self.search_mcp_enabled else "disabled"
                ),
            }
        finally:
            await _shielded_runtime_close(runtime)

    def create(self, invocation: AgentInvocation) -> OpenClawAcpAttemptRuntime:
        return self._runtime(expected_invocation_id=invocation.invocation_id)
