from gesture_preset_controller import GesturePresetController


def test_triggers_a_preset_once_after_the_required_stable_frames():
    controller = GesturePresetController(hold_frames=3)
    presets = {"point": [0, 10000]}

    first = controller.update("point", detected=True, map_preset=presets.get)
    second = controller.update("point", detected=True, map_preset=presets.get)
    third = controller.update("point", detected=True, map_preset=presets.get)
    repeated = controller.update("point", detected=True, map_preset=presets.get)

    assert first.positions is None
    assert second.positions is None
    assert third.positions == [0, 10000]
    assert third.gesture == "point"
    assert repeated.positions is None


def test_tracking_gap_clears_stability_without_rearming_the_same_gesture():
    controller = GesturePresetController(hold_frames=2)
    presets = {"point": [0, 10000]}

    controller.update("point", detected=True, map_preset=presets.get)
    assert controller.update(
        "point", detected=True, map_preset=presets.get
    ).positions == [0, 10000]

    controller.update(None, detected=False, map_preset=presets.get)
    controller.update("point", detected=True, map_preset=presets.get)
    assert controller.update(
        "point", detected=True, map_preset=presets.get
    ).positions is None


def test_reset_rearms_the_last_triggered_gesture():
    controller = GesturePresetController(hold_frames=2)
    presets = {"point": [0, 10000]}

    controller.update("point", detected=True, map_preset=presets.get)
    controller.update("point", detected=True, map_preset=presets.get)
    controller.reset()

    controller.update("point", detected=True, map_preset=presets.get)
    assert controller.update(
        "point", detected=True, map_preset=presets.get
    ).positions == [0, 10000]
