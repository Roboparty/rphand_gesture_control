from __future__ import annotations

import sys

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


class ClosedCamera:
    def __init__(self, events: list[str]):
        self.events = events

    def set(self, _prop: int, _value: int) -> None:
        return None

    def isOpened(self) -> bool:
        return False

    def release(self) -> None:
        self.events.append("camera.release")


class PartialController:
    def __init__(self):
        self.stop_calls = 0
        self.disconnect_calls = 0

    def stop_motors(self) -> None:
        self.stop_calls += 1

    def disconnect(self) -> None:
        self.disconnect_calls += 1


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
