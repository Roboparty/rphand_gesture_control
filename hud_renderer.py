"""OpenCV HUD used by the standalone TUI window."""

from __future__ import annotations

import cv2

from gesture_recognizer import FINGERS, GESTURE_NAMES_CN, HandObservation


def draw_hud(
    frame,
    obs: HandObservation,
    positions,
    joint_names,
    mode,
    sending,
    driver_ok,
    pos_max=10000,
    *,
    banner="",
    display_inputs=None,
):
    """Draw the legacy dark telemetry panel for direct OpenCV use."""

    h, w = frame.shape[:2]
    if banner:
        cv2.rectangle(frame, (0, h - 50), (w, h), (20, 20, 20), -1)
        cv2.putText(
            frame,
            banner,
            (16, h - 16),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 255, 255),
            2,
        )

    panel_w = min(320, w)
    overlay = frame.copy()
    cv2.rectangle(overlay, (w - panel_w, 0), (w, h), (30, 30, 30), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
    primary = (255, 255, 0)
    text = (255, 255, 255)
    muted = (180, 180, 180)
    track = (80, 80, 80)
    success = (0, 255, 0)
    danger = (0, 0, 255)
    finger_fill = (0, 200, 255)
    thumb_fill = (255, 160, 0)
    joint_fill = (0, 255, 120)

    x0 = w - panel_w + 16
    y = 34
    cv2.putText(
        frame,
        f"Mode: {mode}",
        (x0, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        primary,
        2,
    )
    y += 30
    status = "SENDING" if sending else "PAUSED (Space)"
    color = success if (sending and driver_ok) else danger
    cv2.putText(
        frame,
        status,
        (x0, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        color,
        2,
    )
    y += 30
    gesture_cn = GESTURE_NAMES_CN.get(obs.gesture, obs.gesture)
    cv2.putText(
        frame,
        f"Gesture: {obs.gesture}",
        (x0, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        text,
        1,
    )
    y += 24
    cv2.putText(
        frame,
        f"({gesture_cn})",
        (x0, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        muted,
        1,
    )
    y += 30

    if obs.detected:
        display_inputs = display_inputs or {}
        for finger in FINGERS:
            value = display_inputs.get(finger, obs.curls[finger])
            cv2.putText(
                frame,
                finger,
                (x0, y + 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                muted,
                1,
            )
            bar_x = x0 + 70
            cv2.rectangle(frame, (bar_x, y - 8), (bar_x + 150, y + 6), track, -1)
            cv2.rectangle(
                frame,
                (bar_x, y - 8),
                (bar_x + int(150 * value), y + 6),
                finger_fill,
                -1,
            )
            y += 22
        value = display_inputs.get("thumb_spread", obs.thumb_spread)
        cv2.putText(
            frame,
            "th_roll",
            (x0, y + 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            muted,
            1,
        )
        bar_x = x0 + 70
        cv2.rectangle(frame, (bar_x, y - 8), (bar_x + 150, y + 6), track, -1)
        cv2.rectangle(
            frame,
            (bar_x, y - 8),
            (bar_x + int(150 * value), y + 6),
            thumb_fill,
            -1,
        )
        y += 22
    y += 10

    cv2.putText(
        frame,
        "Hand joints:",
        (x0, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        text,
        1,
    )
    y += 22
    for name, position in zip(joint_names, positions):
        fraction = min(max(position / pos_max, 0.0), 1.0)
        cv2.putText(
            frame,
            name[:12],
            (x0, y + 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            muted,
            1,
        )
        bar_x = x0 + 110
        cv2.rectangle(frame, (bar_x, y - 8), (bar_x + 110, y + 6), track, -1)
        cv2.rectangle(
            frame,
            (bar_x, y - 8),
            (bar_x + int(110 * fraction), y + 6),
            joint_fill,
            -1,
        )
        cv2.putText(
            frame,
            str(int(position)),
            (bar_x + 115, y + 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            muted,
            1,
        )
        y += 20
