from __future__ import annotations

import pytest

from control_safety import CommandLimiter


def make_limiter(**overrides) -> CommandLimiter:
    options = {
        "joint_ranges": [(0.0, 10000.0), (10000.0, 0.0)],
        "initial_positions": [5000.0, 5000.0],
        "deadband": 0.0,
        "max_step": 20000.0,
        "max_velocity": 20000.0,
        "max_acceleration": 20000.0,
        "initial_time": 0.0,
    }
    options.update(overrides)
    return CommandLimiter(**options)


def test_clamps_targets_to_each_joint_range_even_when_range_is_reversed():
    limiter = make_limiter()

    output = limiter.limit([-100.0, 12000.0], now=1.0)

    assert output == [0.0, 10000.0]


def test_deadband_holds_the_previous_output():
    limiter = make_limiter(deadband=10.0)

    output = limiter.limit([5005.0, 4992.0], now=1.0)

    assert output == [5000.0, 5000.0]


def test_velocity_limit_caps_distance_per_second():
    limiter = make_limiter(
        initial_positions=[0.0, 0.0],
        max_velocity=100.0,
        max_acceleration=10000.0,
    )

    first = limiter.limit([1000.0, 1000.0], now=1.0)
    second = limiter.limit([1000.0, 1000.0], now=2.0)

    assert first == pytest.approx([100.0, 100.0])
    assert second == pytest.approx([200.0, 200.0])


def test_acceleration_limit_ramps_velocity_between_commands():
    limiter = make_limiter(
        initial_positions=[0.0, 0.0],
        max_velocity=1000.0,
        max_acceleration=50.0,
    )

    first = limiter.limit([1000.0, 1000.0], now=1.0)
    second = limiter.limit([1000.0, 1000.0], now=2.0)

    assert first == pytest.approx([50.0, 50.0])
    assert second == pytest.approx([150.0, 150.0])


def test_per_command_step_limit_is_applied_after_velocity_limits():
    limiter = make_limiter(
        initial_positions=[0.0, 0.0],
        max_step=40.0,
        max_velocity=10000.0,
        max_acceleration=10000.0,
    )

    output = limiter.limit([1000.0, 1000.0], now=1.0)

    assert output == pytest.approx([40.0, 40.0])


def test_rejects_a_target_with_the_wrong_joint_count():
    limiter = make_limiter()

    with pytest.raises(ValueError, match="expected 2 targets"):
        limiter.limit([1000.0], now=1.0)
