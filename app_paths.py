import sys
from pathlib import Path


def resource_path(name: str) -> Path:
    bundle_directory = Path(
        getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    )
    return bundle_directory / name


def offer_export_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path.home() / "Documents" / "OFERTY CENOWE BLACHCALC"
    return Path(__file__).resolve().parent / "OFERTY CENOWE BLACHCALC"


def wz_export_directory() -> Path:
    return offer_export_directory() / "WZ"
