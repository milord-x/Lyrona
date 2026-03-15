from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


LIBVLC_NAMES = (
    "libvlc.so.5",
    "libvlc.so",
    "libvlc.dylib",
    "libvlc.dll",
)

PLUGIN_DIR_CANDIDATES = (
    Path("vlc/plugins"),
    Path("plugins"),
)


def bundled_root() -> Optional[Path]:
    if not getattr(sys, "frozen", False):
        return None

    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        return Path(bundle_dir)

    return Path(sys.executable).resolve().parent


def _prepend_env_path(name: str, value: Path) -> None:
    existing = os.environ.get(name, "").strip()
    if not existing:
        os.environ[name] = str(value)
        return

    current_parts = [part for part in existing.split(os.pathsep) if part]
    if str(value) in current_parts:
        return

    os.environ[name] = os.pathsep.join([str(value), *current_parts])


def _find_first_existing(root: Path, candidates: tuple[Path, ...]) -> Optional[Path]:
    for candidate in candidates:
        resolved = root / candidate
        if resolved.exists():
            return resolved
    return None


def _find_libvlc_path(root: Path) -> Optional[Path]:
    for name in LIBVLC_NAMES:
        candidate = root / name
        if candidate.exists():
            return candidate
    return None


def configure_bundled_vlc() -> None:
    root = bundled_root()
    if root is None:
        return

    plugin_dir = _find_first_existing(root, PLUGIN_DIR_CANDIDATES)
    libvlc_path = _find_libvlc_path(root)

    if plugin_dir is not None:
        os.environ.setdefault("PYTHON_VLC_MODULE_PATH", str(plugin_dir))
        os.environ.setdefault("VLC_PLUGIN_PATH", str(plugin_dir))

    if libvlc_path is None:
        return

    os.environ.setdefault("PYTHON_VLC_LIB_PATH", str(libvlc_path))
    _prepend_env_path("LD_LIBRARY_PATH", libvlc_path.parent)
