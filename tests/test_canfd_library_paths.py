from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import threading

from vendor import canfd_lib


def test_linux_canbus_candidates_prefer_the_bundled_architecture_directory(tmp_path):
    vendor_dir = tmp_path / "vendor"

    candidates = canfd_lib._linux_library_candidates(
        "libcanbus.so",
        module_dir=str(vendor_dir),
    )

    assert candidates[0] == str(
        vendor_dir / "lib" / "linux" / "x86_64" / "libcanbus.so"
    )
    assert candidates[-1] == "libcanbus.so"


class _FakeFunction:
    def __init__(self, result=0):
        self.result = result
        self.calls = []
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        self.calls.append(args)
        return self.result


class _FakeCanBusLibrary:
    def __init__(self):
        self.CAN_ScanDevice = _FakeFunction()
        self.CAN_OpenDevice = _FakeFunction()
        self.CAN_CloseDevice = _FakeFunction()
        self.CANFD_Init = _FakeFunction()
        self.CANFD_Transmit = _FakeFunction(result=1)
        self.CANFD_Receive = _FakeFunction()


def _load_linux_canfd_module(monkeypatch):
    if not sys.platform.startswith("win"):
        return canfd_lib

    module_path = Path(canfd_lib.__file__)
    spec = importlib.util.spec_from_file_location(
        "vendor.canfd_lib_linux_test",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setattr(sys, "platform", "linux")
    spec.loader.exec_module(module)
    return module


def test_linux_vendor_driver_binds_the_official_channel_aware_abi(monkeypatch):
    module = _load_linux_canfd_module(monkeypatch)
    fake_library = _FakeCanBusLibrary()
    driver = object.__new__(module._LinuxLibCanBusCANFD)
    driver._libcan = fake_library

    driver._bind_libcanbus_symbols()

    assert len(fake_library.CANFD_Init.argtypes) == 3
    assert len(fake_library.CANFD_Transmit.argtypes) == 5
    assert len(fake_library.CANFD_Receive.argtypes) == 5


def test_linux_vendor_driver_passes_channel_to_init_send_and_receive(monkeypatch):
    module = _load_linux_canfd_module(monkeypatch)
    fake_library = _FakeCanBusLibrary()
    driver = object.__new__(module._LinuxLibCanBusCANFD)
    driver._libcan = fake_library
    driver._is_connected = False
    driver._receive_thread = None
    driver._receive_stop_event = threading.Event()
    driver._receive_callback = None

    assert driver.connect(device_index=2, channel_index=3)
    assert fake_library.CANFD_Init.calls[0][0:2] == (2, 3)

    assert driver.send(0x123, b"\x01\x02")
    assert fake_library.CANFD_Transmit.calls[0][0:2] == (2, 3)

    original_receive = fake_library.CANFD_Receive

    def receive_once(*args):
        original_receive(*args)
        driver._receive_stop_event.set()
        return 0

    fake_library.CANFD_Receive = receive_once
    driver._receive_loop()
    assert original_receive.calls[0][0:2] == (2, 3)
