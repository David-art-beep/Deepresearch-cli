"""Starlette application and server entry point for the local console."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Mapping, Sequence

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from starlette.routing import Route

from deepresearch_cli.config.paths import builtin_asset_dir
from deepresearch_cli.persistence import RunNotFoundError, RunStore

from .manager import WebRunManager
from .snapshot import build_run_snapshot


def create_app(
    *, runs_dir: Path = Path("./runs"), output_dir: Path = Path("./output"),
    node_dirs: Sequence[Path] = (), manager: WebRunManager | None = None,
    startup_request: Mapping[str, Any] | None = None,
) -> Starlette:
    runs_dir = runs_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    store = RunStore(runs_dir)
    controller = manager or WebRunManager(runs_dir, output_dir, node_dirs)
    static_dir = builtin_asset_dir() / "web"

    def snapshot(run_id: str):
        try:
            value = build_run_snapshot(store, run_id, output_dir=output_dir)
            value["worker_active"] = controller.active(run_id)
            return value
        except RunNotFoundError:
            pending = controller.pending_snapshot(run_id)
            if pending is not None:
                pending["worker_active"] = controller.active(run_id)
                return pending
            raise

    initial_run_id: str | None = None

    async def start_initial_run() -> None:
        nonlocal initial_run_id
        if startup_request is not None:
            initial_run_id = controller.start(startup_request)

    @asynccontextmanager
    async def lifespan(_: Starlette):
        await start_initial_run()
        yield

    async def index(request: Request):
        if request.url.path == "/" and initial_run_id is not None:
            return RedirectResponse(f"/runs/{initial_run_id}", status_code=307)
        return FileResponse(static_dir / "index.html")

    async def asset(request: Request):
        name = request.path_params["name"]
        if name not in {"app.js", "styles.css"}:
            return JSONResponse({"error": "asset not found"}, status_code=404)
        return FileResponse(static_dir / name)

    async def create_run(request: Request):
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError("request body must be an object")
            if body.get("report_format") not in {"brief", "formal_report"}:
                raise ValueError(
                    "report_format must be selected: brief or formal_report"
                )
            run_id = controller.start(body)
            return JSONResponse({"run_id": run_id, "url": f"/runs/{run_id}"}, status_code=202)
        except (ValueError, TypeError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    async def get_run(request: Request):
        try:
            return JSONResponse(snapshot(request.path_params["run_id"]))
        except RunNotFoundError:
            return JSONResponse({"error": "run not found"}, status_code=404)
        except Exception as exc:
            return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)

    async def events(request: Request):
        run_id = request.path_params["run_id"]

        async def stream():
            previous = None
            heartbeat = 0
            while not await request.is_disconnected():
                try:
                    value = snapshot(run_id)
                except RunNotFoundError:
                    yield 'event: error\ndata: {"error":"run not found"}\n\n'
                    return
                marker = (
                    value.get("last_event_seq"),
                    value.get("status"),
                    value.get("error"),
                    (value.get("search") or {}).get("version"),
                )
                if marker != previous:
                    yield "event: snapshot\ndata: " + json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n\n"
                    previous = marker
                heartbeat += 1
                if heartbeat % 20 == 0:
                    yield ": heartbeat\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    async def resume(request: Request):
        try:
            body = await request.json()
            if not isinstance(body, dict):
                body = {}
            controller.resume(request.path_params["run_id"], body)
            return JSONResponse({"status": "resuming"}, status_code=202)
        except RunNotFoundError:
            return JSONResponse({"error": "run not found"}, status_code=404)
        except (ValueError, TypeError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=409)

    async def result_file(request: Request):
        run_id, filename = request.path_params["run_id"], request.path_params["filename"]
        if Path(filename).name != filename or filename in {".", ".."}:
            return JSONResponse({"error": "unsafe filename"}, status_code=400)
        path = output_dir / run_id / filename
        if path.is_symlink() or not path.is_file():
            return JSONResponse({"error": "file not found"}, status_code=404)
        return FileResponse(path, filename=filename)

    routes = [
        Route("/", index), Route("/runs/{run_id}", index),
        Route("/assets/{name}", asset), Route("/api/runs", create_run, methods=["POST"]),
        Route("/api/runs/{run_id}", get_run), Route("/api/runs/{run_id}/events", events),
        Route("/api/runs/{run_id}/resume", resume, methods=["POST"]),
        Route("/api/runs/{run_id}/files/{filename}", result_file),
    ]
    app = Starlette(debug=False, routes=routes, lifespan=lifespan)
    app.state.run_manager = controller
    return app


def run_web_server(
    *, host: str, port: int, runs_dir: Path, output_dir: Path,
    node_dirs: Sequence[Path] = (), startup_request: Mapping[str, Any] | None = None,
) -> int:
    import uvicorn

    app = create_app(
        runs_dir=runs_dir, output_dir=output_dir, node_dirs=node_dirs,
        startup_request=startup_request,
    )
    print(f"DeepResearch 控制台：http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0
