"""Electron bridge protocol without robot-control responsibilities."""

from __future__ import annotations

import base64
import json
import queue
import threading
import time
from typing import IO, Optional

import cv2
import numpy as np


COMMAND_KEYS = {
    "quit": ord("q"),
    "cycle_mode": ord("m"),
    "toggle_pause": ord(" "),
    "emergency_stop": ord("e"),
}


def parse_command_line(line: str) -> Optional[int]:
    """Return the existing keyboard code for one whitelisted JSON command."""

    try:
        payload = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict) or payload.get("type") != "command":
        return None
    return COMMAND_KEYS.get(payload.get("command"))


class ElectronBridge:
    """Move GUI I/O off the robot-control loop through bounded queues."""

    def __init__(
        self,
        input_stream: IO[str],
        output_stream: IO[str],
        max_fps: float = 15.0,
        jpeg_quality: int = 75,
    ) -> None:
        self._input_stream = input_stream
        self._output_stream = output_stream
        self._frame_interval = 1.0 / max(float(max_fps), 1.0)
        self._jpeg_quality = int(jpeg_quality)
        self._commands: queue.Queue[int] = queue.Queue()
        self._frames: queue.Queue[np.ndarray] = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        self._last_submitted_at = float("-inf")
        self._sequence = 0
        self._command_thread = threading.Thread(
            target=self._read_commands,
            name="electron-command-reader",
            daemon=True,
        )
        self._frame_thread = threading.Thread(
            target=self._publish_frames,
            name="electron-frame-publisher",
            daemon=True,
        )
        self._command_thread.start()
        self._frame_thread.start()

    def poll_key(self) -> int:
        try:
            return self._commands.get_nowait()
        except queue.Empty:
            return 0

    def submit_frame(self, frame: np.ndarray, *, now: float | None = None) -> bool:
        submitted_at = time.monotonic() if now is None else float(now)
        if submitted_at - self._last_submitted_at < self._frame_interval:
            return False
        self._last_submitted_at = submitted_at
        latest = frame.copy()
        try:
            self._frames.put_nowait(latest)
        except queue.Full:
            try:
                self._frames.get_nowait()
            except queue.Empty:
                pass
            self._frames.put_nowait(latest)
        return True

    def close(self) -> None:
        self._stop.set()
        self._frame_thread.join(timeout=2.0)

    def _read_commands(self) -> None:
        for line in self._input_stream:
            if self._stop.is_set():
                break
            key = parse_command_line(line)
            if key is not None:
                self._commands.put(key)

    def _publish_frames(self) -> None:
        while not self._stop.is_set() or not self._frames.empty():
            try:
                frame = self._frames.get(timeout=0.05)
            except queue.Empty:
                continue
            ok, encoded = cv2.imencode(
                ".jpg",
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality],
            )
            if not ok:
                continue
            self._sequence += 1
            message = {
                "type": "frame",
                "sequence": self._sequence,
                "jpeg": base64.b64encode(encoded).decode("ascii"),
            }
            try:
                self._output_stream.write(
                    json.dumps(message, separators=(",", ":")) + "\n"
                )
                self._output_stream.flush()
            except (BrokenPipeError, OSError, ValueError):
                self._stop.set()
                return
