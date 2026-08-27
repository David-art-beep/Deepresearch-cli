"""Production backend selection without coupling WorkflowService to adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from deepresearch_cli.progress import ProgressReporter

from .claude_acp import ClaudeAcpBackendFactory
from .codex_acp import CodexAcpBackendFactory
from .codex_exec import CodexBackendFactory
from .hermes_acp import HermesBackendFactory
from .protocol import BackendFactory


PRODUCTION_BACKENDS = ("hermes", "codex", "codex-exec", "claude-code")


def build_backend_factory(
    backend: str,
    *,
    workspace: Path,
    command: Optional[str] = None,
    profile: Optional[str] = None,
    model: Optional[str] = None,
    progress_reporter: Optional[ProgressReporter] = None,
    search_mcp_enabled: bool = True,
    search_dir: Optional[Path] = None,
    search_provider_python: Optional[str] = None,
    search_provider_limit: int = 20,
    search_coordinator: Optional[object] = None,
    camofox_fallback_enabled: bool = False,
    camofox_home: Optional[Path] = None,
    camofox_base_url: Optional[str] = None,
) -> BackendFactory:
    if backend == "hermes":
        return HermesBackendFactory(
            workspace=workspace,
            hermes_command=command,
            profile=profile,
            progress_reporter=progress_reporter,
            search_mcp_enabled=search_mcp_enabled,
            search_dir=search_dir,
            search_provider_python=search_provider_python,
            search_provider_limit=search_provider_limit,
            search_coordinator=search_coordinator,
            camofox_fallback_enabled=camofox_fallback_enabled,
            camofox_home=camofox_home,
            camofox_base_url=camofox_base_url,
        )
    if backend == "codex":
        return CodexAcpBackendFactory(
            workspace=workspace,
            codex_command=command,
            profile=profile,
            model=model,
            progress_reporter=progress_reporter,
            search_mcp_enabled=search_mcp_enabled,
            search_dir=search_dir,
            search_provider_python=search_provider_python,
            search_provider_limit=search_provider_limit,
            search_coordinator=search_coordinator,
            camofox_fallback_enabled=camofox_fallback_enabled,
            camofox_home=camofox_home,
            camofox_base_url=camofox_base_url,
        )
    if backend == "codex-exec":
        return CodexBackendFactory(
            workspace=workspace,
            codex_command=command,
            profile=profile,
            model=model,
            progress_reporter=progress_reporter,
            search_mcp_enabled=search_mcp_enabled,
            search_dir=search_dir,
            search_provider_python=search_provider_python,
            search_provider_limit=search_provider_limit,
            search_coordinator=search_coordinator,
            camofox_fallback_enabled=camofox_fallback_enabled,
            camofox_home=camofox_home,
            camofox_base_url=camofox_base_url,
        )
    if backend == "claude-code":
        return ClaudeAcpBackendFactory(
            workspace=workspace,
            claude_acp_command=command,
            profile=profile,
            model=model,
            progress_reporter=progress_reporter,
            search_mcp_enabled=search_mcp_enabled,
            search_dir=search_dir,
            search_provider_python=search_provider_python,
            search_provider_limit=search_provider_limit,
            search_coordinator=search_coordinator,
            camofox_fallback_enabled=camofox_fallback_enabled,
            camofox_home=camofox_home,
            camofox_base_url=camofox_base_url,
        )
    raise ValueError("unsupported production backend: %s" % backend)
