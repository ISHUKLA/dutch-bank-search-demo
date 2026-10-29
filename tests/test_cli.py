"""Smoke checks for the installed package's command-line contract."""

import subprocess
import sys
import unittest


class CommandLineTests(unittest.TestCase):
    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "bank_search", *arguments],
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

    def test_backend_flag_accepts_both_backends(self) -> None:
        for backend in ("offline", "elasticsearch"):
            with self.subTest(backend=backend):
                result = self.run_cli("--backend", backend)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"Backend: {backend}", result.stdout)

    def test_invalid_backend_is_rejected(self) -> None:
        result = self.run_cli("--backend", "unknown")
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid choice", result.stderr)


if __name__ == "__main__":
    unittest.main()
