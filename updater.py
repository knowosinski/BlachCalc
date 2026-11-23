"""Lokalne porównywanie źródeł i instalowanie przebudowanej aplikacji."""
import hashlib
import json
import subprocess
from pathlib import Path
from tkinter import messagebox
from typing import Any, Callable

from app_paths import resource_path

SOURCE_MANIFEST_NAME = "source_manifest.json"
UPDATED_FLAG = "--updated"
BUILD_TIMEOUT_SECONDS = 3600
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200

_BUILD_INPUTS = (
    "BlachCalc.spec",
    "Build-Windows.ps1",
    "BlachCalc-Setup.iss",
    "requirements.txt",
    "requirements-build.txt",
    "logo.png",
    "BlachCalc.ico",
)


class UpdateError(Exception):
    pass


def get_source_files_hash(source_root: Path) -> dict[str, str]:
    """Zwraca SHA-256 źródeł i plików wejściowych procesu budowania."""
    root = source_root.expanduser().resolve()
    files = {path for path in root.glob("*.py") if path.is_file()}
    files.update(
        root / name
        for name in _BUILD_INPUTS
        if (root / name).is_file()
    )
    hashes: dict[str, str] = {}
    for path in sorted(files, key=lambda item: item.name.casefold()):
        try:
            relative_path = path.relative_to(root).as_posix()
            hashes[relative_path] = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            raise UpdateError(f"Nie można odczytać pliku źródłowego:\n{path}\n\n{error}") from error
    return hashes


def write_source_manifest(
    source_root: Path | None = None,
    manifest_path: Path | None = None,
) -> Path:
    """Zapisuje bazowe hasze źródeł do dołączenia w nowym buildzie."""
    root = (source_root or Path.cwd()).expanduser().resolve()
    output = manifest_path or root / "build" / SOURCE_MANIFEST_NAME
    manifest = {
        "source_root": str(root),
        "files": get_source_files_hash(root),
    }
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as error:
        raise UpdateError(f"Nie można zapisać manifestu źródeł:\n{output}\n\n{error}") from error
    return output


def load_source_manifest() -> tuple[Path, dict[str, str]]:
    manifest_path = resource_path(SOURCE_MANIFEST_NAME)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        raise UpdateError(
            f"Nie można odczytać manifestu lokalnych źródeł:\n{manifest_path}\n\n{error}"
        ) from error
    if not isinstance(manifest, dict):
        raise UpdateError("Manifest lokalnych źródeł ma nieprawidłowy format.")
    source_root = manifest.get("source_root")
    files = manifest.get("files")
    if not isinstance(source_root, str) or not source_root.strip():
        raise UpdateError("Manifest nie zawiera ścieżki lokalnego repozytorium.")
    if not isinstance(files, dict) or any(
        not isinstance(name, str) or not isinstance(digest, str)
        for name, digest in files.items()
    ):
        raise UpdateError("Manifest nie zawiera prawidłowych sum kontrolnych.")
    return Path(source_root), files


def find_changed_source_files(
    source_root: Path,
    baseline_hashes: dict[str, str],
) -> list[str]:
    root = source_root.expanduser().resolve()
    if not root.is_dir():
        raise UpdateError(f"Nie znaleziono lokalnego repozytorium:\n{root}")
    current_hashes = get_source_files_hash(root)
    return sorted(
        (
            name
            for name in baseline_hashes.keys() | current_hashes.keys()
            if baseline_hashes.get(name) != current_hashes.get(name)
        ),
        key=str.casefold,
    )


def check_and_update(
    parent: Any = None,
    before_install: Callable[[], bool] | None = None,
    notify_if_current: bool = True,
) -> bool:
    title = "BlachCalc — aktualizacja"
    try:
        source_root, baseline_hashes = load_source_manifest()
        changed_files = find_changed_source_files(source_root, baseline_hashes)
    except UpdateError as error:
        messagebox.showerror(title, str(error), parent=parent)
        return False

    if not changed_files:
        if notify_if_current:
            messagebox.showinfo(
                title,
                "Lokalne pliki aplikacji są aktualne.",
                parent=parent,
            )
        return False

    changed_count = len(changed_files)
    if not messagebox.askyesno(
        title,
        f"Wykryto {changed_count} zmienionych, dodanych lub usuniętych "
        f"plików źródłowych w lokalnym repozytorium.\n\n"
        "Przebudować i zainstalować aplikację? Dane i oferty zostaną zachowane.",
        parent=parent,
    ):
        return False

    if before_install is not None and not before_install():
        return False

    try:
        rebuild_application(source_root)
    except UpdateError as error:
        messagebox.showerror(title, str(error), parent=parent)
        return False
    except OSError as error:
        messagebox.showerror(title, f"Nie można przebudować aplikacji:\n{error}", parent=parent)
        return False
    return True


def rebuild_application(source_root: Path) -> None:
    """Buduje lokalny instalator i uruchamia go, aby zastąpił zainstalowane pliki."""
    root = source_root.expanduser().resolve()
    build_script = root / "Build-Windows.ps1"
    if not build_script.is_file():
        raise UpdateError(f"Nie znaleziono skryptu budowania:\n{build_script}")

    try:
        result = subprocess.run(
            [
                "powershell",
                "-ExecutionPolicy", "Bypass",
                "-File", str(build_script),
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=BUILD_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise UpdateError("Przebudowa przekroczyła limit czasu (60 minut).") from error

    if result.returncode != 0:
        build_output = "\n".join(
            part.strip() for part in (result.stdout, result.stderr) if part and part.strip()
        )
        details = f"\n\nSzczegóły:\n{build_output[-4000:]}" if build_output else ""
        raise UpdateError(f"Przebudowa nie powiodła się.{details}")

    installer = root / "release" / "BlachCalc-Setup.exe"
    if not installer.is_file():
        raise UpdateError(f"Nie znaleziono instalatora po przebudowie:\n{installer}")
    launch_installer(installer)


def launch_installer(installer_path: Path) -> None:
    try:
        subprocess.Popen(
            [
                str(installer_path),
                "/SILENT",
                "/NORESTART",
                "/CLOSEAPPLICATIONS",
            ],
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
        )
    except OSError as error:
        raise UpdateError(f"Nie można uruchomić instalatora:\n{error}") from error
