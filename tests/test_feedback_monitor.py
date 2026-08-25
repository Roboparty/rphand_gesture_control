from __future__ import annotations

from control_safety import FeedbackMonitor


def make_monitor(**overrides) -> FeedbackMonitor:
    options = {
        "max_send_failures": 2,
        "max_feedback_failures": 2,
        "position_error_limit": 1000.0,
        "position_error_timeout_s": 0.5,
    }
    options.update(overrides)
    return FeedbackMonitor(**options)


def test_consecutive_send_failures_trip_but_a_success_resets_the_count():
    monitor = make_monitor()

    assert monitor.note_send(False) is None
    assert monitor.note_send(True) is None
    assert monitor.note_send(False) is None
    fault = monitor.note_send(False)

    assert fault is not None
    assert fault.code == "send_failure"


def test_missing_feedback_trips_after_the_configured_number_of_reads():
    monitor = make_monitor()

    assert monitor.evaluate([100.0], None, alarms=None, now=0.0) is None
    fault = monitor.evaluate([100.0], None, alarms=None, now=0.1)

    assert fault is not None
    assert fault.code == "feedback_missing"


def test_motor_alarm_trips_immediately():
    monitor = make_monitor()

    fault = monitor.evaluate(
        target=[100.0, 100.0],
        actual=[100.0, 100.0],
        alarms=[0, 4],
        now=0.0,
    )

    assert fault is not None
    assert fault.code == "motor_alarm"


def test_position_error_must_persist_before_it_trips():
    monitor = make_monitor()

    assert monitor.evaluate([5000.0], [0.0], alarms=[0], now=0.0) is None
    assert monitor.evaluate([5000.0], [0.0], alarms=[0], now=0.4) is None
    fault = monitor.evaluate([5000.0], [0.0], alarms=[0], now=0.5)

    assert fault is not None
    assert fault.code == "position_error"


def test_healthy_feedback_resets_the_position_error_timer():
    monitor = make_monitor()

    assert monitor.evaluate([5000.0], [0.0], alarms=[0], now=0.0) is None
    assert monitor.evaluate([5000.0], [5000.0], alarms=[0], now=0.4) is None
    assert monitor.evaluate([5000.0], [0.0], alarms=[0], now=0.8) is None
    assert monitor.evaluate([5000.0], [0.0], alarms=[0], now=1.2) is None


def test_first_fault_is_latched():
    monitor = make_monitor(max_send_failures=1)

    first = monitor.note_send(False)
    second = monitor.evaluate([0.0], [0.0], alarms=[7], now=1.0)

    assert first is not None
    assert second is first
    assert monitor.fault is first
