import unittest

from run_tests import ProgressResult


class ProgressResultTests(unittest.TestCase):
    def test_emits_test_names_results_and_progress(self) -> None:
        events: list[dict] = []

        class SampleTests(unittest.TestCase):
            def test_passes(self) -> None:
                self.assertEqual(1 + 1, 2)

            def test_is_skipped(self) -> None:
                self.skipTest("próba pominięta")

        suite = unittest.TestSuite(
            (
                SampleTests("test_passes"),
                SampleTests("test_is_skipped"),
            )
        )
        result = ProgressResult(suite.countTestCases(), events.append)
        suite.run(result)

        test_results = [event for event in events if event["event"] == "result"]
        progress = [event for event in events if event["event"] == "progress"]
        self.assertEqual(
            [event["status"] for event in test_results],
            ["PASS", "SKIP"],
        )
        self.assertEqual(
            [event["test"].rsplit(".", 1)[-1] for event in test_results],
            ["test_passes", "test_is_skipped"],
        )
        self.assertEqual(
            [event["done"] for event in progress],
            [1, 2],
        )
