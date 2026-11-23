import json
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import Mock, patch

from updater import (
    BUILD_TIMEOUT_SECONDS,
    UpdateError,
    check_and_update,
    find_changed_source_files,
    get_source_files_hash,
    rebuild_application,
    write_source_manifest,
)


class UpdaterTests(unittest.TestCase):
    def test_source_hashes_include_python_and_build_inputs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "calculator.py").write_text("value = 1", encoding="utf-8")
            (root / "BlachCalc.spec").write_text("spec", encoding="utf-8")
            (root / "notes.txt").write_text("ignored", encoding="utf-8")

            hashes = get_source_files_hash(root)

        self.assertEqual(set(hashes), {"calculator.py", "BlachCalc.spec"})
        self.assertEqual(len(hashes["calculator.py"]), 64)

    def test_manifest_stores_repository_path_and_hashes(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "calculator.py").write_text("value = 1", encoding="utf-8")
            manifest_path = write_source_manifest(root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["source_root"], str(root.resolve()))
        self.assertIn("calculator.py", manifest["files"])

    def test_changed_sources_include_modified_added_and_removed_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "modified.py").write_text("new", encoding="utf-8")
            (root / "added.py").write_text("added", encoding="utf-8")

            changed = find_changed_source_files(
                root,
                {"modified.py": "old-hash", "removed.py": "old-hash"},
            )

        self.assertEqual(changed, ["added.py", "modified.py", "removed.py"])

    def test_check_and_update_reports_no_changes_without_prompting(self):
        with (
            patch("updater.load_source_manifest", return_value=(Path("source"), {"app.py": "same"})),
            patch("updater.find_changed_source_files", return_value=[]),
            patch("updater.messagebox.showinfo") as showinfo,
            patch("updater.messagebox.askyesno") as confirm,
        ):
            result = check_and_update(notify_if_current=True)

        self.assertFalse(result)
        showinfo.assert_called_once()
        confirm.assert_not_called()

    def test_check_and_update_asks_with_changed_file_count(self):
        source_root = Path("source")
        with (
            patch("updater.load_source_manifest", return_value=(source_root, {"app.py": "old"})),
            patch("updater.find_changed_source_files", return_value=["app.py", "new.py"]),
            patch("updater.messagebox.askyesno", return_value=False) as confirm,
            patch("updater.rebuild_application") as rebuild,
        ):
            result = check_and_update()

        self.assertFalse(result)
        self.assertIn("2 zmienionych", confirm.call_args.args[1])
        rebuild.assert_not_called()

    def test_check_and_update_builds_after_confirmation_and_prepare(self):
        source_root = Path("source")
        prepare = Mock(return_value=True)
        with (
            patch("updater.load_source_manifest", return_value=(source_root, {"app.py": "old"})),
            patch("updater.find_changed_source_files", return_value=["app.py"]),
            patch("updater.messagebox.askyesno", return_value=True),
            patch("updater.rebuild_application") as rebuild,
        ):
            result = check_and_update(before_install=prepare)

        self.assertTrue(result)
        prepare.assert_called_once()
        rebuild.assert_called_once_with(source_root)

    def test_check_and_update_stops_if_prepare_callback_declines(self):
        prepare = Mock(return_value=False)
        with (
            patch("updater.load_source_manifest", return_value=(Path("source"), {"app.py": "old"})),
            patch("updater.find_changed_source_files", return_value=["app.py"]),
            patch("updater.messagebox.askyesno", return_value=True),
            patch("updater.rebuild_application") as rebuild,
        ):
            result = check_and_update(before_install=prepare)

        self.assertFalse(result)
        prepare.assert_called_once()
        rebuild.assert_not_called()

    def test_rebuild_builds_and_launches_the_generated_installer(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "Build-Windows.ps1").touch()
            installer = root / "release" / "BlachCalc-Setup.exe"
            installer.parent.mkdir()
            installer.touch()

            with (
                patch(
                    "updater.subprocess.run",
                    return_value=CompletedProcess([], 0, stdout="", stderr=""),
                ) as run,
                patch("updater.launch_installer") as launch,
            ):
                rebuild_application(root)

        self.assertEqual(run.call_args.kwargs["cwd"], root.resolve())
        self.assertEqual(run.call_args.kwargs["timeout"], BUILD_TIMEOUT_SECONDS)
        launch.assert_called_once_with(installer)

    def test_rebuild_includes_build_output_when_build_fails(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "Build-Windows.ps1").touch()
            with patch(
                "updater.subprocess.run",
                return_value=CompletedProcess([], 1, stdout="test failure", stderr=""),
            ):
                with self.assertRaisesRegex(UpdateError, "test failure"):
                    rebuild_application(root)

    def test_rebuild_requires_build_script(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaisesRegex(UpdateError, "Build-Windows.ps1"):
                rebuild_application(Path(temporary_directory))


if __name__ == "__main__":
    unittest.main()
