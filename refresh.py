"""Odświeżanie aplikacji: zamknięcie, okno aktualizacji, instalacja z lokalnych plików i ponowne uruchomienie."""
import os
import subprocess
import sys
from pathlib import Path

from version import INSTALLER_ASSET_NAME

UPDATED_FLAG = "--updated"
INSTALLER_ENV = "BLACHCALC_INSTALLER"
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def installer_candidates() -> list[Path]:
    candidates: list[Path] = []
    from_env = os.environ.get(INSTALLER_ENV, "").strip()
    if from_env:
        candidates.append(Path(from_env))
    start = Path(sys.executable if is_frozen() else __file__).resolve().parent
    for folder in (start, *list(start.parents)[:5]):
        candidates.append(folder / "release" / INSTALLER_ASSET_NAME)
        candidates.append(folder / INSTALLER_ASSET_NAME)
    candidates.append(Path.home() / "Documents" / "GitHub" / "BlachCalc" / "release" / INSTALLER_ASSET_NAME)
    return candidates


def find_local_installer(extra: str = "") -> Path | None:
    """Zwraca najświeższy znaleziony instalator z bieżącymi plikami aplikacji."""
    paths = ([Path(extra)] if extra else []) + installer_candidates()
    existing = [path for path in paths if path.is_file()]
    return max(existing, key=lambda path: path.stat().st_mtime, default=None)


def installer_command(installer: Path) -> list[str]:
    return [str(installer), "/SILENT", "/NORESTART", "/CLOSEAPPLICATIONS", "/FORCECLOSEAPPLICATIONS"]


def restart_command() -> list[str]:
    arguments = [argument for argument in sys.argv[1:] if argument != UPDATED_FLAG]
    base = [sys.executable] if is_frozen() else [sys.executable, str(Path(sys.argv[0]).resolve())]
    return [*base, *arguments, UPDATED_FLAG]


def _spawn(command: list[str]) -> None:
    subprocess.Popen(
        command,
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )


def launch_installer(installer: Path) -> None:
    _spawn(installer_command(installer))


def launch_restart() -> None:
    _spawn(restart_command())
