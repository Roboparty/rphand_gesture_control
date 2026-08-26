from rock_paper_scissors import RockPaperScissorsController


POSES = {
    "fist": [1, 1],
    "open_palm": [2, 2],
    "victory": [3, 3],
}


def map_preset(gesture):
    return POSES.get(gesture)


def test_stable_player_gesture_triggers_the_winning_counter_pose():
    controller = RockPaperScissorsController(hold_frames=3, cooldown_s=3.0)

    assert controller.update("fist", True, 10.0, map_preset).positions is None
    assert controller.update("fist", True, 10.1, map_preset).positions is None
    result = controller.update("fist", True, 10.2, map_preset)

    assert result.positions == POSES["open_palm"]
    assert result.log_message == "[猜拳] 你出石头, 我出布, 我赢了"
    assert controller.banner == "You: ROCK   Me: PAPER   ->  I WIN!"


def test_same_gesture_requires_rearming_and_cooldown_before_repeating():
    controller = RockPaperScissorsController(hold_frames=2, cooldown_s=3.0)

    controller.update("victory", True, 1.0, map_preset)
    assert controller.update("victory", True, 1.1, map_preset).positions == POSES["fist"]
    assert controller.update("victory", True, 4.5, map_preset).positions is None

    controller.update(None, False, 4.6, map_preset)
    controller.update("victory", True, 4.7, map_preset)
    assert controller.update("victory", True, 4.8, map_preset).positions == POSES["fist"]


def test_reset_clears_transient_ui_without_discarding_cooldown():
    controller = RockPaperScissorsController(hold_frames=2, cooldown_s=3.0)

    controller.update("open_palm", True, 5.0, map_preset)
    controller.update("open_palm", True, 5.1, map_preset)
    assert controller.banner

    controller.reset()

    assert controller.banner == ""
    controller.update("open_palm", True, 5.2, map_preset)
    assert controller.update("open_palm", True, 5.3, map_preset).positions is None


def test_missing_preset_does_not_consume_the_round():
    controller = RockPaperScissorsController(hold_frames=1, cooldown_s=3.0)

    result = controller.update("fist", True, 2.0, lambda _gesture: None)
    assert result.positions is None
    assert controller.banner == ""

    result = controller.update("fist", True, 2.1, map_preset)
    assert result.positions == POSES["open_palm"]
