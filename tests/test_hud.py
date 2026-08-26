from types import SimpleNamespace

import numpy as np

from main import draw_hud


def test_electron_hud_uses_the_same_opaque_light_panel_over_any_frame():
    dark_frame = np.zeros((480, 800, 3), dtype=np.uint8)
    bright_frame = np.full((480, 800, 3), 120, dtype=np.uint8)
    observation = SimpleNamespace(detected=False, gesture="none")

    for frame in (dark_frame, bright_frame):
        draw_hud(
            frame,
            observation,
            [0],
            ["joint_1"],
            "mirror",
            True,
            True,
            light_panel=True,
        )

    dark_panel_pixel = dark_frame[-20, -20]
    bright_panel_pixel = bright_frame[-20, -20]
    assert np.array_equal(dark_panel_pixel, bright_panel_pixel)
    assert float(dark_panel_pixel.mean()) > 220
