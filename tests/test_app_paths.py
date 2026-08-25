from __future__ import annotations

import sys

import app_paths


def test_packaged_app_dir_uses_pyinstaller_bundle_directory(monkeypatch, tmp_path):
    bundle_dir = tmp_path / "_internal"
    executable = tmp_path / "RP-Hand.exe"

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle_dir), raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))

    assert app_paths.app_dir() == str(bundle_dir)
    assert app_paths.resolve_app_path("config.yaml") == str(bundle_dir / "config.yaml")
