"""Build JSON-safe runtime telemetry for external user interfaces."""

from __future__ import annotations

from typing import Mapping, Sequence

from gesture_recognizer import FINGERS, GESTURE_NAMES_CN, HandObservation


def _unit(value: object) -> float:
    return min(max(float(value), 0.0), 1.0)


def build_runtime_state(
    *,
    mode: str,
    retargeting_strategy: str,
    retargeting_effective: str,
    retargeting_fallback: str,
    detection_enabled: bool,
    sending: bool,
    safety_state: str,
    observation: HandObservation,
    display_inputs: Mapping[str, float] | None,
    positions: Sequence[float],
    joint_names: Sequence[str],
    position_max: float,
    driver_connected: bool,
    banner: str = "",
) -> dict[str, object]:
    """Return the control state and renderer-owned HUD data for one frame."""

    detected = bool(observation.detected)
    source_inputs = display_inputs or {}
    curls = getattr(observation, "curls", {})
    inputs = {
        finger: _unit(source_inputs.get(finger, curls.get(finger, 0.0)))
        if detected
        else 0.0
        for finger in FINGERS
    }
    inputs["thumb_spread"] = (
        _unit(source_inputs.get("thumb_spread", observation.thumb_spread))
        if detected
        else 0.0
    )

    maximum = max(float(position_max), 1.0)
    joints = [
        {
            "name": str(name),
            "value": float(position),
            "ratio": _unit(float(position) / maximum),
        }
        for name, position in zip(joint_names, positions)
    ]
    gesture = str(getattr(observation, "gesture", "none"))
    return {
        "mode": str(mode),
        "retargeting_strategy": str(retargeting_strategy),
        "retargeting_effective": str(retargeting_effective),
        "retargeting_fallback": str(retargeting_fallback),
        "detection_enabled": bool(detection_enabled),
        "sending": bool(sending),
        "safety_state": str(safety_state),
        "telemetry": {
            "detected": detected,
            "driver_connected": bool(driver_connected),
            "gesture": gesture,
            "gesture_label": GESTURE_NAMES_CN.get(gesture, gesture),
            "inputs": inputs,
            "joints": joints,
            "banner": str(banner),
        },
    }
