import asyncio
import json
from collections import Counter
from pathlib import Path

from deepresearch_cli.config import NodeRegistry, RunRequest, load_workflow_spec
from deepresearch_cli.driver import ExecutionSessionConfig, WorkflowDriver
from deepresearch_cli.harness.stub import StubHarness
from deepresearch_cli.persistence import RunStore


class SupplementHarness(StubHarness):
    """Emit one batch task so the repeated YAML nodes become runnable."""

    @classmethod
    def _materialize_stub_outputs(cls, invocation):
        super()._materialize_stub_outputs(invocation)
        if invocation.node_type != "supplement-planner":
            return
        context = invocation.agent_context
        dimension = context["scope"]["dimension-id"]
        plan_path = Path(context["outputs"]["supplement-plan"]["path"])
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["supplement_items"] = [
            {
                "id": f"{dimension}-s1",
                "type": "coverage",
                "gap": "A deterministic second pass is required.",
                "question": "What does the second pass find?",
                "rationale": "Exercise the configured repeated cycle.",
                "suggested_sources": ["official"],
                "candidate_leads": [],
                "source_refs": ["review:stub"],
                "review_refs": [],
                "impact_if_skipped": "The cycle would not be tested.",
                "status": "pending",
                "resolution_note": "",
            }
        ]
        cls._write_json(plan_path, plan)
        task_dir = Path(context["outputs"]["research-tasks"]["directory"])
        cls._write_json(
            task_dir / f"{dimension}.json",
            {"dimension_id": dimension, "question": "Run the second pass"},
        )


def test_repeated_yaml_nodes_execute_after_supplement_batch_exists(tmp_path):
    harness = SupplementHarness()
    asyncio.run(harness.start())
    store = RunStore(tmp_path / "runs")
    driver = WorkflowDriver(
        store,
        harness,
        ExecutionSessionConfig(harness="stub"),
        output_dir=tmp_path / "output",
    )
    projection = driver.create_run(
        RunRequest("second cycle", mode="heavy"),
        load_workflow_spec(mode="heavy"),
        NodeRegistry.load(),
    )

    projection = asyncio.run(driver.drive(projection.run_id))

    assert projection.status == "completed"
    counts = Counter(item.node_type for item in harness.invocations)
    assert counts["research"] == 2
    assert counts["review"] == 2
    assert counts["perspective"] == 2
    assert any(item.step_id == "research-2" for item in projection.instances.values())
    assert any(item.step_id == "perspective-2" for item in projection.instances.values())
    completed_plans = [
        item for item in projection.artifacts
        if item.artifact_type == "supplement-plan" and item.step_id == "research-2"
    ]
    assert len(completed_plans) == 1
    final_review = next(
        item for item in harness.invocations if item.node_type == "final-review-diagnostic"
    )
    assert final_review.agent_context["inputs"]["outline"]
    assert final_review.agent_context["inputs"]["drafts"]
    assert final_review.agent_context["inputs"]["supplement-plans"]
    assert final_review.agent_context["prompt"]["content_unit_paths"]
