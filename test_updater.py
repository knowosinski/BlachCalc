import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from updater import (
    ReleaseInfo,
    UpdateError,
    check_and_update,
    install_local_update,
    is_newer,
    parse_version,
    release_from_payload,
)


class UpdaterTests(unittest.TestCase):
    def test_version_comparison(self):
        self.assertTrue(is_newer("v1.2.0", "1.1.9"))
        self.assertTrue(is_newer("1.10", "1.9.5"))
        self.assertFalse(is_newer("1.1.0", "1.1"))
        self.assertFalse(is_newer("1.0.9", "1.1.0"))
        self.assertEqual(parse_version("v2.0.1"), (2, 0, 1))
        with self.assertRaises(ValueError):
            parse_version("beta")

    def test_release_payload(self):
        payload = {
            "tag_name": "v1.2.0",
            "assets": [
                {"name": "other.zip", "browser_download_url": "https://x/other.zip"},
                {
                    "name": "BlachCalc-Setup.exe",
                    "browser_download_url": "https://x/BlachCalc-Setup.exe",
                    "digest": "sha256:ABCD",
                },
            ],
        }
        release = release_from_payload(payload)
        self.assertEqual(release.version, "1.2.0")
        self.assertEqual(release.sha256, "abcd")
        with self.assertRaises(UpdateError):
            release_from_payload({"tag_name": "v1.2.0", "assets": []})

    def test_check_and_update_runs_prepare_callback_before_installing_github_release(self):
        release = ReleaseInfo("99.0.0", "https://github.com/example/release.exe", None)
        installer = Path("installer.exe")
        prepare = Mock(return_value=True)
        with (
            patch("updater.fetch_latest_release", return_value=release),
            patch("updater.messagebox.askyesno", return_value=True),
            patch("updater.download_installer", return_value=installer) as download,
            patch("updater.launch_installer") as launch,
        ):
            self.assertTrue(check_and_update(before_install=prepare))

        prepare.assert_called_once_with()
        download.assert_called_once_with(release)
        launch.assert_called_once_with(installer)

    def test_check_and_update_stops_if_prepare_callback_declines(self):
        release = ReleaseInfo("99.0.0", "https://github.com/example/release.exe", None)
        prepare = Mock(return_value=False)
        with (
            patch("updater.fetch_latest_release", return_value=release),
            patch("updater.messagebox.askyesno", return_value=True),
            patch("updater.download_installer") as download,
            patch("updater.launch_installer") as launch,
        ):
            self.assertFalse(check_and_update(before_install=prepare))

        prepare.assert_called_once_with()
        download.assert_not_called()
        launch.assert_not_called()

    def test_check_and_update_can_skip_up_to_date_notification(self):
        release = ReleaseInfo("1.0.0", "https://github.com/example/release.exe", None)
        with (
            patch("updater.fetch_latest_release", return_value=release),
            patch("updater.messagebox.showinfo") as showinfo,
        ):
            self.assertFalse(check_and_update(notify_if_current=False))

        showinfo.assert_not_called()

    def test_local_update_requires_existing_exe_and_runs_after_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            installer = Path(directory) / "BlachCalc-Setup.exe"
            installer.write_bytes(b"test installer")
            prepare = Mock(return_value=True)
            with (
                patch("updater.messagebox.askyesno", return_value=True),
                patch("updater.launch_installer") as launch,
            ):
                self.assertTrue(install_local_update(installer, before_install=prepare))

        prepare.assert_called_once_with()
        launch.assert_called_once_with(installer)

    def test_local_update_rejects_missing_installer(self):
        with (
            patch("updater.messagebox.showerror") as showerror,
            patch("updater.launch_installer") as launch,
        ):
            self.assertFalse(install_local_update("missing.exe"))

        showerror.assert_called_once()
        launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
