"""Run browser interaction contracts without third-party packages or camera/cloud."""
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which("node"), "Node.js required for browser interaction contracts")
class WebClientTest(unittest.TestCase):
    def test_browser_interaction_contracts(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ["node", "--test", str(root / "tests" / "web_client.test.cjs")],
            cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
