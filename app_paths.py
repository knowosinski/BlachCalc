import filecmp
import shutil
import sys
from datetime import date
from pathlib import Path


def resource_path(name: str) -> Path:
    bundle_directory = Path(
        getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    )
    return bundle_directory / name


EXPORT_ROOT_NAME = "BLACHCALC"
LEGACY_EXPORT_ROOT_NAME = "OFERTY CENOWE BLACHCALC"


def export_root_directory() -> Path:
    return Path.home() / "Documents" / EXPORT_ROOT_NAME


def offer_export_directory() -> Path:
    return export_root_directory() / "OFERTY"


def wz_export_directory() -> Path:
    return export_root_directory() / "WZ"


def excel_export_directory() -> Path:
    return export_root_directory() / "EXCEL"


def ensure_export_directories(settings: dict[str, str] | None = None) -> None:
    """Tworzy BLACHCALC\\OFERTY, WZ i EXCEL; przenosi dane ze starego folderu, jeśli istnieje."""
    if settings is not None:
        directories = (
            Path(settings["offer_export_directory"]).expanduser(),
            Path(settings["wz_export_directory"]).expanduser(),
            Path(settings["excel_export_directory"]).expanduser(),
            Path(settings["print_jobs_directory"]).expanduser(),
        )
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        return
    root = export_root_directory()
    legacy = root.parent / LEGACY_EXPORT_ROOT_NAME
    try:
        if legacy.is_dir() and not root.exists():
            legacy.rename(root)
            offers = offer_export_directory()
            offers.mkdir(parents=True, exist_ok=True)
            for child in list(root.iterdir()):
                if child.is_dir() and child.name not in {"OFERTY", "WZ", "EXCEL"}:
                    child.rename(offers / child.name)
        for directory in (offer_export_directory(), wz_export_directory(), excel_export_directory()):
            directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Foldery zostaną utworzone przy pierwszym zapisie pliku.
        pass


def copy_export_directory(source: str | Path, destination: str | Path) -> bool:
    source_path = Path(source).expanduser().resolve()
    destination_path = Path(destination).expanduser().resolve()
    if source_path == destination_path or not source_path.exists():
        return False
    if not source_path.is_dir():
        raise NotADirectoryError(f"Folder eksportu nie istnieje: {source_path}")
    if source_path in destination_path.parents or destination_path in source_path.parents:
        raise ValueError("Nowa lokalizacja eksportu nie może zawierać starego folderu ani znajdować się w nim.")
    destination_path.mkdir(parents=True, exist_ok=True)

    def copy_without_overwrite(source_file: str, target_file: str) -> str:
        target = Path(target_file)
        if target.exists():
            if filecmp.cmp(source_file, target, shallow=False):
                return str(target)
            source_path = Path(source_file)
            index = 1
            while target.exists():
                target = Path(target_file).with_name(
                    f"{source_path.stem} (import {index}){source_path.suffix}"
                )
                index += 1
        return str(shutil.copy2(source_file, target))

    shutil.copytree(
        source_path,
        destination_path,
        dirs_exist_ok=True,
        copy_function=copy_without_overwrite,
    )
    return True


def dated_export_directory(directory: Path, export_date: date | None = None) -> Path:
    export_date = export_date or date.today()
    return directory / export_date.strftime("%d.%m")


def excel_copy_path(
    base_directory: Path,
    pdf_filename: str | Path,
    export_date: date | None = None,
) -> Path:
    return dated_export_directory(base_directory, export_date) / f"{Path(pdf_filename).stem}.xlsx"


def ensure_file_extension(filename: str, extension: str) -> str:
    # Windows nie dopisuje domyślnego rozszerzenia, gdy nazwa zawiera kropkę (np. "S.C.").
    if not filename:
        return filename
    suffix = f".{extension.lstrip('.')}"
    if filename.lower().endswith(suffix.lower()):
        return filename
    return filename + suffix
