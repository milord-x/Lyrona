from __future__ import annotations

import platform
import shutil
import tarfile
from pathlib import Path

import PyInstaller.__main__


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_ROOT = PROJECT_ROOT / "dist"
BUILD_ROOT = PROJECT_ROOT / "build" / "pyinstaller"
APP_NAME = "lyrona"

LIBVLC_CANDIDATES = (
    Path("/usr/lib/libvlc.so.5"),
    Path("/usr/lib/x86_64-linux-gnu/libvlc.so.5"),
    Path("/usr/lib/aarch64-linux-gnu/libvlc.so.5"),
    Path("/usr/lib/libvlc.so"),
)

LIBVLCCORE_CANDIDATES = (
    Path("/usr/lib/libvlccore.so.9"),
    Path("/usr/lib/x86_64-linux-gnu/libvlccore.so.9"),
    Path("/usr/lib/aarch64-linux-gnu/libvlccore.so.9"),
    Path("/usr/lib/libvlccore.so"),
)

PLUGIN_DIR_CANDIDATES = (
    Path("/usr/lib/vlc/plugins"),
    Path("/usr/lib/x86_64-linux-gnu/vlc/plugins"),
    Path("/usr/lib/aarch64-linux-gnu/vlc/plugins"),
)


def find_first_existing(candidates: tuple[Path, ...]) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    joined = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"Required VLC runtime asset not found. Tried: {joined}")


def normalized_arch() -> str:
    machine = platform.machine().lower()
    aliases = {
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }
    return aliases.get(machine, machine)


def release_name() -> str:
    system = platform.system().lower()
    if system != "linux":
        raise RuntimeError("The standalone build script currently supports Linux only.")
    return f"{APP_NAME}-linux-{normalized_arch()}"


def clean_output(paths: list[Path]) -> None:
    for path in paths:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


def remove_vlc_plugin_cache(root: Path) -> None:
    for plugin_cache in root.rglob("plugins.dat"):
        plugin_cache.unlink()


def build_app() -> Path:
    libvlc_path = find_first_existing(LIBVLC_CANDIDATES)
    libvlccore_path = find_first_existing(LIBVLCCORE_CANDIDATES)
    plugin_dir = find_first_existing(PLUGIN_DIR_CANDIDATES)

    app_dir = DIST_ROOT / APP_NAME

    clean_output([app_dir, BUILD_ROOT])

    PyInstaller.__main__.run(
        [
            "--noconfirm",
            "--clean",
            "--onedir",
            "--name",
            APP_NAME,
            "--distpath",
            str(DIST_ROOT),
            "--workpath",
            str(BUILD_ROOT / "work"),
            "--specpath",
            str(BUILD_ROOT / "spec"),
            "--collect-submodules",
            "mutagen",
            "--add-binary",
            f"{libvlc_path}:.",
            "--add-binary",
            f"{libvlccore_path}:.",
            "--add-data",
            f"{plugin_dir}:vlc/plugins",
            str(PROJECT_ROOT / "lyrona.py"),
        ]
    )

    remove_vlc_plugin_cache(app_dir)
    return app_dir


def stage_release(app_dir: Path) -> Path:
    target_dir = DIST_ROOT / release_name()
    archive_path = DIST_ROOT / f"{target_dir.name}.tar.gz"

    clean_output([target_dir, archive_path])
    shutil.copytree(app_dir, target_dir)
    remove_vlc_plugin_cache(target_dir)

    readme_path = target_dir / "README.txt"
    readme_path.write_text(
        "\n".join(
            [
                "Lyrona standalone build",
                "",
                "Run:",
                "  ./lyrona --help",
                "",
                "This build bundles Python, project dependencies, libvlc, and VLC plugins.",
                "Your machine still needs a working Linux audio stack.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(target_dir, arcname=target_dir.name)

    return archive_path


def main() -> int:
    app_dir = build_app()
    archive_path = stage_release(app_dir)

    print(f"Built app directory: {app_dir}")
    print(f"Built release archive: {archive_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
