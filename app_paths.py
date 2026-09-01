"""应用路径解析: 兼容源码运行和 PyInstaller 打包运行。"""

import os
import sys


def app_dir() -> str:
    """应用资源目录: 兼容源码运行和 PyInstaller one-folder 包。"""
    if getattr(sys, "frozen", False):
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            return os.path.abspath(bundle_dir)
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def resolve_app_path(path: str) -> str:
    """相对路径一律相对应用根目录解析, 与当前工作目录无关。"""
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(app_dir(), path))


def resolve_lhandpro_library_path(
    configured_path: str,
    platform: str | None = None,
) -> str:
    """Resolve the native hand SDK without changing the Windows config.

    Windows installations keep using the configured DLL. Linux ignores a
    bundled Windows DLL and selects the architecture-specific shared object
    staged by the Docker packaging step.
    """

    configured = resolve_app_path(configured_path)
    target_platform = platform or sys.platform

    if target_platform.startswith("linux"):
        # The one-folder package can contain both platform SDKs. Do not let an
        # existing Windows DLL short-circuit Linux shared-object resolution.
        if os.path.exists(configured) and not configured.lower().endswith(".dll"):
            return configured
        for relative_path in (
            "vendor/lib/linux/x86_64/libLHandProLib.so",
            "vendor/lib/libLHandProLib.so",
        ):
            candidate = resolve_app_path(relative_path)
            if os.path.exists(candidate):
                return candidate

        return configured

    if os.path.exists(configured):
        return configured

    return configured
