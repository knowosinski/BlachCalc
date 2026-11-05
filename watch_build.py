"""Automatycznie buduje BlachCalc po zmianie plików źródłowych.

python watch_build.py              czeka na zmiany i buduje po chwili ciszy
python watch_build.py --once       buduje od razu jeden raz i kończy
python watch_build.py --quiet 30   buduje po 30 s bez nowych zmian (domyślnie 20)

Każdy build uruchamia testy (Build-Windows.ps1), a przy ich błędzie wydanie nie powstaje.
Zatrzymanie: Ctrl+C.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD_SCRIPT = ROOT / "Build-Windows.ps1"
WATCHED_PATTERNS = ("*.py", "*.iss", "*.spec")
IGNORED_PARTS = {"build", "dist", "release", "__pycache__", ".git", ".venv", "venv"}


def is_watched(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if IGNORED_PARTS.intersection(relative.parts):
        return False
    # Zmiany samych testów nie zmieniają wydania.
    return not path.name.startswith("test_")


def snapshot() -> dict[Path, int]:
    state: dict[Path, int] = {}
    for pattern in WATCHED_PATTERNS:
        for path in ROOT.rglob(pattern):
            if is_watched(path):
                try:
                    state[path] = path.stat().st_mtime_ns
                except OSError:
                    continue
    return state


def build() -> bool:
    print(f"[{time.strftime('%H:%M:%S')}] Budowanie…", flush=True)
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(BUILD_SCRIPT),
        ],
        cwd=ROOT,
    )
    if result.returncode == 0:
        print(f"[{time.strftime('%H:%M:%S')}] Build zakończony pomyślnie.", flush=True)
    else:
        print(
            f"[{time.strftime('%H:%M:%S')}] Build nieudany (kod {result.returncode}). "
            "Popraw błędy; kolejna zmiana uruchomi build ponownie.",
            flush=True,
        )
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--once", action="store_true", help="zbuduj jeden raz i zakończ")
    parser.add_argument("--quiet", type=float, default=20, help="sekundy ciszy po ostatniej zmianie")
    args = parser.parse_args()

    if args.once:
        return 0 if build() else 1

    known = snapshot()
    print(
        f"Obserwuję {len(known)} plików. Build ruszy po {args.quiet:g} s bez zmian. Ctrl+C kończy.",
        flush=True,
    )
    last_change: float | None = None
    try:
        while True:
            time.sleep(2)
            current = snapshot()
            if current != known:
                known = current
                last_change = time.monotonic()
                continue
            if last_change is not None and time.monotonic() - last_change >= args.quiet:
                last_change = None
                build()
                # Pliki dotknięte przez build nie powinny wywołać kolejnego.
                known = snapshot()
    except KeyboardInterrupt:
        print("Zatrzymano.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
