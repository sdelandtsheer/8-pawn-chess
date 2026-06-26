import gzip
import json
import struct
import tempfile
import unittest
from pathlib import Path

from compact_solve import CompactSolver
from export_tablebase import build_metadata, gzip_file, write_binary, write_jsonl, write_metadata
from rules import algebraic_to_square, bit, initial_state, state_key
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

    def test_write_jsonl_exports_compact_solver_with_standard_keys(self) -> None:
        solver = CompactSolver(board_width=2)
        solver.solve(initial_state(2))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tablebase.jsonl"
            write_jsonl(solver, path, export_progress_interval=0)
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            keys = {row["key"] for row in rows}
            self.assertEqual(len(rows), len(solver.memo))
            self.assertIn(f"{state_key(initial_state(2), board_width=2):x}", keys)

    def test_gzip_file_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "tablebase.jsonl"
            target = Path(tmp) / "tablebase.jsonl.gz"
            source.write_text('{"key":"1"}\n', encoding="utf-8")
            gzip_file(source, target)
            with gzip.open(target, "rt", encoding="utf-8") as file:
                self.assertEqual(file.read(), source.read_text(encoding="utf-8"))

    def test_write_binary_exports_fixed_records(self) -> None:
        solver = CompactSolver(board_width=2)
        solver.solve(initial_state(2))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tablebase.bin"
            write_binary(solver, path, board_width=2, export_progress_interval=0)
            data = path.read_bytes()

            self.assertEqual(data[:4], b"PWTB")
            self.assertEqual(data[4], 1)
            self.assertEqual(data[5], 2)
            self.assertEqual(data[6], 17)
            self.assertEqual(data[7], 22)
            self.assertEqual(struct.unpack("<Q", data[8:16])[0], len(solver.memo))
            self.assertEqual(len(data), 16 + len(solver.memo) * 22)

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
            self.assertEqual(loaded["board_width"], 8)
            self.assertEqual(loaded["states"], len(solver.memo))
            self.assertIsNone(loaded["gzip_path"])

    def test_build_metadata_reads_compact_initial_result(self) -> None:
        solver = CompactSolver(board_width=2)
        solver.solve(initial_state(2))
        with tempfile.TemporaryDirectory() as tmp:
            metadata = build_metadata(
                solver,
                complete=True,
                elapsed_seconds=1.25,
                jsonl_path=Path(tmp) / "tablebase.jsonl",
                gzip_path=None,
                board_width=2,
            )
            self.assertEqual(metadata.board_width, 2)
            self.assertEqual(metadata.dtm, 8)
            self.assertEqual(metadata.best_move_coord, "a2a3")


if __name__ == "__main__":
    unittest.main()
