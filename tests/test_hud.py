from types import SimpleNamespace

import numpy as np

from hud_renderer import draw_hud


def test_tui_hud_keeps_the_existing_dark_translucent_side_panel():
    frame = np.full((480, 800, 3), 120, dtype=np.uint8)
    observation = SimpleNamespace(detected=False, gesture="none")

    draw_hud(
        frame,
        observation,
        [0],
        ["joint_1"],
        "mirror",
        True,
        True,
    )

    assert 60 < float(frame[-20, -20].mean()) < 90
    assert np.array_equal(frame[-20, 20], np.array([120, 120, 120]))
