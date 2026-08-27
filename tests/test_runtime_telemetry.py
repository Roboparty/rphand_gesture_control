import json
from types import SimpleNamespace

from runtime_telemetry import build_runtime_state


def test_builds_json_safe_runtime_state_for_the_electron_sidebar():
    observation = SimpleNamespace(
        detected=True,
        gesture="pinch",
        curls={
            "thumb": 0.4,
            "index": 0.5,
            "middle": 0.6,
            "ring": 0.7,
            "pinky": 0.8,
        },
        thumb_spread=0.3,
    )

    state = build_runtime_state(
        mode="mirror",
        detection_enabled=True,
        sending=True,
        safety_state="tracking",
        observation=observation,
        display_inputs={"thumb": 1.2, "index": -0.1, "thumb_spread": 0.75},
        positions=[2500, 12500],
        joint_names=["thumb_bend", "thumb_rotate"],
        position_max=10000,
        driver_connected=True,
        banner="",
    )

    assert state["mode"] == "mirror"
    assert state["telemetry"]["gesture"] == "pinch"
    assert state["telemetry"]["gesture_label"] == "捏合"
    assert state["telemetry"]["inputs"]["thumb"] == 1.0
    assert state["telemetry"]["inputs"]["index"] == 0.0
    assert state["telemetry"]["inputs"]["middle"] == 0.6
    assert state["telemetry"]["inputs"]["thumb_spread"] == 0.75
    assert state["telemetry"]["joints"] == [
        {"name": "thumb_bend", "value": 2500.0, "ratio": 0.25},
        {"name": "thumb_rotate", "value": 12500.0, "ratio": 1.0},
    ]
    assert json.loads(json.dumps(state, ensure_ascii=False)) == state


def test_undetected_observation_reports_empty_input_activity():
    observation = SimpleNamespace(
        detected=False,
        gesture="none",
        curls={},
        thumb_spread=0.0,
    )

    state = build_runtime_state(
        mode="mirror",
        detection_enabled=False,
        sending=False,
        safety_state="safe_hold",
        observation=observation,
        display_inputs=None,
        positions=[0],
        joint_names=["thumb_bend"],
        position_max=10000,
        driver_connected=True,
        banner="SAFE POSE",
    )

    assert state["telemetry"]["detected"] is False
    assert set(state["telemetry"]["inputs"].values()) == {0.0}
    assert state["telemetry"]["banner"] == "SAFE POSE"
