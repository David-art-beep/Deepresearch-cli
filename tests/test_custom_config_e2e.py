import asyncio
import json
import shutil
from pathlib import Path

from deepresearch_cli.cli import main
from deepresearch_cli.config import (
    NodeRegistry,
    RunRequest,
    compile_workflow,
    load_workflow_spec,
)
from deepresearch_cli.driver import ExecutionSessionConfig, WorkflowDriver
from deepresearch_cli.harness.stub import StubHarness
from deepresearch_cli.persistence import RunStore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ROOT = PROJECT_ROOT / "examples" / "custom-workflow"


class EightResearchHarness(StubHarness):
    """Start eight Research invocations before any of them can finish."""

    def __init__(self) -> None:
        super().__init__()
        self.active_research = 0
        self.peak_research = 0
        self.all_research_started = asyncio.Event()

    @staticmethod
    def _stub_plan(mode):
        plan = json.loads(json.dumps(StubHarness._stub_plan(mode)))
        template = plan["dimensions"][0]
        plan["dimensions"] = []
        for index in range(1, 5):
            dimension = json.loads(json.dumps(template))
            dimension["id"] = f"d{index}"
            dimension["name"] = f"Original dimension {index}"
            dimension["scope_ownership"]["owns"] = [f"stub fact {index}"]
            plan["dimensions"].append(dimension)
        return plan

    async def invoke(self, invocation):
        if invocation.node_type != "research":
            return await super().invoke(invocation)
        self.active_research += 1
        self.peak_research = max(self.peak_research, self.active_research)
        if self.active_research == 8:
            self.all_research_started.set()
        try:
            await asyncio.wait_for(self.all_research_started.wait(), timeout=5)
            return await super().invoke(invocation)
        finally:
            self.active_research -= 1


def test_example_custom_node_and_workflow_compile_to_eight_task_fanout():
    registry = NodeRegistry.load([EXAMPLE_ROOT / "nodes"])
    workflow = compile_workflow(
        load_workflow_spec(path=EXAMPLE_ROOT / "custom-heavy-8.yaml"),
        registry,
        output_format="markdown",
    )

    assert registry.get("expand-research-plan").kind == "script"
    assert "command/expand_research_plan.py" in registry.get(
        "expand-research-plan"
    ).resources
    first_research = next(step for step in workflow.steps if step.step_id == "research")
    second_research = next(
        step for step in workflow.steps if step.step_id == "research-2"
    )
    first_task = next(
        binding for binding in first_research.bindings if binding.port == "task"
    )
    second_task = next(
        binding for binding in second_research.bindings if binding.port == "task"
    )
    assert first_task.source_step_id == "expand-research-plan"
    assert second_task.source_step_id == "supplement-planner"


def test_custom_script_node_can_run_standalone_from_a_plan_artifact(tmp_path, capsys):
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(EightResearchHarness._stub_plan("normal"), ensure_ascii=False),
        encoding="utf-8",
    )
    runs = tmp_path / "runs"
    output = tmp_path / "output"

    code = main(
        [
            "node",
            "run",
            "expand-research-plan",
            "--nodes-dir",
            str(EXAMPLE_ROOT / "nodes"),
            "--input",
            f"plan={plan_path}",
            "--runs-dir",
            str(runs),
            "--output-dir",
            str(output),
            "--json",
        ]
    )
    value = json.loads(capsys.readouterr().out)

    assert code == 0
    assert value["status"] == "completed"
    expanded = json.loads(Path(value["result"]["path"]).read_text(encoding="utf-8"))
    assert [item["id"] for item in expanded["dimensions"]] == [
        f"d{index}" for index in range(1, 9)
    ]
    events = RunStore(runs).load_run(value["run_id"]).events
    custom_finished = next(
        event
        for event in events
        if event["type"] == "step_finished"
        and event["node_id"] == "expand-research-plan"
    )
    task_refs = [
        item
        for item in custom_finished["artifact_refs"]
        if item["type"] == "research-task"
    ]
    assert len(task_refs) == 8


def test_persisted_plan_stage_resumes_into_eight_concurrent_research_tasks(tmp_path):
    copied_example = tmp_path / "custom-workflow"
    shutil.copytree(EXAMPLE_ROOT, copied_example)
    harness = EightResearchHarness()
    asyncio.run(harness.start())
    store = RunStore(tmp_path / "runs")
    driver = WorkflowDriver(
        store,
        harness,
        ExecutionSessionConfig(harness="stub", max_concurrency=8),
        output_dir=tmp_path / "output",
    )
    registry = NodeRegistry.load([copied_example / "nodes"])
    projection = driver.create_run(
        RunRequest("config E2E", mode="heavy"),
        load_workflow_spec(path=copied_example / "custom-heavy-8.yaml"),
        registry,
    )

    plan_ready = asyncio.run(driver.drive(projection.run_id, max_steps=2))
    assert plan_ready.status == "running"
    assert {item.step_id for item in plan_ready.instances.values()} == {"scout", "plan"}

    # Resume is intentionally isolated from the original YAML, Script and Validator.
    shutil.rmtree(copied_example)
    research_ready = asyncio.run(driver.resume(projection.run_id, max_steps=9))

    assert research_ready.status == "running"
    assert harness.peak_research == 8
    research_calls = [
        item for item in harness.invocations if item.node_type == "research"
    ]
    assert len(research_calls) == 8
    assert {item.agent_context["scope"]["dimension-id"] for item in research_calls} == {
        f"d{index}" for index in range(1, 9)
    }
    manifest = store.load_manifest(projection.run_id)
    custom_snapshot = next(
        item for item in manifest["nodes"] if item["id"] == "expand-research-plan"
    )
    assert "command/expand_research_plan.py" in custom_snapshot["resources"]
    assert "command/validate_expanded_plan.py" in custom_snapshot["resources"]
    assert "formal_validate_plan.py" in custom_snapshot["resources"]

    completed = asyncio.run(driver.resume(projection.run_id))
    assert completed.status == "completed"
    assert (tmp_path / "output" / projection.run_id / "report.md").is_file()
    assert {item.artifact_type for item in completed.artifacts} >= {
        "briefing",
        "research-plan",
        "research-task",
        "evidence",
        "review",
        "perspective",
        "supplement-plan",
        "report-outline",
        "content-task",
        "report-draft",
        "stitched-report",
        "final-review",
        "report",
    }
    report_planner = next(
        item for item in harness.invocations if item.node_type == "report-planner"
    )
    assert len(report_planner.agent_context["inputs"]["evidence"]) == 8


def test_new_user_can_discover_the_example_custom_node_from_cli(capsys):
    code = main(
        [
            "nodes",
            "describe",
            "expand-research-plan",
            "--nodes-dir",
            str(EXAMPLE_ROOT / "nodes"),
            "--json",
        ]
    )
    value = json.loads(capsys.readouterr().out)

    assert code == 0
    assert value["id"] == "expand-research-plan"
    assert value["kind"] == "script"
    assert value["outputs"]["research-tasks"]["mode"] == "batch"
