from __future__ import annotations

from copy import deepcopy

import numpy as np

import main as app


class FakeObservation:
    def __init__(self, detected: bool):
        self.detected = detected
        self.curls = {"thumb": 0.8, "index": 0.4}
        self.thumb_spread = 0.0
        self.gesture = "unknown"


class SequenceRecognizer:
    def __init__(self):
        self._observations = iter(
            [FakeObservation(True), FakeObservation(False), FakeObservation(False)]
        )

    def process(self, _frame):
        return next(self._observations)

    def draw_landmarks(self, _frame, _observation) -> None:
        return None

    def close(self) -> None:
        return None


class TwoJointMapper:
    joint_names = ["joint_1", "joint_2"]
    num_joints = 2

    def map_mirror(self, _values):
        return [8000.0, 4000.0]

    def map_preset(self, _gesture):
        return None


class RecordingDriver:
    def __init__(self):
        self.commands: list[list[float]] = []
        self.stop_calls = 0
        self._connected = False

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def stop(self) -> None:
        self.stop_calls += 1

    def set_joint_positions(self, positions, speed=None) -> bool:
        self.commands.append(list(positions))
        return True

    def get_state(self):
        positions = self.commands[-1] if self.commands else [0.0, 0.0]
        return dict(zip(TwoJointMapper.joint_names, positions))

    @property
    def is_connected(self) -> bool:
        return self._connected


class ThreeFrameCamera:
    def set(self, _prop, _value) -> None:
        return None

    def isOpened(self) -> bool:
        return True

    def read(self):
        return True, np.zeros((8, 8, 3), dtype=np.uint8)

    def release(self) -> None:
        return None


def test_main_sends_safe_return_commands_when_tracking_is_lost(monkeypatch):
    config = deepcopy(app.load_config("config.yaml"))
    config["camera"]["mirror"] = False
    config["control"]["mode"] = "mirror"
    config["control"]["send_rate_hz"] = 1000
    config["hand"]["joints"] = [
        {"name": "joint_1", "src": "thumb", "range": [0, 10000]},
        {"name": "joint_2", "src": "index", "range": [0, 10000]},
    ]
    config["safety"] = {
        "tracking": {
            "grace_period_s": 0.3,
            "lost_action": "open",
            "safe_return_duration_s": 1.0,
        }
    }
    driver = RecordingDriver()
    keys = iter([0, 0, ord("q")])
    monotonic_times = iter([0.0, 0.8, 1.3])

    monkeypatch.setattr(app, "load_config", lambda _path: config)
    monkeypatch.setattr(app, "GestureRecognizer", lambda **_kwargs: SequenceRecognizer())
    monkeypatch.setattr(app, "GestureMapper", lambda *_args, **_kwargs: TwoJointMapper())
    monkeypatch.setattr(app, "make_driver", lambda _cfg, _names: driver)
    monkeypatch.setattr(app.cv2, "VideoCapture", lambda *_args: ThreeFrameCamera())
    monkeypatch.setattr(app.cv2, "waitKey", lambda _delay: next(keys))
    monkeypatch.setattr(app.cv2, "imshow", lambda *_args: None)
    monkeypatch.setattr(app.cv2, "destroyAllWindows", lambda: None)
    monkeypatch.setattr(app, "draw_hud", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app.time, "monotonic", lambda: next(monotonic_times))
    monkeypatch.setattr(app.os, "system", lambda _command: 0)

    result = app.main(["--driver", "sim"])

    assert result == 0
    assert driver.commands == [
        [8000.0, 4000.0],
        [4000.0, 2000.0],
        [0.0, 0.0],
    ]
