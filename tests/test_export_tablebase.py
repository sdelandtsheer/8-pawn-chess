import gzip
import json
import tempfile
import unittest
from pathlib import Path

from export_tablebase import build_metadata, gzip_file, write_jsonl, write_metadata
from rules import algebraic_to_square, bit
from solve import Solver


def small_solver() -> Solver:
    from rules import State

    state = State(bit(algebraic_to_square("a8")), 0, 1)
    solver = Solver()
    solver.solve(state)
    return solver


class ExportTablebaseTests(unittest.TestCase):
    def test_write_jsonl_exports_solver_memo(self) -> None:
        solver = small_solver()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tablebase.jsonl"
            write_jsonl(solver, path, export_progress_interval=0)
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), len(solver.memo))
            self.assertIn("key", rows[0])
            self.assertIn("outcome", rows[0])
            self.assertIn("dtm", rows[0])
            self.assertIn("best_move", rows[0])

    def test_gzip_file_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "tablebase.jsonl"
            target = Path(tmp) / "tablebase.jsonl.gz"
            source.write_text('{"key":"1"}\n', encoding="utf-8")
            gzip_file(source, target)
            with gzip.open(target, "rt", encoding="utf-8") as file:
                self.assertEqual(file.read(), source.read_text(encoding="utf-8"))

    def test_write_metadata(self) -> None:
        solver = small_solver()
        with tempfile.TemporaryDirectory() as tmp:
            metadata = build_metadata(
                solver,
                complete=True,
                elapsed_seconds=1.25,
                jsonl_path=Path(tmp) / "tablebase.jsonl",
                gzip_path=None,
            )
            path = Path(tmp) / "metadata.json"
            write_metadata(metadata, path)
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(loaded["complete"])
            self.assertEqual(loaded["states"], len(solver.memo))
            self.assertIsNone(loaded["gzip_path"])


if __name__ == "__main__":
    unittest.main()
