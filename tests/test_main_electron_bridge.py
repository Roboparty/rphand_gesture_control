from __future__ import annotations

from copy import deepcopy

import numpy as np

import main as app


class Observation:
    detected = True
    curls = {"thumb": 0.5, "index": 0.5}
    thumb_spread = 0.0
    gesture = "unknown"


class Recognizer:
    def process(self, _frame):
        return Observation()

    def draw_landmarks(self, _frame, _observation):
        return None

    def close(self):
        return None


class Mapper:
    joint_names = ["joint_1"]
    num_joints = 1

    def map_mirror(self, _values):
        return [5000.0]


class Camera:
    def set(self, _prop, _value):
        return None

    def isOpened(self):
        return True

    def read(self):
        return True, np.zeros((16, 24, 3), dtype=np.uint8)

    def release(self):
        return None


class Driver:
    def __init__(self):
        self.stop_calls = 0
        self.stopped = False
        self.connected = False

    def connect(self):
        self.connected = True
        return True

    def disconnect(self):
        self.connected = False

    def stop(self):
        if self.stopped:
            return
        self.stopped = True
        self.stop_calls += 1

    def set_joint_positions(self, _positions, speed=None):
        return True

    def get_state(self):
        return {"joint_1": 5000.0}

    @property
    def is_connected(self):
        return self.connected


class FakeBridge:
    def __init__(self):
        self.keys = iter([ord("e"), ord("q")])
        self.frames = 0
        self.closed = False

    def submit_frame(self, _frame, *, now=None):
        self.frames += 1
        return True

    def poll_key(self):
        return next(self.keys)

    def close(self):
        self.closed = True


def test_electron_bridge_reuses_the_existing_emergency_stop_branch(monkeypatch):
    config = deepcopy(app.load_config("config.yaml"))
    config["camera"]["mirror"] = False
    config["control"]["mode"] = "mirror"
    config["control"]["send_rate_hz"] = 1000
    config["hand"]["joints"] = [
        {"name": "joint_1", "src": "index", "range": [0, 10000]}
    ]
    driver = Driver()
    bridge = FakeBridge()

    monkeypatch.setattr(app, "load_config", lambda _path: config)
    monkeypatch.setattr(app, "GestureRecognizer", lambda **_kwargs: Recognizer())
    monkeypatch.setattr(app, "GestureMapper", lambda *_args, **_kwargs: Mapper())
    monkeypatch.setattr(app, "make_driver", lambda _cfg, _names: driver)
    monkeypatch.setattr(app.cv2, "VideoCapture", lambda *_args: Camera())
    monkeypatch.setattr(
        app.cv2,
        "imshow",
        lambda *_args: (_ for _ in ()).throw(AssertionError("imshow called")),
    )
    monkeypatch.setattr(
        app.cv2,
        "waitKey",
        lambda *_args: (_ for _ in ()).throw(AssertionError("waitKey called")),
    )
    monkeypatch.setattr(app.cv2, "destroyAllWindows", lambda: None)
    monkeypatch.setattr(app, "draw_hud", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "ElectronBridge", lambda *_args, **_kwargs: bridge, raising=False)
    monkeypatch.setattr(app.os, "system", lambda _command: 0)

    result = app.main(["--driver", "sim", "--electron-bridge"])

    assert result == 0
    assert bridge.frames == 2
    assert bridge.closed is True
    assert driver.stop_calls == 1
