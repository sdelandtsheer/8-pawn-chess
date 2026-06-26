import shutil
import subprocess
import unittest
from pathlib import Path


class BrowserCoreTests(unittest.TestCase):
    @unittest.skipIf(shutil.which("node") is None, "node is required for browser core tests")
    def test_width_four_keying_and_move_encoding(self) -> None:
        script = Path("tests/browser_core_smoke.js")
        result = subprocess.run(
            ["node", str(script)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
