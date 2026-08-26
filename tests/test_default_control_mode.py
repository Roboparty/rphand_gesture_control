from pathlib import Path

import yaml


def test_default_control_mode_is_mirror():
    config_path = Path(__file__).resolve().parents[1] / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert config["control"]["mode"] == "mirror"
