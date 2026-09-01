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


def test_linux_lhandpro_library_falls_back_to_bundled_so(monkeypatch, tmp_path):
    bundle_dir = tmp_path / "_internal"
    windows_library = bundle_dir / "vendor" / "bin" / "LHandProLib.dll"
    linux_library = (
        bundle_dir / "vendor" / "lib" / "linux" / "x86_64" / "libLHandProLib.so"
    )
    windows_library.parent.mkdir(parents=True)
    windows_library.write_bytes(b"MZ")
    linux_library.parent.mkdir(parents=True)
    linux_library.write_bytes(b"ELF")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle_dir), raising=False)

    assert app_paths.resolve_lhandpro_library_path(
        "vendor/bin/LHandProLib.dll",
        platform="linux",
    ) == str(linux_library)


def test_windows_lhandpro_library_keeps_existing_configured_dll(monkeypatch, tmp_path):
    bundle_dir = tmp_path / "_internal"
    windows_library = bundle_dir / "vendor" / "bin" / "LHandProLib.dll"
    windows_library.parent.mkdir(parents=True)
    windows_library.write_bytes(b"MZ")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle_dir), raising=False)

    assert app_paths.resolve_lhandpro_library_path(
        "vendor/bin/LHandProLib.dll",
        platform="win32",
    ) == str(windows_library)
