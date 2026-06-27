import shutil
import subprocess
import unittest
from pathlib import Path


class BrowserCoreTests(unittest.TestCase):
    def run_node_script(self, script: Path) -> None:
        result = subprocess.run(
            ["node", str(script)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)

    @unittest.skipIf(shutil.which("node") is None, "node is required for browser core tests")
    def test_width_four_keying_and_move_encoding(self) -> None:
        self.run_node_script(Path("tests/browser_core_smoke.js"))

    @unittest.skipIf(shutil.which("node") is None, "node is required for browser core tests")
    def test_generated_width_four_strategy_html(self) -> None:
        self.run_node_script(Path("tests/strategy_html_smoke.js"))


if __name__ == "__main__":
    unittest.main()
