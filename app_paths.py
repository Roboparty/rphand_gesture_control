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
