"""Application resource lifecycle helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Optional


class RuntimeResources:
    """Own runtime resources and close them once in a deterministic order."""

    def __init__(self, destroy_windows: Callable[[], None]):
        self.driver: Optional[Any] = None
        self.camera: Optional[Any] = None
        self.recognizer: Optional[Any] = None
        self._destroy_windows = destroy_windows
        self._closed = False

    def __enter__(self) -> "RuntimeResources":
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        resources = (
            (self.driver, "disconnect"),
            (self.camera, "release"),
            (self.recognizer, "close"),
        )
        for resource, method_name in resources:
            if resource is None:
                continue
            try:
                getattr(resource, method_name)()
            except Exception as exc:
                print(f"[Cleanup] {method_name} 失败: {exc}")

        try:
            self._destroy_windows()
        except Exception as exc:
            print(f"[Cleanup] destroyAllWindows 失败: {exc}")

