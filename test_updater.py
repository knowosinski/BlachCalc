import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from updater import (
    UpdateError,
    check_and_update,
    install_local_update,
    get_app_files_hash,
    rebuild_application,
)


class UpdaterTests(unittest.TestCase):
    """Testy dla lokalnego systemu przebudowy (zamiennik GitHub updates)."""

    def test_get_app_files_hash_returns_empty_for_missing_dir(self):
        """Sprawdź, że hash zwraca pusty dict dla nieistniejącego katalogu."""
        with patch("updater.Path.exists", return_value=False):
            hashes = get_app_files_hash()
        self.assertEqual(hashes, {})

    def test_check_and_update_asks_for_rebuild_confirmation(self):
        """Sprawdź, że check_and_update pyta użytkownika o potwierdzenie."""
        prepare = Mock(return_value=True)
        with (
            patch("updater.messagebox.askyesno", return_value=False),
            patch("updater.rebuild_application") as rebuild,
        ):
            result = check_and_update(before_install=prepare)
        
        self.assertFalse(result)
        rebuild.assert_not_called()

    def test_check_and_update_runs_rebuild_after_confirmation(self):
        """Sprawdź, że rebuild uruchamia się po potwierdzeniu."""
        prepare = Mock(return_value=True)
        with (
            patch("updater.messagebox.askyesno", return_value=True),
            patch("updater.rebuild_application") as rebuild,
        ):
            result = check_and_update(before_install=prepare)
        
        self.assertTrue(result)
        prepare.assert_called_once()
        rebuild.assert_called_once()

    def test_check_and_update_stops_if_prepare_callback_declines(self):
        """Sprawdź, że rebuild nie uruchamia się jeśli prepare() zwróci False."""
        prepare = Mock(return_value=False)
        with (
            patch("updater.messagebox.askyesno", return_value=True),
            patch("updater.rebuild_application") as rebuild,
        ):
            result = check_and_update(before_install=prepare)
        
        self.assertFalse(result)
        prepare.assert_called_once()
        rebuild.assert_not_called()

    def test_rebuild_application_raises_error_if_build_script_missing(self):
        """Sprawdź, że rebuild podnosi UpdateError gdy Build-Windows.ps1 nie istnieje."""
        with patch("updater.Path.exists", return_value=False):
            with self.assertRaises(UpdateError):
                rebuild_application()

    def test_install_local_update_requires_existing_exe(self):
        """Sprawdź, że install_local_update wymaga istniejącego pliku .exe."""
        with (
            patch("updater.messagebox.showerror") as showerror,
            patch("updater.launch_installer") as launch,
        ):
            result = install_local_update("missing.exe")
        
        self.assertFalse(result)
        showerror.assert_called_once()
        launch.assert_not_called()

    def test_install_local_update_asks_for_confirmation(self):
        """Sprawdź, że install_local_update pyta o potwierdzenie."""
        temp_exe = Path("/tmp/test.exe")
        with (
            patch.object(Path, "is_file", return_value=True),
            patch("updater.messagebox.askyesno", return_value=False),
            patch("updater.launch_installer") as launch,
        ):
            result = install_local_update(temp_exe)
        
        self.assertFalse(result)
        launch.assert_not_called()

    def test_install_local_update_launches_after_confirmation(self):
        """Sprawdź, że launch_installer uruchamia się po potwierdzeniu."""
        temp_exe = Path("/tmp/test.exe")
        prepare = Mock(return_value=True)
        with (
            patch.object(Path, "is_file", return_value=True),
            patch.object(Path, "suffix", ".exe", create=True),
            patch("updater.messagebox.askyesno", return_value=True),
            patch("updater.launch_installer") as launch,
        ):
            result = install_local_update(temp_exe, before_install=prepare)
        
        self.assertTrue(result)
        prepare.assert_called_once()
        launch.assert_called_once()


if __name__ == "__main__":
    unittest.main()

