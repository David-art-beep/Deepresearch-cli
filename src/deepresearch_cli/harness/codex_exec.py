"""Codex CLI backend using the official non-interactive JSONL interface."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shutil
import signal
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from deepresearch_cli.progress import ProgressReporter
from deepresearch_cli.search.registry import ProviderRegistry, ProviderRegistryError, load_search_environment

from .protocol import AgentExecutionResult, AgentInvocation, HarnessError
from .camofox_fallback import CamofoxFallbackSupport
from .search_mcp import SearchMcpLaunchSpec, SearchMcpSupport


_CODEX_JSONL_STREAM_LIMIT_BYTES = 16_000_000

def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _toml_array(values: list[str] | tuple[str, ...]) -> str:
    return "[" + ",".join(_toml_string(item) for item in values) + "]"


def _event_projection(event: Mapping[str, Any]) -> Optional[dict[str, Any]]:
    event_type = event.get("type")
    if event_type not in {"item.started", "item.completed"}:
        return None
    item = event.get("item")
    if not isinstance(item, Mapping):
        return None
    item_type = str(item.get("type") or "tool")
    if item_type == "agent_message":
        return None
    identifier = str(item.get("id") or uuid.uuid4().hex)
    kind = {
        "command_execution": "terminal",
        "file_change": "edit",
        "mcp_tool_call": "mcp",
        "web_search": "search",
    }.get(item_type, item_type)
    title = (
        item.get("command")
        or item.get("tool")
        or item.get("query")
        or item.get("path")
        or kind
    )
    if event_type == "item.started":
        return {
            "sessionUpdate": "tool_call",
            "toolCallId": identifier,
            "kind": kind,
            "title": str(title),
            "status": "in_progress",
        }
    status = str(item.get("status") or "completed")
    if status not in {"completed", "failed", "cancelled", "rejected"}:
        status = "completed"
    return {
        "sessionUpdate": "tool_call_update",
        "toolCallId": identifier,
        "kind": kind,
        "title": str(title),
        "status": status,
    }


class CodexExecAttemptRuntime:
    """One disposable ``codex exec`` process for one Agent attempt."""

    def __init__(
        self,
        workspace: Path,
        *,
        codex_command: Optional[str] = None,
        profile: Optional[str] = None,
        model: Optional[str] = None,
        progress_reporter: Optional[ProgressReporter] = None,
        search_mcp_enabled: bool = False,
        search_support: Optional[SearchMcpSupport] = None,
        camofox_fallback_enabled: bool = False,
        camofox_home: Optional[Path] = None,
        camofox_base_url: Optional[str] = None,
        expected_invocation_id: Optional[str] = None,
    ) -> None:
        self.workspace = workspace.expanduser().resolve()
        supplied = codex_command or shutil.which("codex") or "codex"
        self.codex_command = shutil.which(supplied) or supplied
        self.profile = profile
        self.model = model
        self.progress_reporter = progress_reporter
        self.search_mcp_enabled = search_mcp_enabled
        self.search_support = search_support or SearchMcpSupport(
            camofox_fallback_enabled=camofox_fallback_enabled,
            camofox_base_url=camofox_base_url,
        )
        self.camofox_support = CamofoxFallbackSupport(
            enabled=camofox_fallback_enabled,
            home=camofox_home,
            base_url=camofox_base_url,
        )
        self.expected_invocation_id = expected_invocation_id
        self._process: Optional[asyncio.subprocess.Process] = None
        self._process_instance_id: Optional[str] = None
        self._active_invocation_id: Optional[str] = None
        self._lease_file: Optional[Path] = None
        self._cancel_requested = False
        self._started = False
        self._closed = False

    async def start(self) -> None:
        if self._closed:
            raise HarnessError("Codex attempt runtime has already been closed")
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._process_instance_id = "codex-process-" + uuid.uuid4().hex
        self._started = True

    def _mcp_arguments(self, specs: Sequence[Any]) -> tuple[list[str], dict[str, str]]:
        # Keep the private helper compatible with embedders/tests that pass the
        # historical single SearchMcpLaunchSpec value.
        if isinstance(specs, SearchMcpLaunchSpec):
            specs = (specs,)
        arguments: list[str] = []
        all_names: set[str] = set()
        environment = dict(os.environ)
        for spec in specs:
            prefix = f"mcp_servers.{spec.name}"
            names = sorted(spec.env)
            all_names.update(names)
            arguments.extend([
                "-c", f"{prefix}.command={_toml_string(spec.command)}",
                "-c", f"{prefix}.args={_toml_array(spec.args)}",
                "-c", f"{prefix}.env_vars={_toml_array(names)}",
                "-c", f"{prefix}.required={'true' if isinstance(spec, SearchMcpLaunchSpec) else 'false'}",
                "-c", f"{prefix}.startup_timeout_sec=20",
                "-c", f"{prefix}.tool_timeout_sec=180",
            ])
            environment.update(spec.env)
        if specs:
            arguments.extend([
                "-c", "shell_environment_policy.inherit=all",
                "-c", f"shell_environment_policy.exclude={_toml_array(sorted(all_names))}",
            ])
        return arguments, environment

    def _command(self, invocation: AgentInvocation, specs: Sequence[Any]) -> tuple[list[str], dict[str, str]]:
        command = [self.codex_command]
        if self.profile:
            command.extend(["--profile", self.profile])
        if self.model:
            command.extend(["--model", self.model])
        command.extend(["--ask-for-approval", "never", "exec"])
        if not self.profile:
            command.append("--ignore-user-config")
        command.extend([
            "--ignore-rules",
            "--json",
            "--ephemeral",
            "--skip-git-repo-check",
            "--sandbox", "workspace-write" if invocation.allow_workspace_edits else "read-only",
            "--color", "never",
            "-C", str(invocation.workspace),
        ])
        environment = dict(os.environ)
        if specs:
            arguments, environment = self._mcp_arguments(specs)
            command.extend(arguments)
        command.append("-")
        return command, environment

    async def invoke(self, invocation: AgentInvocation) -> AgentExecutionResult:
        if not self._started or self._closed:
            raise HarnessError("Codex attempt runtime has not been started")
        if self._active_invocation_id is not None:
            raise HarnessError("one Codex attempt runtime cannot serve multiple invocations")
        if self.expected_invocation_id and invocation.invocation_id != self.expected_invocation_id:
            raise HarnessError("Codex attempt runtime received an unexpected invocation id")
        self._active_invocation_id = invocation.invocation_id
        self._notify_started(invocation)
        specs: list[Any] = []
        if self.search_mcp_enabled and invocation.node_type == "research":
            search_spec = self.search_support.build(
                identity=invocation.invocation_id,
                store_dir=invocation.workspace.parent / "search",
                batch_timeout_seconds=min(invocation.timeout_seconds or 120.0, 120.0),
            )
            specs.append(search_spec)
            self._lease_file = search_spec.lease_file
        command, environment = self._command(invocation, specs)
        events: list[dict[str, Any]] = []
        messages: list[str] = []
        stderr_chunks: list[str] = []
        session_id: Optional[str] = None
        usage: Optional[dict[str, Any]] = None
        turn_error: Optional[str] = None
        outcome = "failed"
        try:
            self._process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=invocation.workspace,
                env=environment,
                start_new_session=True,
                limit=_CODEX_JSONL_STREAM_LIMIT_BYTES,
            )
            assert self._process.stdin is not None
            self._process.stdin.write(invocation.prompt.encode("utf-8"))
            await self._process.stdin.drain()
            self._process.stdin.close()

            async def read_stdout() -> None:
                nonlocal session_id, usage, turn_error
                assert self._process is not None and self._process.stdout is not None
                while True:
                    line = await self._process.stdout.readline()
                    if not line:
                        return
                    try:
                        event = json.loads(line.decode("utf-8"))
                    except (UnicodeError, json.JSONDecodeError):
                        continue
                    if not isinstance(event, dict):
                        continue
                    events.append(event)
                    if event.get("type") == "thread.started" and isinstance(event.get("thread_id"), str):
                        session_id = event["thread_id"]
                    item = event.get("item")
                    if (
                        event.get("type") == "item.completed"
                        and isinstance(item, Mapping)
                        and item.get("type") == "agent_message"
                        and isinstance(item.get("text"), str)
                    ):
                        messages.append(item["text"])
                    if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
                        usage = dict(event["usage"])
                    if event.get("type") in {"turn.failed", "error"}:
                        turn_error = str(event.get("message") or event.get("error") or event)
                    projection = _event_projection(event)
                    if projection is not None and self.progress_reporter is not None:
                        with contextlib.suppress(Exception):
                            self.progress_reporter.acp_event(invocation, projection)

            async def read_stderr() -> None:
                assert self._process is not None and self._process.stderr is not None
                while True:
                    chunk = await self._process.stderr.read(4096)
                    if not chunk:
                        return
                    stderr_chunks.append(chunk.decode("utf-8", errors="replace"))

            waitable = asyncio.gather(self._process.wait(), read_stdout(), read_stderr())
            if invocation.timeout_seconds is None:
                await waitable
            else:
                await asyncio.wait_for(waitable, timeout=invocation.timeout_seconds)
            return_code = int(self._process.returncode or 0)
            if self._cancel_requested:
                outcome = "cancelled"
                error = "Codex invocation cancelled"
                stop_reason = "cancelled"
            elif return_code == 0 and turn_error is None:
                outcome = "succeeded"
                error = None
                stop_reason = "end_turn"
            else:
                outcome = "failed"
                error = turn_error or "".join(stderr_chunks)[-4000:] or f"codex exited with {return_code}"
                stop_reason = "failed"
            return AgentExecutionResult(
                status=outcome,
                response_text=(messages[-1].strip() if messages else ""),
                native_process_id=self._process.pid,
                native_process_instance_id=self._process_instance_id,
                native_session_id=session_id,
                stop_reason=stop_reason,
                events=events,
                stderr="".join(stderr_chunks),
                usage=usage,
                error=error,
            )
        except asyncio.TimeoutError:
            outcome = "cancelled"
            await self._terminate_process()
            return AgentExecutionResult(
                status="cancelled",
                native_process_id=self._process.pid if self._process else None,
                native_process_instance_id=self._process_instance_id,
                native_session_id=session_id,
                stop_reason="cancelled",
                events=events,
                stderr="".join(stderr_chunks),
                error=f"Codex invocation timed out after {invocation.timeout_seconds}s",
            )
        except asyncio.CancelledError:
            outcome = "cancelled"
            await asyncio.shield(self._terminate_process())
            raise
        except Exception as exc:
            return AgentExecutionResult(
                status="failed",
                native_process_id=self._process.pid if self._process else None,
                native_process_instance_id=self._process_instance_id,
                native_session_id=session_id,
                events=events,
                stderr="".join(stderr_chunks),
                error=f"{type(exc).__name__}: {exc}",
            )
        finally:
            if self._lease_file is not None:
                with contextlib.suppress(OSError):
                    self._lease_file.unlink()
            self._lease_file = None
            self._notify_finished(invocation, outcome)

    async def _terminate_process(self) -> None:
        process = self._process
        if process is None or process.returncode is not None:
            return
        if self._lease_file is not None:
            with contextlib.suppress(OSError):
                self._lease_file.unlink()
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            with contextlib.suppress(ProcessLookupError):
                process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(process.wait(), timeout=2.0)

    async def cancel(self, invocation_id: str) -> None:
        if self._active_invocation_id == invocation_id:
            self._cancel_requested = True
            await self._terminate_process()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._terminate_process()
        self._started = False

    def _notify_started(self, invocation: AgentInvocation) -> None:
        if self.progress_reporter is not None:
            with contextlib.suppress(Exception):
                self.progress_reporter.invocation_started(invocation, backend="Codex")

    def _notify_finished(self, invocation: AgentInvocation, status: str) -> None:
        if self.progress_reporter is not None:
            with contextlib.suppress(Exception):
                self.progress_reporter.invocation_finished(invocation, status, backend="Codex")


@dataclass(frozen=True)
class CodexBackendFactory:
    workspace: Path
    codex_command: Optional[str] = None
    profile: Optional[str] = None
    model: Optional[str] = None
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

    def _command(self) -> str:
        supplied = self.codex_command or shutil.which("codex") or "codex"
        command = shutil.which(supplied) or (supplied if Path(supplied).is_file() else None)
        if command is None:
            raise HarnessError(f"Codex executable not found: {supplied}")
        return str(Path(command).expanduser().resolve())

    def _search_support(self) -> SearchMcpSupport:
        return SearchMcpSupport(
            search_dir=self.search_dir,
            provider_python=self.search_provider_python,
            provider_limit=self.search_provider_limit,
            coordinator=self.search_coordinator,
            camofox_fallback_enabled=self.camofox_fallback_enabled,
            camofox_base_url=self.camofox_base_url,
        )

    async def _run(self, *args: str) -> tuple[int, str, str]:
        process = await asyncio.create_subprocess_exec(
            self._command(), *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)
        return process.returncode or 0, stdout.decode(errors="replace"), stderr.decode(errors="replace")

    async def preflight(self) -> Mapping[str, Any]:
        version_code, version_out, version_err = await self._run("--version")
        if version_code:
            raise HarnessError(version_err or version_out or "codex --version failed")
        login_code, login_out, login_err = await self._run("login", "status")
        if login_code:
            raise HarnessError(login_err or login_out or "codex login status failed")
        report: dict[str, Any] = {
            "harness": "codex",
            "command": self._command(),
            "version": (version_out or version_err).strip(),
            "authentication": (login_out or login_err).strip(),
            "profile": self.profile,
            "model": self.model,
            "ok": True,
        }
        if self.search_mcp_enabled:
            support = self._search_support()
            search_dir = support.resolved_search_dir()
            provider_python = support.resolved_provider_python()
            environment = load_search_environment(search_dir)
            registry = ProviderRegistry(
                search_dir=search_dir,
                python_executable=provider_python,
                environment=environment,
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
                "search_mcp": "configured",
                "search_dir": str(search_dir),
                "search_provider_python": provider_python,
                "search_route_count": len(registry.definitions),
                "search_route_available_count": available,
            })
        else:
            report["search_mcp"] = "disabled"
        report.update(
            CamofoxFallbackSupport(
                enabled=self.camofox_fallback_enabled,
                home=self.camofox_home,
                base_url=self.camofox_base_url,
            ).report()
        )
        return report

    async def probe(self) -> Mapping[str, Any]:
        return {"codex_exec": "ok", "model_check": "not_run"}

    def create(self, invocation: AgentInvocation) -> CodexExecAttemptRuntime:
        return CodexExecAttemptRuntime(
            self.workspace,
            codex_command=self._command(),
            profile=self.profile,
            model=self.model,
            progress_reporter=self.progress_reporter,
            search_mcp_enabled=self.search_mcp_enabled,
            search_support=self._search_support(),
            camofox_fallback_enabled=self.camofox_fallback_enabled,
            camofox_home=self.camofox_home,
            camofox_base_url=self.camofox_base_url,
            expected_invocation_id=invocation.invocation_id,
        )
