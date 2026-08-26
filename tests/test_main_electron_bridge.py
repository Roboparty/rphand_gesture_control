from __future__ import annotations

from copy import deepcopy

import numpy as np

import main as app


class Observation:
    detected = True
    curls = {"thumb": 0.5, "index": 0.5}
    thumb_spread = 0.0
    pinch_strength = 0.0
    gesture = "unknown"


class Recognizer:
    def __init__(self):
        self.process_calls = 0

    def process(self, _frame):
        self.process_calls += 1
        return Observation()

    def draw_landmarks(self, _frame, _observation):
        return None

    def close(self):
        return None


class Mapper:
    joint_names = ["joint_1"]
    num_joints = 1

    def calibrate_inputs(self, values):
        return dict(values)

    def map_mirror(self, _values, pinch_strength=0.0):
        return [5000.0]

    def map_preset(self, _gesture):
        return None


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
        self.recover_calls = 0
        self.stopped = False
        self.connected = False
        self.commands = []

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

    def recover(self):
        self.recover_calls += 1
        if not self.connected:
            return False
        self.stopped = False
        return True

    def set_joint_positions(self, positions, speed=None):
        self.commands.append(list(positions))
        return True

    def get_state(self):
        return {"joint_1": 5000.0}

    @property
    def is_connected(self):
        return self.connected


class FakeBridge:
    def __init__(self, keys=None):
        self.keys = iter(keys or [ord("e"), ord("q")])
        self.frames = 0
        self.states = []
        self.closed = False

    def submit_frame(self, _frame, *, now=None, state=None):
        self.frames += 1
        self.states.append(None if state is None else dict(state))
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
    monkeypatch.setattr(
        app,
        "draw_hud",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Electron mode must not composite the OpenCV HUD")
        ),
    )
    monkeypatch.setattr(app, "ElectronBridge", lambda *_args, **_kwargs: bridge, raising=False)
    monkeypatch.setattr(app.os, "system", lambda _command: 0)

    result = app.main(["--driver", "sim", "--electron-bridge"])

    assert result == 0
    assert bridge.frames == 2
    assert bridge.closed is True
    assert driver.stop_calls == 1
    assert bridge.states[0]["telemetry"]["gesture"] == "unknown"
    assert bridge.states[0]["telemetry"]["joints"][0]["value"] == 5000.0


def _run_bridge_session(
    monkeypatch,
    keys,
    *,
    monotonic_times=None,
    safe_return_duration_s=1.2,
):
    config = deepcopy(app.load_config("config.yaml"))
    config["camera"]["mirror"] = False
    config["control"]["mode"] = "mirror"
    config["control"]["send_rate_hz"] = 1000
    config["hand"]["joints"] = [
        {"name": "joint_1", "src": "index", "range": [0, 10000]}
    ]
    config["safety"] = {
        "tracking": {
            "grace_period_s": 0.0,
            "lost_action": "open",
            "safe_return_duration_s": safe_return_duration_s,
        }
    }
    driver = Driver()
    bridge = FakeBridge(keys)
    recognizer = Recognizer()

    monkeypatch.setattr(app, "load_config", lambda _path: config)
    monkeypatch.setattr(app, "GestureRecognizer", lambda **_kwargs: recognizer)
    monkeypatch.setattr(app, "GestureMapper", lambda *_args, **_kwargs: Mapper())
    monkeypatch.setattr(app, "make_driver", lambda _cfg, _names: driver)
    monkeypatch.setattr(app.cv2, "VideoCapture", lambda *_args: Camera())
    monkeypatch.setattr(app.cv2, "destroyAllWindows", lambda: None)
    monkeypatch.setattr(
        app,
        "draw_hud",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Electron mode must not composite the OpenCV HUD")
        ),
    )
    monkeypatch.setattr(app, "ElectronBridge", lambda *_args, **_kwargs: bridge, raising=False)
    monkeypatch.setattr(app.os, "system", lambda _command: 0)
    if monotonic_times is not None:
        times = iter(monotonic_times)
        monkeypatch.setattr(app.time, "monotonic", lambda: next(times))

    result = app.main(["--driver", "sim", "--electron-bridge"])
    return result, bridge, recognizer, driver


def test_electron_bridge_can_select_an_explicit_mode(monkeypatch):
    result, bridge, _recognizer, _driver = _run_bridge_session(
        monkeypatch,
        [app.KEY_MODE_GESTURE, ord("q")],
    )

    assert result == 0
    assert [state["mode"] for state in bridge.states] == ["mirror", "gesture"]


def test_disabling_detection_keeps_frames_but_skips_recognition(monkeypatch):
    result, bridge, recognizer, _driver = _run_bridge_session(
        monkeypatch,
        [app.KEY_TOGGLE_DETECTION, 0, ord("q")],
    )

    assert result == 0
    assert bridge.frames == 3
    assert recognizer.process_calls == 1
    assert [state["detection_enabled"] for state in bridge.states] == [
        True,
        False,
        False,
    ]


def test_disabling_detection_returns_to_safe_open_even_while_paused(monkeypatch):
    result, _bridge, _recognizer, driver = _run_bridge_session(
        monkeypatch,
        [ord(" "), app.KEY_TOGGLE_DETECTION, 0, ord("q")],
        monotonic_times=[0.0, 1.0, 2.0, 3.0],
        safe_return_duration_s=0.0,
    )

    assert result == 0
    assert driver.commands[0] == [5000.0]
    assert driver.commands[-1] == [0.0]


def test_electron_recovery_disables_tracking_and_returns_to_safe_open(monkeypatch):
    result, bridge, recognizer, driver = _run_bridge_session(
        monkeypatch,
        [ord("e"), 0, 0x1005, 0, ord("q")],
        monotonic_times=[0.0, 1.0, 2.0, 3.0, 4.0],
        safe_return_duration_s=0.0,
    )

    assert result == 0
    assert driver.recover_calls == 1
    assert driver.commands[0] == [5000.0]
    assert driver.commands[-1] == [0.0]
    assert recognizer.process_calls == 3
    assert [state.get("safety_state") for state in bridge.states] == [
        "tracking",
        "stopped",
        "stopped",
        "safe_hold",
        "safe_hold",
    ]
    assert bridge.states[-1]["detection_enabled"] is False
    assert bridge.states[-1]["sending"] is False
