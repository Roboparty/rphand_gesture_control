from pathlib import Path

import pytest
import yaml

from gesture_mapping import GestureMapper, project_normalized_value


JOINTS = [
    {"name": "index_finger", "src": "index", "range": [0, 10000]},
    {"name": "thumb_rotate", "src": "thumb_spread", "range": [0, 10000]},
]

CALIBRATION = {
    "index": {"open": 0.25},
    "thumb_spread": {"open": 0.16},
}

PINCH_JOINTS = [
    {"name": "thumb_bend", "src": "thumb", "range": [0, 10000]},
    {"name": "thumb_rotate", "src": "thumb_spread", "range": [0, 10000]},
    {"name": "index_finger", "src": "index", "range": [0, 10000]},
    {"name": "middle_finger", "src": "middle", "range": [0, 10000]},
]

PINCH_ASSIST = {
    "enabled": True,
    "targets": {"thumb": 0.8, "thumb_spread": 0.6, "index": 0.85},
}

RETARGET_JOINTS = [
    {"name": "index_finger", "src": "index", "range": [0, 10000]},
    {"name": "middle_finger", "src": "middle", "range": [0, 10000]},
    {"name": "ring_finger", "src": "ring", "range": [0, 10000]},
    {"name": "pinky_finger", "src": "pinky", "range": [0, 10000]},
]

FINGER_RETARGETING = {
    "enabled": True,
    "fusion": "max",
    "calibration": {
        "middle": {"open": 0.0, "closed": 0.5},
        "ring": {"open": 0.0, "closed": 0.5},
        "pinky": {"open": 0.0, "closed": 0.5},
    },
}


def test_project_normalized_value_clips_to_the_joint_range():
    joint = {"name": "finger", "range": [1000, 9000]}

    assert project_normalized_value(-0.5, joint) == 1000
    assert project_normalized_value(0.25, joint) == 3000
    assert project_normalized_value(1.5, joint) == 9000


def test_open_baseline_maps_to_fully_open_and_closed_endpoint_is_preserved():
    mapper = GestureMapper(JOINTS, {}, CALIBRATION)

    assert mapper.map_mirror({"index": 0.25, "thumb_spread": 0.16}) == [0, 0]
    assert mapper.map_mirror({"index": 1.0, "thumb_spread": 1.0}) == [10000, 10000]


def test_values_between_open_baseline_and_one_are_renormalized():
    mapper = GestureMapper(JOINTS, {}, CALIBRATION)

    corrected = mapper.calibrate_inputs({"index": 0.625, "thumb_spread": 0.58})

    assert corrected["index"] == pytest.approx(0.5)
    assert corrected["thumb_spread"] == pytest.approx(0.5)


def test_calibration_clips_tracking_noise_outside_valid_range():
    mapper = GestureMapper(JOINTS, {}, CALIBRATION)

    corrected = mapper.calibrate_inputs({"index": 0.1, "thumb_spread": 1.2})

    assert corrected == {"index": 0.0, "thumb_spread": 1.0}


def test_missing_calibration_keeps_legacy_mapping_unchanged():
    mapper = GestureMapper(JOINTS, {})

    assert mapper.map_mirror({"index": 0.2, "thumb_spread": 0.3}) == [2000, 3000]


def test_invalid_open_baseline_is_rejected():
    with pytest.raises(ValueError, match="open 必须小于 1"):
        GestureMapper(JOINTS, {}, {"index": {"open": 1.0}})


def test_real_hardware_open_hand_sample_maps_all_six_joints_to_zero():
    config_path = Path(__file__).resolve().parents[1] / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    mapper = GestureMapper(
        config["hand"]["joints"],
        config["presets"],
        config["hand"]["input_calibration"],
    )
    open_sample = {
        "thumb": 0.2057,
        "thumb_spread": 0.1617,
        "index": 0.2576,
        "middle": 0.2607,
        "ring": 0.1893,
        "pinky": 0.2296,
    }

    assert mapper.map_mirror(open_sample) == [0.0] * 6


def test_real_hardware_thumb_and_index_closed_samples_reach_full_travel():
    config_path = Path(__file__).resolve().parents[1] / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    mapper = GestureMapper(
        config["hand"]["joints"],
        config["presets"],
        config["hand"]["input_calibration"],
    )
    sample = {
        "thumb": 0.446,
        "thumb_spread": 0.1617,
        "index": 0.672,
        "middle": 0.2607,
        "ring": 0.1893,
        "pinky": 0.2296,
    }

    positions = mapper.map_mirror(sample)

    assert positions[0] == pytest.approx(10000.0)
    assert positions[2] == pytest.approx(10000.0)
    assert positions[1] == pytest.approx(0.0)
    assert positions[3:] == pytest.approx([0.0, 0.0, 0.0])


def test_real_hardware_pinky_only_closed_sample_reaches_full_travel():
    config_path = Path(__file__).resolve().parents[1] / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    mapper = GestureMapper(
        config["hand"]["joints"],
        config["presets"],
        config["hand"]["input_calibration"],
        config["hand"]["pinch_assist"],
        config["hand"]["finger_retargeting"],
    )
    open_sample = {
        "thumb": 0.2057,
        "thumb_spread": 0.1617,
        "index": 0.2576,
        "middle": 0.2607,
        "ring": 0.1893,
        "pinky": 0.2296,
    }
    # 由真机截图中的 6480 反推：0.03 + 0.648 * (0.42 - 0.03)。
    observed_retractions = {"middle": 0.0, "ring": 0.0, "pinky": 0.28272}

    positions = mapper.map_mirror(
        open_sample,
        finger_retractions=observed_retractions,
    )

    assert positions[:5] == pytest.approx([0.0] * 5)
    assert positions[5] >= 9800


def test_real_hardware_ring_only_closed_sample_reaches_full_travel():
    config_path = Path(__file__).resolve().parents[1] / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    mapper = GestureMapper(
        config["hand"]["joints"],
        config["presets"],
        config["hand"]["input_calibration"],
        config["hand"]["pinch_assist"],
        config["hand"]["finger_retargeting"],
    )
    open_sample = {
        "thumb": 0.2057,
        "thumb_spread": 0.1617,
        "index": 0.2576,
        "middle": 0.2607,
        "ring": 0.1893,
        "pinky": 0.2296,
    }
    # 由真机截图中的 6904 反推：0.03 + 0.6904 * (0.46 - 0.03)。
    observed_retractions = {"middle": 0.0, "ring": 0.326872, "pinky": 0.0}

    positions = mapper.map_mirror(
        open_sample,
        finger_retractions=observed_retractions,
    )

    assert positions[:4] == pytest.approx([0.0] * 4)
    assert positions[4] >= 9800
    assert positions[5] == pytest.approx(0.0)


def test_pinch_assist_progressively_enhances_only_configured_sources():
    mapper = GestureMapper(PINCH_JOINTS, {}, {}, PINCH_ASSIST)
    inputs = {"thumb": 0.0, "thumb_spread": 0.0, "index": 0.0, "middle": 0.2}

    half = mapper.map_mirror(inputs, pinch_strength=0.5)
    full = mapper.map_mirror(inputs, pinch_strength=1.0)

    assert half == pytest.approx([4000, 3000, 4250, 2000])
    assert full == pytest.approx([8000, 6000, 8500, 2000])


def test_disabled_pinch_assist_preserves_plain_continuous_mapping():
    mapper = GestureMapper(
        PINCH_JOINTS,
        {},
        {},
        {"enabled": False, "targets": PINCH_ASSIST["targets"]},
    )
    inputs = {"thumb": 0.1, "thumb_spread": 0.2, "index": 0.3, "middle": 0.4}

    assert mapper.map_mirror(inputs, pinch_strength=1.0) == pytest.approx(
        [1000, 2000, 3000, 4000]
    )


def test_pinch_assist_rejects_targets_outside_normalized_range():
    with pytest.raises(ValueError, match="捏合辅助目标必须在 0 到 1 之间"):
        GestureMapper(
            PINCH_JOINTS,
            {},
            {},
            {"enabled": True, "targets": {"thumb": 1.1}},
        )


def test_fingertip_retraction_boosts_only_configured_fingers():
    mapper = GestureMapper(
        RETARGET_JOINTS,
        {},
        {},
        {},
        FINGER_RETARGETING,
    )
    curls = {"index": 0.6, "middle": 0.2, "ring": 0.3, "pinky": 0.4}
    retractions = {"middle": 0.25, "ring": 0.05, "pinky": 0.4}

    positions = mapper.map_mirror(curls, finger_retractions=retractions)

    assert positions == pytest.approx([6000, 5000, 3000, 8000])


def test_disabled_finger_retargeting_preserves_legacy_mapping():
    config = {**FINGER_RETARGETING, "enabled": False}
    mapper = GestureMapper(RETARGET_JOINTS, {}, {}, {}, config)
    curls = {"index": 0.6, "middle": 0.2, "ring": 0.3, "pinky": 0.4}

    positions = mapper.map_mirror(
        curls,
        finger_retractions={"middle": 0.5, "ring": 0.5, "pinky": 0.5},
    )

    assert positions == pytest.approx([6000, 2000, 3000, 4000])


def test_missing_retraction_data_falls_back_to_legacy_mapping():
    mapper = GestureMapper(RETARGET_JOINTS, {}, {}, {}, FINGER_RETARGETING)
    curls = {"index": 0.6, "middle": 0.2, "ring": 0.3, "pinky": 0.4}

    assert mapper.map_mirror(curls) == pytest.approx([6000, 2000, 3000, 4000])


def test_finger_retargeting_clips_noise_beyond_calibrated_endpoints():
    mapper = GestureMapper(RETARGET_JOINTS, {}, {}, {}, FINGER_RETARGETING)
    curls = {"index": 0.0, "middle": 0.0, "ring": 0.0, "pinky": 0.0}

    positions = mapper.map_mirror(
        curls,
        finger_retractions={"middle": -0.2, "ring": 0.8, "pinky": 4.0},
    )

    assert positions == pytest.approx([0, 0, 10000, 10000])


def test_invalid_finger_retraction_calibration_is_rejected():
    config = {
        "enabled": True,
        "calibration": {"pinky": {"open": 0.4, "closed": 0.2}},
    }

    with pytest.raises(ValueError, match="回缩 closed 必须大于 open"):
        GestureMapper(RETARGET_JOINTS, {}, {}, {}, config)
