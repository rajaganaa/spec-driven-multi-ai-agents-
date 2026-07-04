"""
tests/test_eval.py — Phase 3 (evaluation harness) unit tests

Focus areas:
  1. hub/eval/golden_tasks.py: the fixed suite is well-formed (5-10
     tasks, unique ids, valid roles).
  2. hub/eval/judge.py: drives a real ADK LlmAgent + Runner loop with a
     FakeLlm (tests/fake_llm.py) instead of a live model call — no
     network access, no API key — confirming pass/fail is derived from
     per-criterion scores (not a separately-hallucinated verdict field),
     and that a malformed/incomplete judge response is reported as
     ok=False rather than silently passing.
  3. hub/eval/runner.py: drives the real hub/runner/task_runner.py
     pipeline (also via FakeLlm) in a fully isolated tmp_path fake hub,
     and specifically verifies the snapshot/restore guarantee described
     in that module's docstring — a real project.meta.json/board.json
     (simulating the user's actual active project) must come back
     byte-for-byte unchanged after an eval run, and every golden spec
     file the run wrote must be cleaned up, even though the run
     temporarily points the "active project" at the eval sandbox.

All file I/O is redirected into a tmp_path fake hub via monkeypatch on
hub.tools.tools and hub.memory.spec_loader's module-level path
constants, matching tests/test_task_runner.py's fake_hub fixture — no
test here touches the real specs/, status/, project.meta.json, or
workspace/projects/.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from google.adk.models.llm_response import LlmResponse  # noqa: E402
from google.genai import types  # noqa: E402

from hub.eval import judge as J  # noqa: E402
from hub.eval import runner as EV  # noqa: E402
from hub.eval.golden_tasks import GOLDEN_TASKS, GoldenTask  # noqa: E402
from hub.memory import spec_loader as S  # noqa: E402
from hub.runner import task_runner as R  # noqa: E402
from hub.tools import tools as TOOLS  # noqa: E402
from tests.fake_llm import FakeLlm, json_turn  # noqa: E402


def function_call_turn(name: str, args: dict) -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=[types.Part.from_function_call(name=name, args=args)]))


def text_response_turn(text: str) -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=[types.Part.from_text(text=text)]))


def make_verdict_json(criteria: list, all_pass: bool, overall_score: float = 0.9) -> dict:
    return {
        "criterion_scores": [{"criterion": c, "passed": all_pass, "comment": "ok"} for c in criteria],
        "overall_score": overall_score,
        "summary": "Looks fine." if all_pass else "Missing required behavior.",
    }


@pytest.fixture
def fake_hub(tmp_path, monkeypatch):
    """Fully isolated fake hub, same shape as test_task_runner.py's
    fixture: specs/, status/, project.meta.json, and
    workspace/projects/ all redirected into tmp_path."""
    root = tmp_path / "fake-hub"
    specs = root / "specs"
    features_dir = specs / "features"
    tasks_dir = specs / "tasks"
    workspace_root = root / "workspace" / "projects"
    features_dir.mkdir(parents=True)
    tasks_dir.mkdir(parents=True)
    workspace_root.mkdir(parents=True)

    monkeypatch.setattr(TOOLS, "ROOT", root)
    monkeypatch.setattr(TOOLS, "SPECS_ROOT", specs.resolve())
    monkeypatch.setattr(TOOLS, "WORKSPACE_ROOT", workspace_root.resolve())

    monkeypatch.setattr(S, "ROOT", root)
    monkeypatch.setattr(S, "SPECS_DIR", specs)
    monkeypatch.setattr(S, "FEATURES_DIR", features_dir)
    monkeypatch.setattr(S, "TASKS_DIR", tasks_dir)
    monkeypatch.setattr(S, "BOARD_PATH", root / "status" / "board.json")
    monkeypatch.setattr(S, "META_PATH", root / "project.meta.json")

    return {"root": root, "features_dir": features_dir, "tasks_dir": tasks_dir, "workspace_root": workspace_root}


def _write_real_active_project(fake_hub, project_id: str = "my-real-project") -> None:
    """Simulate the user already having a real active project when an
    eval run starts — this is exactly the state run_eval_suite's
    snapshot/restore must protect."""
    (fake_hub["root"] / "project.meta.json").write_text(
        json.dumps({"project_id": project_id, "goal": "The user's actual real project", "stack": ["python"]}),
        encoding="utf-8",
    )
    (fake_hub["root"] / "status").mkdir(parents=True, exist_ok=True)
    (fake_hub["root"] / "status" / "board.json").write_text(
        json.dumps({"project_id": project_id, "updated_at": "", "tasks": [
            {"id": "T01", "feature": "F01", "status": "done", "agent": "coder", "commit": "abc123"}
        ]}),
        encoding="utf-8",
    )


# ── golden_tasks.py ──────────────────────────────────────────────────────

class TestGoldenTasks:
    def test_task_count_in_range(self):
        assert 5 <= len(GOLDEN_TASKS) <= 10

    def test_ids_are_unique(self):
        ids = [t.id for t in GOLDEN_TASKS]
        assert len(ids) == len(set(ids))

    def test_every_task_has_valid_role(self):
        for t in GOLDEN_TASKS:
            assert t.role in ("coder", "tester", "reviewer", "explorer")

    def test_every_task_has_acceptance_criteria(self):
        for t in GOLDEN_TASKS:
            assert len(t.acceptance_criteria) >= 1

    def test_context_files_referencing_existing_code_have_seed_content(self):
        # If a task's context_files points at a file the task doesn't
        # itself create (bug fix / test / review tasks), seed_files must
        # provide that file's starting content, or the task is
        # unrunnable — the specialist would be told to read a file that
        # doesn't exist.
        for t in GOLDEN_TASKS:
            if t.role in ("tester", "reviewer") or "fix" in t.title.lower() or "refactor" in t.title.lower():
                for cf in t.context_files:
                    assert cf in t.seed_files, f"{t.id} references {cf} but has no seed_files entry for it"


# ── judge.py ─────────────────────────────────────────────────────────────

class TestJudge:
    def test_all_criteria_pass_is_scored_as_passed(self):
        task = GoldenTask(
            id="X1", title="Test task", role="coder", goal="g", instructions="i",
            acceptance_criteria=["criterion A", "criterion B"],
        )
        fake_model = FakeLlm(model="fake", turns=[json_turn(make_verdict_json(task.acceptance_criteria, True))])

        result = J.run_judge(task, {"ok": True, "final_text": "done"}, model=fake_model)

        assert result["ok"] is True
        assert result["passed"] is True
        assert result["overall_score"] == 0.9

    def test_one_failed_criterion_means_not_passed(self):
        task = GoldenTask(
            id="X2", title="Test task", role="coder", goal="g", instructions="i",
            acceptance_criteria=["criterion A", "criterion B"],
        )
        verdict = make_verdict_json(task.acceptance_criteria, True)
        verdict["criterion_scores"][1]["passed"] = False
        fake_model = FakeLlm(model="fake", turns=[json_turn(verdict)])

        result = J.run_judge(task, {"ok": True, "final_text": "done"}, model=fake_model)

        assert result["ok"] is True
        assert result["passed"] is False

    def test_incomplete_criterion_scoring_is_not_passed(self):
        # Judge only scored 1 of 2 acceptance criteria by exact text match.
        task = GoldenTask(
            id="X3", title="Test task", role="coder", goal="g", instructions="i",
            acceptance_criteria=["criterion A", "criterion B"],
        )
        verdict = make_verdict_json(["criterion A"], True)
        fake_model = FakeLlm(model="fake", turns=[json_turn(verdict)])

        result = J.run_judge(task, {"ok": True, "final_text": "done"}, model=fake_model)

        assert result["ok"] is True
        assert result["passed"] is False

    def test_malformed_judge_output_is_reported_not_raised(self):
        task = GoldenTask(id="X4", title="t", role="coder", goal="g", instructions="i", acceptance_criteria=["a"])
        fake_model = FakeLlm(model="fake", turns=[text_response_turn("not valid json at all")])

        result = J.run_judge(task, {"ok": True, "final_text": "done"}, model=fake_model)

        assert result["ok"] is False
        assert result["error"]

    def test_failed_task_run_can_still_be_judged(self):
        task = GoldenTask(id="X5", title="t", role="coder", goal="g", instructions="i", acceptance_criteria=["a"])
        fake_model = FakeLlm(model="fake", turns=[json_turn(make_verdict_json(["a"], False, overall_score=0.0))])

        result = J.run_judge(task, {"ok": False, "error": "ran out of retries", "attempt_count": 3}, model=fake_model)

        assert result["ok"] is True
        assert result["passed"] is False


# ── runner.py ────────────────────────────────────────────────────────────

class TestRunEvalSuite:
    def test_real_active_project_state_is_restored(self, fake_hub):
        _write_real_active_project(fake_hub)
        meta_before = (fake_hub["root"] / "project.meta.json").read_bytes()
        board_before = (fake_hub["root"] / "status" / "board.json").read_bytes()

        task = GoldenTask(
            id="EVALX", title="Trivial write task", role="coder", goal="g", instructions="i",
            acceptance_criteria=["a file is written"],
        )
        specialist_model = FakeLlm(model="fake", turns=[
            function_call_turn("write_file", {"path": "out.py", "content": "x = 1\n"}),
            text_response_turn("Done."),
        ])
        judge_model = FakeLlm(model="fake", turns=[json_turn(make_verdict_json(task.acceptance_criteria, True))])

        summary = EV.run_eval_suite([task], model=specialist_model, judge_model=judge_model)

        assert summary["ok"] is True
        assert (fake_hub["root"] / "project.meta.json").read_bytes() == meta_before
        assert (fake_hub["root"] / "status" / "board.json").read_bytes() == board_before

    def test_no_prior_active_project_leaves_none_behind(self, fake_hub):
        # No project.meta.json/board.json exist before this run at all.
        assert not (fake_hub["root"] / "project.meta.json").exists()

        task = GoldenTask(
            id="EVALY", title="Trivial write task", role="coder", goal="g", instructions="i",
            acceptance_criteria=["a file is written"],
        )
        specialist_model = FakeLlm(model="fake", turns=[
            function_call_turn("write_file", {"path": "out.py", "content": "x = 1\n"}),
            text_response_turn("Done."),
        ])
        judge_model = FakeLlm(model="fake", turns=[json_turn(make_verdict_json(task.acceptance_criteria, True))])

        EV.run_eval_suite([task], model=specialist_model, judge_model=judge_model)

        assert not (fake_hub["root"] / "project.meta.json").exists()
        assert not (fake_hub["root"] / "status" / "board.json").exists()

    def test_golden_specs_are_cleaned_up(self, fake_hub):
        task = GoldenTask(
            id="EVALZ", title="Trivial write task", role="coder", goal="g", instructions="i",
            acceptance_criteria=["a file is written"],
        )
        specialist_model = FakeLlm(model="fake", turns=[
            function_call_turn("write_file", {"path": "out.py", "content": "x = 1\n"}),
            text_response_turn("Done."),
        ])
        judge_model = FakeLlm(model="fake", turns=[json_turn(make_verdict_json(task.acceptance_criteria, True))])

        EV.run_eval_suite([task], model=specialist_model, judge_model=judge_model)

        assert not (fake_hub["tasks_dir"] / EV.EVAL_TASKS_SUBDIR).exists()
        assert list(fake_hub["features_dir"].glob(f"{EV.EVAL_FEATURE_ID}*.md")) == []

    def test_workspace_cleaned_up_by_default(self, fake_hub):
        task = GoldenTask(
            id="EVALW", title="Trivial write task", role="coder", goal="g", instructions="i",
            acceptance_criteria=["a file is written"],
        )
        specialist_model = FakeLlm(model="fake", turns=[
            function_call_turn("write_file", {"path": "out.py", "content": "x = 1\n"}),
            text_response_turn("Done."),
        ])
        judge_model = FakeLlm(model="fake", turns=[json_turn(make_verdict_json(task.acceptance_criteria, True))])

        EV.run_eval_suite([task], model=specialist_model, judge_model=judge_model)

        assert not (fake_hub["workspace_root"] / EV.DEFAULT_EVAL_PROJECT_ID).exists()

    def test_pass_and_fail_counts_are_correct(self, fake_hub):
        passing_task = GoldenTask(
            id="EVALP", title="Passing task", role="coder", goal="g", instructions="i",
            acceptance_criteria=["criterion"],
        )
        failing_task = GoldenTask(
            id="EVALF", title="Failing task", role="coder", goal="g", instructions="i",
            acceptance_criteria=["criterion"],
        )

        # One shared FakeLlm queue drives both specialist runs in order:
        # task 1 succeeds on its first attempt; task 2 keeps hitting a
        # sandboxed path (blocked) until retries are exhausted.
        specialist_model = FakeLlm(model="fake", turns=[
            function_call_turn("write_file", {"path": "out.py", "content": "x = 1\n"}),
            text_response_turn("Done."),
            function_call_turn("write_file", {"path": "../escape.py", "content": "x"}),
            text_response_turn("Wrote it."),
            function_call_turn("write_file", {"path": "../escape.py", "content": "x"}),
            text_response_turn("Wrote it."),
            function_call_turn("write_file", {"path": "../escape.py", "content": "x"}),
            text_response_turn("Wrote it."),
        ])
        judge_model = FakeLlm(model="fake", turns=[
            json_turn(make_verdict_json(passing_task.acceptance_criteria, True)),
            json_turn(make_verdict_json(failing_task.acceptance_criteria, False, overall_score=0.1)),
        ])

        summary = EV.run_eval_suite(
            [passing_task, failing_task], model=specialist_model, judge_model=judge_model, max_retries=3,
        )

        assert summary["ok"] is True
        assert summary["task_count"] == 2
        assert summary["passed_count"] == 1
        assert summary["failed_count"] == 1
        assert summary["results"][0]["run"]["ok"] is True
        assert summary["results"][1]["run"]["ok"] is False

    def test_seed_files_are_written_before_the_task_runs(self, fake_hub):
        task = GoldenTask(
            id="EVALS", title="Uses a seeded file", role="coder", goal="g", instructions="i",
            acceptance_criteria=["a test file is written"],
            seed_files={"existing.py": "def f():\n    return 1\n"},
        )
        specialist_model = FakeLlm(model="fake", turns=[
            function_call_turn("write_file", {"path": "test_existing.py", "content": "def test_f():\n    assert True\n"}),
            text_response_turn("Done."),
        ])
        judge_model = FakeLlm(model="fake", turns=[json_turn(make_verdict_json(task.acceptance_criteria, True))])

        summary = EV.run_eval_suite(
            [task], model=specialist_model, judge_model=judge_model, keep_workspace=True,
        )

        assert summary["ok"] is True
        # The seed file must have existed on disk *before* the specialist
        # ran (it's read via a plain sandboxed read here, independent of
        # whether the FakeLlm-driven specialist itself called read_file).
        seeded = TOOLS.read_file(EV.DEFAULT_EVAL_PROJECT_ID, "existing.py")
        assert seeded["ok"] is True
        assert seeded["content"] == "def f():\n    return 1\n"
        written = TOOLS.read_file(EV.DEFAULT_EVAL_PROJECT_ID, "test_existing.py")
        assert written["ok"] is True
        # keep_workspace=True was used specifically so we could assert on
        # disk state here; clean up manually since the harness didn't.
        import shutil
        shutil.rmtree(fake_hub["workspace_root"] / EV.DEFAULT_EVAL_PROJECT_ID, ignore_errors=True)
