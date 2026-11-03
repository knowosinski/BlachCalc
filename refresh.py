"""Porównanie builda lokalnego z instalacją i uruchamianie jego instalatora."""
import hashlib
import os
import subprocess
import sys
from pathlib import Path

from version import INSTALLER_ASSET_NAME

UPDATED_FLAG = "--updated"
BUILD_ENV = "BLACHCALC_BUILD_DIR"
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def build_directory_candidates() -> list[Path]:
    candidates: list[Path] = []
    from_env = os.environ.get(BUILD_ENV, "").strip()
    if from_env:
        candidates.append(Path(from_env))
    start = Path(sys.executable if is_frozen() else __file__).resolve().parent
    for folder in (start, *list(start.parents)[:6]):
        candidates.append(folder / "dist" / "BlachCalc")
    candidates.append(
        Path.home() / "Documents" / "GitHub" / "BlachCalc" / "dist" / "BlachCalc"
    )
    return candidates


def find_local_build(extra: str = "") -> Path | None:
    """Znajduje folder aplikacji zbudowanej przez PyInstaller."""
    paths = ([Path(extra)] if extra else []) + build_directory_candidates()
    for path in paths:
        if (path / "BlachCalc.exe").is_file():
            return path
    return None


def compare_application_files(build: Path, installed: Path) -> list[str]:
    """Zwraca pliki dodane lub zmienione w buildzie względem instalacji."""
    build = build.resolve()
    installed = installed.resolve()
    if build == installed:
        raise ValueError("Folder builda i folder instalacji nie mogą być takie same.")
    if not (build / "BlachCalc.exe").is_file():
        raise ValueError(f"Folder nie zawiera aplikacji BlachCalc.exe: {build}")
    if not (installed / "BlachCalc.exe").is_file():
        raise ValueError(f"Nie znaleziono zainstalowanej aplikacji: {installed}")

    installed_files = {
        path.relative_to(installed).as_posix().casefold(): path
        for path in installed.rglob("*")
        if path.is_file()
    }
    changed: list[str] = []
    for source in build.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(build)
        destination = installed_files.get(relative.as_posix().casefold())
        if destination is None:
            changed.append(relative.as_posix())
            continue
        source_hash = hashlib.sha256(source.read_bytes()).digest()
        installed_hash = hashlib.sha256(destination.read_bytes()).digest()
        if source_hash != installed_hash:
            changed.append(relative.as_posix())
    return sorted(changed, key=str.casefold)


def source_files_newer_than_build(build: Path) -> list[Path]:
    """Finds repository Python files newer than the local packaged executable."""
    source_directory = build.parent.parent
    executable = build / "BlachCalc.exe"
    if not executable.is_file():
        return []
    build_timestamp = executable.stat().st_mtime
    return sorted(
        (
            source
            for source in source_directory.glob("*.py")
            if source.is_file() and source.stat().st_mtime > build_timestamp
        ),
        key=lambda path: path.name.casefold(),
    )


def installer_for_build(build: Path) -> Path | None:
    """Znajduje instalator wygenerowany obok wskazanego folderu builda."""
    candidates: list[Path] = []
    for folder in (build.parent.parent, build.parent):
        candidates.extend((
            folder / "release" / INSTALLER_ASSET_NAME,
            folder / INSTALLER_ASSET_NAME,
        ))
    existing = [path for path in candidates if path.is_file()]
    return max(existing, key=lambda path: path.stat().st_mtime, default=None)


def installer_command(installer: Path) -> list[str]:
    return [str(installer), "/SILENT", "/NORESTART", "/CLOSEAPPLICATIONS", "/FORCECLOSEAPPLICATIONS"]


def _spawn(command: list[str]) -> None:
    subprocess.Popen(
        command,
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )


def launch_installer(installer: Path) -> None:
    _spawn(installer_command(installer))
