"""Aktualizacja BlachCalc z najnowszego wydania (GitHub Releases)."""
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from tkinter import messagebox
from typing import Any

from version import APP_VERSION, GITHUB_REPO, INSTALLER_ASSET_NAME

LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
REQUEST_TIMEOUT_SECONDS = 20
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200


class UpdateError(Exception):
    pass


class ReleaseInfo:
    def __init__(self, version: str, download_url: str, sha256: str | None) -> None:
        self.version = version
        self.download_url = download_url
        self.sha256 = sha256


def parse_version(text: str) -> tuple[int, ...]:
    match = re.search(r"\d+(?:\.\d+)*", text or "")
    if not match:
        raise ValueError(f"Nieprawidłowy numer wersji: {text!r}")
    return tuple(int(part) for part in match.group(0).split("."))


def is_newer(candidate: str, current: str) -> bool:
    left, right = parse_version(candidate), parse_version(current)
    width = max(len(left), len(right))
    pad = lambda parts: parts + (0,) * (width - len(parts))
    return pad(left) > pad(right)


def release_from_payload(payload: dict[str, Any]) -> ReleaseInfo:
    version = str(payload.get("tag_name") or "")
    try:
        parse_version(version)
    except ValueError as error:
        raise UpdateError("Najnowsze wydanie nie ma poprawnego numeru wersji.") from error
    for asset in payload.get("assets") or []:
        if asset.get("name") == INSTALLER_ASSET_NAME and asset.get("browser_download_url"):
            digest = str(asset.get("digest") or "")
            sha256 = digest.split(":", 1)[1].lower() if digest.lower().startswith("sha256:") else None
            return ReleaseInfo(version.lstrip("vV"), asset["browser_download_url"], sha256)
    raise UpdateError(f"Najnowsze wydanie nie zawiera pliku {INSTALLER_ASSET_NAME}.")


def fetch_latest_release() -> ReleaseInfo:
    request = urllib.request.Request(
        LATEST_RELEASE_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "BlachCalc-Updater"},
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.load(response)
    except Exception as error:
        raise UpdateError(f"Nie można sprawdzić aktualizacji (brak internetu lub wydania na GitHub):\n{error}") from error
    return release_from_payload(payload)


def download_installer(release: ReleaseInfo) -> Path:
    target_dir = Path(tempfile.mkdtemp(prefix="blachcalc-update-"))
    target = target_dir / INSTALLER_ASSET_NAME
    request = urllib.request.Request(release.download_url, headers={"User-Agent": "BlachCalc-Updater"})
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response, target.open("wb") as output:
            while chunk := response.read(1024 * 256):
                digest.update(chunk)
                output.write(chunk)
    except Exception as error:
        raise UpdateError(f"Nie udało się pobrać instalatora:\n{error}") from error
    if release.sha256 and digest.hexdigest().lower() != release.sha256:
        target.unlink(missing_ok=True)
        raise UpdateError("Pobrany instalator ma nieprawidłową sumę kontrolną. Aktualizację przerwano.")
    if target.stat().st_size == 0:
        raise UpdateError("Pobrany instalator jest pusty.")
    return target


def launch_installer(installer: Path) -> None:
    subprocess.Popen(
        [str(installer), "/SILENT", "/NORESTART", "/CLOSEAPPLICATIONS", "/FORCECLOSEAPPLICATIONS"],
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )


def check_and_update(parent: Any = None) -> bool:
    """Pyta o aktualizację i uruchamia instalator. Zwraca True, gdy aplikacja ma się zamknąć."""
    title = "BlachCalc — aktualizacja"
    try:
        release = fetch_latest_release()
        if not is_newer(release.version, APP_VERSION):
            messagebox.showinfo(title, f"Masz najnowszą wersję ({APP_VERSION}).", parent=parent)
            return False
        if not messagebox.askyesno(
            title,
            f"Dostępna jest wersja {release.version} (zainstalowana: {APP_VERSION}).\n\n"
            "Pobrać i zainstalować teraz? Program zamknie się i uruchomi ponownie. "
            "Dane i oferty zostaną zachowane.",
            parent=parent,
        ):
            return False
        installer = download_installer(release)
        launch_installer(installer)
    except UpdateError as error:
        messagebox.showerror(title, str(error), parent=parent)
        return False
    except OSError as error:
        messagebox.showerror(title, f"Nie można uruchomić instalatora:\n{error}", parent=parent)
        return False
    return True


def run_standalone() -> None:
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        check_and_update(root)
    finally:
        root.destroy()
    sys.exit(0)
