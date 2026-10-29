"""Smoke checks for the installed package's command-line contract."""

import os
import subprocess
import sys
import unittest


class CommandLineTests(unittest.TestCase):
    def run_cli(self, offline: str | None = None) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment.pop("USE_OFFLINE", None)
        if offline is not None:
            environment["USE_OFFLINE"] = offline
        return subprocess.run(
            [sys.executable, "-m", "bank_search"],
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    def test_default_runs_without_services(self) -> None:
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Scaffold ready", result.stdout)
        self.assertIn("Backend: offline", result.stdout)
        self.assertIn("Search implementation: pending", result.stdout)

    def test_offline_flag_selects_both_backends(self) -> None:
        for offline, backend in (("true", "offline"), ("false", "elasticsearch")):
            with self.subTest(backend=backend):
                result = self.run_cli(offline)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"Backend: {backend}", result.stdout)

    def test_invalid_offline_flag_is_rejected(self) -> None:
        result = self.run_cli("unknown")
        self.assertEqual(result.returncode, 2)
        self.assertIn("USE_OFFLINE", result.stderr)


if __name__ == "__main__":
    unittest.main()
