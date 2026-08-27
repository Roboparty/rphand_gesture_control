from __future__ import annotations

import sys
from copy import deepcopy

import main as app
from drivers.lhandpro_driver import LHandProDriver
from drivers.sim_driver import SimHandDriver


class FakeRecognizer:
    def __init__(self, events: list[str]):
        self.events = events

    def close(self) -> None:
        self.events.append("recognizer.close")


class FakeMapper:
    joint_names = ["joint_1"]
    num_joints = 1


class FakeDriver:
    def __init__(self, events: list[str]):
        self.events = events
        self._connected = False

    def connect(self) -> bool:
        self._connected = True
        self.events.append("driver.connect")
        return True

    def disconnect(self) -> None:
        self._connected = False
        self.events.append("driver.disconnect")

    @property
    def is_connected(self) -> bool:
        return self._connected


class FailedDriver(FakeDriver):
    def connect(self) -> bool:
        self.events.append("driver.connect")
        return False


class ClosedCamera:
    def __init__(self, events: list[str]):
        self.events = events

    def set(self, _prop: int, _value: int) -> None:
        return None

    def isOpened(self) -> bool:
        return False

    def release(self) -> None:
        self.events.append("camera.release")


class FailedReadCamera(ClosedCamera):
    def isOpened(self) -> bool:
        return True

    def read(self):
        return False, None


class RecordingBridge:
    def __init__(self):
        self.events: list[dict] = []
        self.closed = False

    def publish_status(self, phase: str, *, state: str, **details) -> None:
        self.events.append(
            {"type": "status", "phase": phase, "state": state, **details}
        )

    def publish_ready(self) -> None:
        self.events.append({"type": "ready"})

    def publish_fatal(self, code: str, message: str, *, retryable: bool) -> None:
        self.events.append(
            {
                "type": "fatal",
                "code": code,
                "message": message,
                "retryable": retryable,
            }
        )

    def poll_key(self) -> int:
        return 0

    def close(self) -> None:
        self.closed = True


class PartialController:
    def __init__(self):
        self.stop_calls = 0
        self.disconnect_calls = 0

    def stop_motors(self) -> None:
        self.stop_calls += 1

    def disconnect(self) -> None:
        self.disconnect_calls += 1


class RecoverySdk:
    def __init__(self, *, fail_enable: bool = False):
        self.fail_enable = fail_enable
        self.clear_alarm_calls = []
        self.enable_calls = []

    def set_clear_alarm(self, motor_id: int) -> None:
        self.clear_alarm_calls.append(motor_id)

    def set_enable(self, motor_id: int, enabled: bool) -> None:
        self.enable_calls.append((motor_id, enabled))
        if self.fail_enable:
            raise RuntimeError("enable failed")


class RecoveryController:
    def __init__(self, sdk: RecoverySdk):
        self.sdk_handle = sdk


def test_camera_open_failure_still_closes_all_runtime_resources(monkeypatch):
    events: list[str] = []
    recognizer = FakeRecognizer(events)
    driver = FakeDriver(events)
    camera = ClosedCamera(events)

    monkeypatch.setattr(app, "GestureRecognizer", lambda **_kwargs: recognizer)
    monkeypatch.setattr(app, "GestureMapper", lambda *_args, **_kwargs: FakeMapper())
    monkeypatch.setattr(app, "make_driver", lambda _cfg, _names: driver)
    monkeypatch.setattr(app.cv2, "VideoCapture", lambda *_args, **_kwargs: camera)
    monkeypatch.setattr(
        app.cv2,
        "destroyAllWindows",
        lambda: events.append("windows.destroy"),
    )
    monkeypatch.setattr(app.os, "system", lambda _command: 0)
    monkeypatch.setattr(sys, "argv", ["main.py", "--driver", "sim"])

    result = app.main()

    assert result == 1
    assert events == [
        "driver.connect",
        "driver.disconnect",
        "camera.release",
        "recognizer.close",
        "windows.destroy",
    ]


def test_electron_camera_open_failure_reports_a_structured_error(monkeypatch):
    events: list[str] = []
    recognizer = FakeRecognizer(events)
    driver = FakeDriver(events)
    camera = ClosedCamera(events)
    bridge = RecordingBridge()

    monkeypatch.setattr(app, "GestureRecognizer", lambda **_kwargs: recognizer)
    monkeypatch.setattr(app, "GestureMapper", lambda *_args, **_kwargs: FakeMapper())
    monkeypatch.setattr(app, "make_driver", lambda _cfg, _names: driver)
    monkeypatch.setattr(app.cv2, "VideoCapture", lambda *_args, **_kwargs: camera)
    monkeypatch.setattr(app.cv2, "destroyAllWindows", lambda: None)
    monkeypatch.setattr(app, "ElectronBridge", lambda *_args, **_kwargs: bridge)
    monkeypatch.setattr(app.os, "system", lambda _command: 0)

    result = app.main(["--driver", "sim", "--electron-bridge"])

    assert result != 0
    assert bridge.events[-1] == {
        "type": "fatal",
        "code": "CAMERA_OPEN_FAILED",
        "message": "无法打开摄像头 0",
        "retryable": True,
    }
    assert bridge.closed is True


def test_electron_driver_failure_reports_a_structured_error(monkeypatch):
    events: list[str] = []
    bridge = RecordingBridge()

    monkeypatch.setattr(
        app,
        "GestureRecognizer",
        lambda **_kwargs: FakeRecognizer(events),
    )
    monkeypatch.setattr(app, "GestureMapper", lambda *_args, **_kwargs: FakeMapper())
    monkeypatch.setattr(app, "make_driver", lambda _cfg, _names: FailedDriver(events))
    monkeypatch.setattr(app.cv2, "destroyAllWindows", lambda: None)
    monkeypatch.setattr(app, "ElectronBridge", lambda *_args, **_kwargs: bridge)
    monkeypatch.setattr(app.os, "system", lambda _command: 0)

    result = app.main(["--driver", "sim", "--electron-bridge"])

    assert result != 0
    assert bridge.events[-1]["code"] == "DRIVER_CONNECT_FAILED"
    assert bridge.closed is True


def test_electron_camera_read_failure_is_not_a_successful_exit(monkeypatch):
    events: list[str] = []
    bridge = RecordingBridge()

    monkeypatch.setattr(app, "GestureRecognizer", lambda **_kwargs: FakeRecognizer(events))
    monkeypatch.setattr(app, "GestureMapper", lambda *_args, **_kwargs: FakeMapper())
    monkeypatch.setattr(app, "make_driver", lambda _cfg, _names: FakeDriver(events))
    monkeypatch.setattr(
        app.cv2,
        "VideoCapture",
        lambda *_args, **_kwargs: FailedReadCamera(events),
    )
    monkeypatch.setattr(app.cv2, "destroyAllWindows", lambda: None)
    monkeypatch.setattr(app, "ElectronBridge", lambda *_args, **_kwargs: bridge)
    monkeypatch.setattr(app.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(app.os, "system", lambda _command: 0)

    result = app.main(["--driver", "sim", "--electron-bridge"])

    assert result != 0
    assert {"type": "ready"} in bridge.events
    assert bridge.events[-1]["code"] == "CAMERA_READ_FAILED"


def test_electron_config_failure_is_reported_before_runtime_resources_start(monkeypatch):
    bridge = RecordingBridge()

    monkeypatch.setattr(
        app,
        "load_config",
        lambda _path: (_ for _ in ()).throw(ValueError("invalid yaml")),
    )
    monkeypatch.setattr(app, "ElectronBridge", lambda *_args, **_kwargs: bridge)
    monkeypatch.setattr(app.os, "system", lambda _command: 0)

    result = app.main(["--electron-bridge"])

    assert result != 0
    assert bridge.events[-1]["code"] == "CONFIG_ERROR"
    assert bridge.closed is True


def test_electron_empty_config_is_reported_as_a_config_error(monkeypatch):
    bridge = RecordingBridge()

    monkeypatch.setattr(app, "load_config", lambda _path: None)
    monkeypatch.setattr(app, "ElectronBridge", lambda *_args, **_kwargs: bridge)
    monkeypatch.setattr(app.os, "system", lambda _command: 0)

    result = app.main(["--driver", "sim", "--electron-bridge"])

    assert result != 0
    assert bridge.events[-1]["code"] == "CONFIG_ERROR"
    assert bridge.closed is True


def test_electron_invalid_numeric_config_is_reported_as_a_config_error(monkeypatch):
    bridge = RecordingBridge()
    config = deepcopy(app.load_config("config.yaml"))
    config["control"]["send_rate_hz"] = "fast"

    monkeypatch.setattr(app, "load_config", lambda _path: config)
    monkeypatch.setattr(app, "ElectronBridge", lambda *_args, **_kwargs: bridge)
    monkeypatch.setattr(app.os, "system", lambda _command: 0)

    result = app.main(["--electron-bridge"])

    assert result != 0
    assert bridge.events[-1]["code"] == "CONFIG_ERROR"


def test_electron_invalid_joint_config_is_reported_as_a_config_error(monkeypatch):
    bridge = RecordingBridge()
    config = deepcopy(app.load_config("config.yaml"))
    config["hand"]["joints"] = [{"name": "thumb_bend", "src": "thumb"}]

    monkeypatch.setattr(app, "load_config", lambda _path: config)
    monkeypatch.setattr(app, "ElectronBridge", lambda *_args, **_kwargs: bridge)
    monkeypatch.setattr(app.os, "system", lambda _command: 0)

    result = app.main(["--electron-bridge"])

    assert result != 0
    assert bridge.events[-1]["code"] == "CONFIG_ERROR"


def test_partial_lhandpro_connection_is_stopped_and_disconnected():
    controller = PartialController()
    driver = LHandProDriver(library_path="unused")
    driver._controller = controller
    driver._connected = False

    driver.disconnect()
    driver.disconnect()

    assert controller.stop_calls == 1
    assert controller.disconnect_calls == 1


def test_lhandpro_stop_is_idempotent():
    controller = PartialController()
    driver = LHandProDriver(library_path="unused")
    driver._controller = controller
    driver._connected = True

    driver.stop()
    driver.stop()

    assert controller.stop_calls == 1


def test_sim_driver_rejects_commands_after_stop():
    driver = SimHandDriver(["joint_1"])
    driver.connect()

    driver.stop()

    assert driver.set_joint_positions([5000.0]) is False


def test_sim_driver_can_resume_commands_after_controlled_recovery():
    driver = SimHandDriver(["joint_1"])
    driver.connect()
    driver.stop()

    assert driver.recover() is True
    assert driver.set_joint_positions([5000.0]) is True


def test_lhandpro_recovery_clears_alarm_and_reenables_all_motors():
    sdk = RecoverySdk()
    driver = LHandProDriver(library_path="unused")
    driver._controller = RecoveryController(sdk)
    driver._connected = True
    driver._stopped = True

    assert driver.recover() is True
    assert sdk.clear_alarm_calls == [0]
    assert sdk.enable_calls == [(0, True)]
    assert driver._stopped is False


def test_lhandpro_recovery_remains_stopped_when_reenable_fails():
    sdk = RecoverySdk(fail_enable=True)
    driver = LHandProDriver(library_path="unused")
    driver._controller = RecoveryController(sdk)
    driver._connected = True
    driver._stopped = True

    assert driver.recover() is False
    assert driver._stopped is True
