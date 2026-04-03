"""Tests for browser_agent.recording — recorder, player, parameterizer, version control."""

import asyncio
import pytest
from datetime import datetime, timezone

from browser_agent.recording.recorder import (
    WorkflowRecorder, Recording, RecordedAction, RecordingParameter, RecordingStore,
)
from browser_agent.recording.player import WorkflowPlayer, ReplayMode, ReplayResult
from browser_agent.recording.parameterizer import RecordingParameterizer
from browser_agent.recording.adaptive_replay import AdaptiveReplay
from browser_agent.recording.version_control import RecordingVersionControl, RecordingDiff


# --- RecordedAction ---


class TestRecordedAction:
    def test_to_dict_roundtrip(self):
        action = RecordedAction(
            step_index=0, action_type="click",
            target_selector="#submit-btn", target_text="Submit",
            target_coordinates=(100, 200), page_url="https://example.com",
        )
        d = action.to_dict()
        r = RecordedAction.from_dict(d)
        assert r.action_type == "click"
        assert r.target_selector == "#submit-btn"
        assert r.target_coordinates == (100, 200)

    def test_default_values(self):
        a = RecordedAction()
        assert a.success is True
        assert a.is_parameterized is False


# --- Recording ---


class TestRecording:
    def test_to_dict_roundtrip(self):
        rec = Recording(
            name="Test Workflow",
            start_url="https://example.com",
            actions=[
                RecordedAction(step_index=0, action_type="navigate", target_url="https://example.com"),
                RecordedAction(step_index=1, action_type="click", target_selector="#btn"),
            ],
            parameters=[RecordingParameter(name="url", parameter_type="url", default_value="https://example.com")],
        )
        d = rec.to_dict()
        r = Recording.from_dict(d)
        assert r.name == "Test Workflow"
        assert len(r.actions) == 2
        assert len(r.parameters) == 1
        assert r.actions[0].action_type == "navigate"

    def test_compute_hash(self):
        rec = Recording(actions=[
            RecordedAction(action_type="click", target_url="https://example.com"),
        ])
        h = rec.compute_hash()
        assert len(h) == 64

    def test_steps_alias(self):
        rec = Recording(actions=[
            RecordedAction(action_type="navigate"),
        ])
        assert len(rec.steps) == 1
        assert rec.steps[0].action_type == "navigate"

    def test_total_steps_auto(self):
        rec = Recording(actions=[
            RecordedAction(), RecordedAction(), RecordedAction(),
        ])
        assert rec.total_steps == 3


# --- WorkflowRecorder ---


class TestWorkflowRecorder:
    @pytest.fixture
    def recorder(self, tmp_path):
        store = RecordingStore(str(tmp_path / "rec.db"))
        return WorkflowRecorder(store=store)

    @pytest.mark.asyncio
    async def test_start_stop(self, recorder):
        rec = await recorder.start_recording("Test", start_url="https://example.com")
        assert recorder.is_recording is True
        assert rec.name == "Test"

        result = await recorder.stop_recording()
        assert result is not None
        assert result.name == "Test"
        assert recorder.is_recording is False

    @pytest.mark.asyncio
    async def test_record_actions(self, recorder):
        await recorder.start_recording("Multi-step")
        await recorder.record_action(
            action_type="navigate",
            parameters={"url": "https://example.com"},
            target_url="https://example.com",
            page_url="https://example.com",
        )
        await recorder.record_action(
            action_type="click",
            parameters={"selector": "#btn"},
            target_selector="#btn",
            target_description="Submit button",
        )
        rec = await recorder.stop_recording()
        assert len(rec.actions) == 2
        assert rec.actions[0].action_type == "navigate"
        assert rec.actions[1].action_type == "click"

    @pytest.mark.asyncio
    async def test_pause_resume(self, recorder):
        await recorder.start_recording("Pause test")
        await recorder.record_action(action_type="click", parameters={})
        assert recorder.is_recording is True

        await recorder.pause_recording()
        assert recorder.is_recording is False

        # Actions while paused are ignored
        result = await recorder.record_action(action_type="type_text", parameters={"text": "ignored"})
        assert result is None

        await recorder.resume_recording()
        assert recorder.is_recording is True
        await recorder.record_action(action_type="click", parameters={})
        rec = await recorder.stop_recording()
        assert len(rec.actions) == 2  # Paused action was skipped

    @pytest.mark.asyncio
    async def test_metadata(self, recorder):
        await recorder.start_recording("Meta", tags=["smoke", "login"])
        await recorder.record_action(
            action_type="navigate",
            parameters={"url": "https://example.com"},
            page_url="https://example.com",
        )
        rec = await recorder.stop_recording()
        assert rec.tags == ["smoke", "login"]
        assert rec.end_url == "https://example.com"

    @pytest.mark.asyncio
    async def test_stop_without_start(self, recorder):
        result = await recorder.stop_recording()
        assert result is None

    @pytest.mark.asyncio
    async def test_persistence(self, recorder, tmp_path):
        await recorder.start_recording("Persist", start_url="https://example.com")
        await recorder.record_action(action_type="navigate", parameters={"url": "https://example.com"})
        rec = await recorder.stop_recording()

        # Load from store
        store = RecordingStore(str(tmp_path / "rec.db"))
        loaded = await store.load(rec.recording_id)
        assert loaded is not None
        assert loaded.name == "Persist"


# --- WorkflowPlayer ---


class TestWorkflowPlayer:
    @pytest.fixture
    def recording(self):
        return Recording(
            name="Test Recording",
            start_url="https://example.com",
            actions=[
                RecordedAction(step_index=0, action_type="navigate", target_url="https://example.com"),
                RecordedAction(step_index=1, action_type="click", target_selector="#btn", target_description="Submit"),
            ],
        )

    @pytest.mark.asyncio
    async def test_play_success(self, recording):
        player = WorkflowPlayer(mode=ReplayMode.ADAPTIVE)
        result = await player.play(recording)
        assert result.success is True
        assert result.completed_steps == 2
        assert result.total_steps == 2

    @pytest.mark.asyncio
    async def test_play_strict(self, recording):
        player = WorkflowPlayer(mode=ReplayMode.STRICT)
        result = await player.play(recording)
        assert result.success is True
        assert result.mode == ReplayMode.STRICT

    @pytest.mark.asyncio
    async def test_play_vision_only(self, recording):
        player = WorkflowPlayer(mode=ReplayMode.VISION_ONLY)
        result = await player.play(recording)
        assert result.success is True
        # In vision mode, strategy should be "vision"
        assert all(s.strategy_used == "vision" for s in result.step_results)

    @pytest.mark.asyncio
    async def test_dry_run(self, recording):
        player = WorkflowPlayer()
        result = await player.dry_run(recording)
        assert result.success is True
        assert result.execution_time == 0.0
        assert all(s.strategy_used == "dry_run" for s in result.step_results)

    @pytest.mark.asyncio
    async def test_on_step_callback(self, recording):
        steps = []
        player = WorkflowPlayer()

        def on_step(step):
            steps.append(step)

        await player.play(recording, on_step=on_step)
        assert len(steps) == 2

    @pytest.mark.asyncio
    async def test_result_serialization(self, recording):
        player = WorkflowPlayer()
        result = await player.play(recording)
        d = result.to_dict()
        assert "run_id" in d
        assert "step_results" in d
        assert d["total_steps"] == 2

    @pytest.mark.asyncio
    async def test_missing_required_parameter(self):
        recording = Recording(
            actions=[RecordedAction(action_type="navigate")],
            parameters=[RecordingParameter(name="url", required=True)],
        )
        player = WorkflowPlayer()
        result = await player.play(recording)
        assert result.success is False
        assert result.failed_step == 0

    @pytest.mark.asyncio
    async def test_parameter_with_default(self):
        recording = Recording(
            actions=[RecordedAction(action_type="navigate")],
            parameters=[RecordingParameter(name="url", required=True, default_value="https://example.com")],
        )
        player = WorkflowPlayer()
        result = await player.play(recording)
        assert result.success is True


# --- RecordingParameterizer ---


class TestRecordingParameterizer:
    @pytest.mark.asyncio
    async def test_auto_detect(self):
        paramizer = RecordingParameterizer()
        recording = Recording(
            actions=[
                RecordedAction(step_index=0, action_type="navigate", parameters={"url": "https://example.com/search"}),
                RecordedAction(step_index=1, action_type="type_text", parameters={"text": "john.doe@acme.com", "field": "email"}),
            ],
        )
        params = await paramizer.auto_detect_parameters(recording)
        # Should detect at least URL or email
        assert len(params) >= 1

    @pytest.mark.asyncio
    async def test_validate_ok(self):
        paramizer = RecordingParameterizer()
        recording = Recording(
            parameters=[RecordingParameter(name="url", required=True, parameter_type="url")],
        )
        ok, errors = await paramizer.validate_parameters({"url": "https://example.com"}, recording)
        assert ok is True
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_validate_missing(self):
        paramizer = RecordingParameterizer()
        recording = Recording(
            parameters=[RecordingParameter(name="url", required=True)],
        )
        ok, errors = await paramizer.validate_parameters({}, recording)
        assert ok is False
        assert any("url" in e for e in errors)


# --- AdaptiveReplay ---


class TestAdaptiveReplay:
    @pytest.mark.asyncio
    async def test_match_identical_pages(self):
        adaptive = AdaptiveReplay()
        html = "<html><body>Hello</body></html>"
        result = await adaptive.match_page_state(html, html)
        assert result.matches is True
        assert result.similarity == 1.0

    @pytest.mark.asyncio
    async def test_match_different_pages(self):
        adaptive = AdaptiveReplay()
        result = await adaptive.match_page_state("<html>a b c</html>", "<html>x y z</html>")
        assert result.matches is False

    @pytest.mark.asyncio
    async def test_find_element_fallback_to_position(self):
        adaptive = AdaptiveReplay()
        action = RecordedAction(target_coordinates=(100, 200))
        match = await adaptive.find_element(action)
        assert match.found is True
        assert match.strategy == "position"

    @pytest.mark.asyncio
    async def test_find_element_nothing_to_try(self):
        adaptive = AdaptiveReplay()
        action = RecordedAction()
        match = await adaptive.find_element(action)
        assert match.found is False


# --- VersionControl ---


class TestVersionControl:
    @pytest.mark.asyncio
    async def test_save_and_get_version(self, tmp_path):
        store = RecordingStore(str(tmp_path / "vc.db"))
        vc = RecordingVersionControl(store)
        rec = Recording(name="Test", version=0)
        saved = await vc.save_version(rec, "Initial version")
        assert saved.version == 1

        loaded = await vc.get_version(rec.recording_id, 1)
        assert loaded is not None
        assert loaded.version == 1

    @pytest.mark.asyncio
    async def test_diff_versions(self, tmp_path):
        store = RecordingStore(str(tmp_path / "vc.db"))
        vc = RecordingVersionControl(store)

        rec = Recording(
            name="Test", version=0,
            actions=[RecordedAction(step_index=0, action_type="click", target_selector="#btn1")],
        )
        await vc.save_version(rec, "v1")

        rec.actions.append(RecordedAction(step_index=1, action_type="type_text", target_selector="#input"))
        await vc.save_version(rec, "v2: added input")

        diff = await vc.diff(rec.recording_id, 1, 2)
        assert diff.version_a == 1
        assert diff.version_b == 2
        assert len(diff.actions_added) >= 1

    @pytest.mark.asyncio
    async def test_rollback(self, tmp_path):
        store = RecordingStore(str(tmp_path / "vc.db"))
        vc = RecordingVersionControl(store)

        rec = Recording(
            name="Test", version=0,
            actions=[RecordedAction(step_index=0, action_type="click")],
        )
        await vc.save_version(rec, "v1")

        rec.actions.append(RecordedAction(step_index=1, action_type="type_text"))
        await vc.save_version(rec, "v2: added typing")

        rolled = await vc.rollback(rec.recording_id, 1)
        assert rolled is not None
        assert rolled.version == 3
        assert rolled.parent_version == 1
        assert len(rolled.actions) == 1

    @pytest.mark.asyncio
    async def test_list_versions(self, tmp_path):
        store = RecordingStore(str(tmp_path / "vc.db"))
        vc = RecordingVersionControl(store)

        rec = Recording(name="Test", version=0)
        await vc.save_version(rec, "v1")
        await vc.save_version(rec, "v2")
        await vc.save_version(rec, "v3")

        versions = await vc.list_versions(rec.recording_id)
        assert len(versions) == 3
