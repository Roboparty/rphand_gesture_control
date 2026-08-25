from __future__ import annotations

import base64
import io
import json

import cv2
import numpy as np

from electron_bridge import ElectronBridge, parse_command_line


def test_parse_command_line_maps_only_existing_keyboard_actions():
    assert parse_command_line('{"type":"command","command":"quit"}') == ord("q")
    assert parse_command_line('{"type":"command","command":"cycle_mode"}') == ord("m")
    assert parse_command_line('{"type":"command","command":"toggle_pause"}') == ord(" ")
    assert parse_command_line('{"type":"command","command":"emergency_stop"}') == ord("e")
    assert parse_command_line('{"type":"command","command":"shell"}') is None
    assert parse_command_line('{"type":"frame","command":"quit"}') is None
    assert parse_command_line("not-json") is None


def test_bridge_publishes_a_valid_jpeg_message():
    output = io.StringIO()
    bridge = ElectronBridge(
        input_stream=io.StringIO(""),
        output_stream=output,
        max_fps=15.0,
        jpeg_quality=75,
    )
    frame = np.full((16, 24, 3), 127, dtype=np.uint8)

    assert bridge.submit_frame(frame, now=1.0) is True
    bridge.close()

    message = json.loads(output.getvalue().strip())
    assert message["type"] == "frame"
    assert message["sequence"] == 1
    encoded = np.frombuffer(base64.b64decode(message["jpeg"]), dtype=np.uint8)
    decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    assert decoded.shape == frame.shape


def test_bridge_limits_only_ui_frame_submissions():
    output = io.StringIO()
    bridge = ElectronBridge(io.StringIO(""), output, max_fps=10.0)
    frame = np.zeros((8, 8, 3), dtype=np.uint8)

    assert bridge.submit_frame(frame, now=1.00) is True
    assert bridge.submit_frame(frame, now=1.05) is False
    assert bridge.submit_frame(frame, now=1.10) is True
    bridge.close()
