from __future__ import annotations

import pytest

from control_safety import TrackingState, TrackingWatchdog


def make_watchdog(*, lost_action: str = "open") -> TrackingWatchdog:
    return TrackingWatchdog(
        safe_positions=[0.0, 0.0],
        grace_period_s=0.3,
        safe_return_duration_s=1.0,
        lost_action=lost_action,
    )


def test_waits_without_command_before_the_first_hand_is_seen():
    decision = make_watchdog().update(None, now=0.0)

    assert decision.state is TrackingState.WAITING
    assert decision.target is None
    assert decision.should_stop is False


def test_explicit_safe_return_opens_even_before_a_hand_is_seen():
    watchdog = make_watchdog(lost_action="stop")

    assert watchdog.request_safe_return(now=0.0) is True
    decision = watchdog.update(None, now=0.1)

    assert decision.state in {TrackingState.SAFE_RETURN, TrackingState.SAFE_HOLD}
    assert decision.target == [0.0, 0.0]
    assert decision.should_stop is False


def test_resuming_detection_restores_the_configured_tracking_loss_policy():
    watchdog = make_watchdog(lost_action="stop")
    watchdog.request_safe_return(now=0.0)
    watchdog.update(None, now=0.1)

    assert watchdog.resume_tracking_policy(now=0.2) is True
    decision = watchdog.update(None, now=0.6)

    assert decision.state is TrackingState.STOPPED
    assert decision.should_stop is True


def test_short_tracking_gap_holds_the_last_sent_command():
    watchdog = make_watchdog()
    watchdog.update([8000.0, 4000.0], now=0.0)
    watchdog.note_output([7800.0, 3900.0])

    decision = watchdog.update(None, now=0.2)

    assert decision.state is TrackingState.GRACE
    assert decision.target == [7800.0, 3900.0]
    assert decision.should_stop is False


def test_long_tracking_loss_returns_smoothly_to_the_safe_pose():
    watchdog = make_watchdog()
    watchdog.update([8000.0, 4000.0], now=0.0)
    watchdog.note_output([8000.0, 4000.0])

    returning = watchdog.update(None, now=0.8)
    holding = watchdog.update(None, now=1.3)

    assert returning.state is TrackingState.SAFE_RETURN
    assert returning.target == pytest.approx([4000.0, 2000.0])
    assert holding.state is TrackingState.SAFE_HOLD
    assert holding.target == [0.0, 0.0]


def test_stop_strategy_requests_one_stop_after_the_grace_period():
    watchdog = make_watchdog(lost_action="stop")
    watchdog.update([8000.0, 4000.0], now=0.0)
    watchdog.note_output([8000.0, 4000.0])

    first = watchdog.update(None, now=0.4)
    second = watchdog.update(None, now=0.5)

    assert first.state is TrackingState.STOPPED
    assert first.target is None
    assert first.should_stop is True
    assert second.state is TrackingState.STOPPED
    assert second.should_stop is False


def test_reacquired_tracking_immediately_uses_the_new_observation():
    watchdog = make_watchdog()
    watchdog.update([8000.0, 4000.0], now=0.0)
    watchdog.note_output([8000.0, 4000.0])
    watchdog.update(None, now=0.8)

    decision = watchdog.update([2000.0, 1000.0], now=0.9)

    assert decision.state is TrackingState.TRACKING
    assert decision.target == [2000.0, 1000.0]


def test_visible_hand_without_a_new_gesture_keeps_the_last_output_alive():
    watchdog = make_watchdog()
    watchdog.update([8000.0, 4000.0], now=0.0)
    watchdog.note_output([8000.0, 4000.0])

    decision = watchdog.update(None, now=10.0, tracking_detected=True)

    assert decision.state is TrackingState.TRACKING
    assert decision.target == [8000.0, 4000.0]


def test_emergency_stop_is_latched_and_reported_once():
    watchdog = make_watchdog()

    assert watchdog.force_stop() is True
    assert watchdog.force_stop() is False

    first = watchdog.update([8000.0, 4000.0], now=0.0)
    second = watchdog.update([8000.0, 4000.0], now=0.1)

    assert first.state is TrackingState.STOPPED
    assert first.should_stop is True
    assert second.state is TrackingState.STOPPED
    assert second.should_stop is False
