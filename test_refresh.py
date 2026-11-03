import os
import tempfile
import unittest
from pathlib import Path

from refresh import (
    compare_application_files,
    installer_for_build,
    source_files_newer_than_build,
)


class RefreshTests(unittest.TestCase):
    def test_compare_application_files_reports_added_and_changed_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            build = root / "dist" / "BlachCalc"
            installed = root / "installed"
            (build / "_internal").mkdir(parents=True)
            (installed / "_internal").mkdir(parents=True)
            (build / "BlachCalc.exe").write_bytes(b"new executable")
            (installed / "BlachCalc.exe").write_bytes(b"old executable")
            (build / "_internal" / "module.dat").write_bytes(b"same")
            (installed / "_internal" / "module.dat").write_bytes(b"same")
            (build / "_internal" / "new.dat").write_bytes(b"new")

            changed = compare_application_files(build, installed)

        self.assertEqual(
            changed,
            ["_internal/new.dat", "BlachCalc.exe"],
        )

    def test_compare_application_files_returns_empty_for_identical_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            build = root / "build"
            installed = root / "installed"
            build.mkdir()
            installed.mkdir()
            for directory in (build, installed):
                (directory / "BlachCalc.exe").write_bytes(b"same")
                (directory / "module.dat").write_bytes(b"same")

            self.assertEqual(compare_application_files(build, installed), [])

    def test_compare_application_files_rejects_same_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            folder = Path(temporary_directory)
            (folder / "BlachCalc.exe").write_bytes(b"app")

            with self.assertRaisesRegex(ValueError, "nie mogą być takie same"):
                compare_application_files(folder, folder)

    def test_installer_for_build_finds_release_installer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            build = root / "dist" / "BlachCalc"
            build.mkdir(parents=True)
            installer = root / "release" / "BlachCalc-Setup.exe"
            installer.parent.mkdir()
            installer.write_bytes(b"installer")

            self.assertEqual(installer_for_build(build), installer)

    def test_source_files_newer_than_build_detect_stale_local_build(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            build = root / "dist" / "BlachCalc"
            build.mkdir(parents=True)
            executable = build / "BlachCalc.exe"
            executable.write_bytes(b"build")
            source = root / "version.py"
            source.write_text("APP_VERSION = '1.3.0'", encoding="utf-8")
            os.utime(executable, (100, 100))
            os.utime(source, (200, 200))

            self.assertEqual(source_files_newer_than_build(build), [source])

            os.utime(source, (100, 100))
            self.assertEqual(source_files_newer_than_build(build), [])


if __name__ == "__main__":
    unittest.main()
