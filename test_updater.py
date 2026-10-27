import unittest

from updater import UpdateError, is_newer, parse_version, release_from_payload


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


if __name__ == "__main__":
    unittest.main()
