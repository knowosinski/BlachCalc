"""Lokalny system aktualizacji aplikacji - porównanie plików i przebudowa."""
import hashlib
import subprocess
import sys
from pathlib import Path
from tkinter import messagebox
from typing import Any, Callable

from version import APP_VERSION

UPDATED_FLAG = "--updated"
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200


class UpdateError(Exception):
    pass


def get_app_files_hash() -> dict[str, str]:
    """Pobiera hasze wszystkich plików aplikacji w /dist/BlachCalc/"""
    app_dir = Path(sys.argv[0]).parent if getattr(sys, "frozen", False) else Path(__file__).parent / "dist" / "BlachCalc"
    
    hashes = {}
    if not app_dir.exists():
        return hashes
    
    # Haszuj tylko główne pliki aplikacji (exe, dll, pyd)
    for file in app_dir.rglob("*"):
        if file.is_file() and file.suffix.lower() in (".exe", ".dll", ".pyd", ".so"):
            try:
                with open(file, "rb") as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                    rel_path = str(file.relative_to(app_dir))
                    hashes[rel_path] = file_hash
            except (OSError, IOError):
                pass
    
    return hashes


def check_and_update(
    parent: Any = None,
    before_install: Callable[[], bool] | None = None,
    notify_if_current: bool = True,
) -> bool:
    """Sprawdza pliki aplikacji i oferuje lokalną przebudowę."""
    title = "BlachCalc — aktualizacja"
    
    # Zawsze proponuj update z opcją przebudowy
    if not messagebox.askyesno(
        title,
        f"Aplikacja: BlachCalc v{APP_VERSION}\n\n"
        "Przebudować aplikację z najnowszym kodem?\n"
        "Dane i oferty zostaną zachowane.",
        parent=parent,
    ):
        return False
    
    if before_install is not None and not before_install():
        return False
    
    # Rebuild aplikacji
    try:
        rebuild_application(parent)
    except UpdateError as error:
        messagebox.showerror(title, str(error), parent=parent)
        return False
    except OSError as error:
        messagebox.showerror(title, f"Nie można przebudować aplikacji:\n{error}", parent=parent)
        return False
    
    return True


def install_local_update(
    installer_path: str | Path,
    parent: Any = None,
    before_install: Callable[[], bool] | None = None,
) -> bool:
    """Uruchamia lokalny instalator po potwierdzeniu przez użytkownika."""
    title = "BlachCalc — aktualizacja lokalna"
    installer = Path(installer_path).expanduser()
    if installer.suffix.lower() != ".exe" or not installer.is_file():
        messagebox.showerror(
            title,
            "Wskaż istniejący lokalny instalator BlachCalc w formacie .exe.",
            parent=parent,
        )
        return False
    if not messagebox.askyesno(
        title,
        f"Uruchomić instalator z pliku lokalnego?\n{installer}\n\n"
        "Program zamknie się na czas aktualizacji.",
        parent=parent,
    ):
        return False
    if before_install is not None and not before_install():
        return False
    try:
        launch_installer(installer)
    except OSError as error:
        messagebox.showerror(title, f"Nie można uruchomić instalatora:\n{error}", parent=parent)
        return False
    return True


def rebuild_application(parent: Any = None) -> None:
    """Przebudowuje aplikację przy użyciu Build-Windows.ps1"""
    build_script = Path(__file__).parent / "Build-Windows.ps1"
    
    if not build_script.exists():
        raise UpdateError("Skrypt Build-Windows.ps1 nie znaleziony.")
    
    try:
        # Uruchom build script
        result = subprocess.run(
            [
                "powershell",
                "-ExecutionPolicy", "Bypass",
                "-File", str(build_script),
            ],
            capture_output=True,
            text=True,
            timeout=1200,  # 20 minut
        )
        
        if result.returncode != 0:
            raise UpdateError(f"Przebudowa nie powiodła się (sprawdź logi)")
        
        # Znowu uruchom aplikację
        app_exe = Path(__file__).parent / "dist" / "BlachCalc" / "BlachCalc.exe"
        if not app_exe.exists():
            raise UpdateError("Plik aplikacji BlachCalc.exe nie znaleziony po przebudowie.")
        
        launch_app_with_flag(app_exe, UPDATED_FLAG)
    
    except subprocess.TimeoutExpired:
        raise UpdateError("Przebudowa przekroczyła limit czasu (20 minut).")
    except Exception as error:
        raise UpdateError(f"Błąd podczas przebudowy:\n{error}")


def launch_app_with_flag(app_path: Path, flag: str) -> None:
    """Uruchamia aplikację z flagą (np. --updated)"""
    try:
        subprocess.Popen(
            [str(app_path), flag],
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
        )
    except OSError as error:
        raise UpdateError(f"Nie można uruchomić aplikacji:\n{error}")


def launch_installer(installer_path: Path) -> None:
    """Uruchamia instalator w trybie silent."""
    try:
        subprocess.Popen(
            [
                str(installer_path),
                "/SILENT",
                "/NORESTART",
                "/CLOSEAPPLICATIONS",
            ],
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
        )
    except OSError as error:
        raise UpdateError(f"Nie można uruchomić instalatora:\n{error}")


def run_standalone() -> None:
    """Tryb standalone dla testowania."""
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    check_and_update(parent=root, notify_if_current=True)
    root.destroy()


if __name__ == "__main__":
    run_standalone()
