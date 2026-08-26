from pathlib import Path

import pytest
import yaml

from gesture_mapping import GestureMapper


JOINTS = [
    {"name": "index_finger", "src": "index", "range": [0, 10000]},
    {"name": "thumb_rotate", "src": "thumb_spread", "range": [0, 10000]},
]

CALIBRATION = {
    "index": {"open": 0.25},
    "thumb_spread": {"open": 0.16},
}


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
