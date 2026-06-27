import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class Width8HtmlTests(unittest.TestCase):
    def test_width8_html_is_self_contained_zugzwang_page(self) -> None:
        html = Path("browser/wix_width8_zugzwang.html").read_text(encoding="utf-8")
        self.assertIn("const WIDTH = 8;", html)
        self.assertIn("function chooseZugzwangMove", html)
        self.assertIn("function legalMoves", html)
        self.assertIn("Zugzwang", html)
        self.assertNotIn("TABLEBASE_URL", html)

    @unittest.skipIf(shutil.which("node") is None, "node is required for HTML JS syntax check")
    def test_width8_html_javascript_syntax_and_runtime_smoke(self) -> None:
        html = Path("browser/wix_width8_zugzwang.html").read_text(encoding="utf-8")
        scripts = re.findall(r"<script>(.*?)</script>", html, flags=re.S)
        self.assertTrue(scripts)
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as file:
            file.write(_node_dom_stub())
            file.write("\n")
            file.write("\n".join(scripts))
            temp_path = file.name
        try:
            result = subprocess.run(
                ["node", temp_path],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)
        finally:
            Path(temp_path).unlink(missing_ok=True)


def _node_dom_stub() -> str:
    return r"""
function element() {
  return {
    dataset: {},
    style: {},
    children: [],
    className: "",
    textContent: "",
    innerHTML: "",
    appendChild(child) { this.children.push(child); },
    addEventListener() {},
    closest() { return this; },
    contains() { return true; },
    classList: { add() {}, toggle() {} }
  };
}
const ids = new Map();
for (const id of ["board", "status", "last-move", "start-modal", "start-button"]) {
  ids.set(id, element());
}
const sideW = element();
sideW.dataset.side = "w";
const sideB = element();
sideB.dataset.side = "b";
global.document = {
  getElementById(id) { return ids.get(id) || element(); },
  querySelectorAll(selector) { return selector === ".side-button" ? [sideW, sideB] : []; },
  createElement() { return element(); }
};
"""


if __name__ == "__main__":
    unittest.main()
