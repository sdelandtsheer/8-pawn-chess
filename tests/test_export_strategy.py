import json
import struct
import tempfile
import unittest
from pathlib import Path

from export_strategy import (
    STRATEGY_MAGIC,
    STRATEGY_RECORD_BYTES,
    STRATEGY_VERSION,
    StrategyBuilder,
    export_strategy,
    verify_strategy,
)
from rules import BLACK, WHITE, initial_state, state_key
from solve import LOSS, NO_MOVE


class ExportStrategyTests(unittest.TestCase):
    def test_width_two_black_strategy_covers_all_initial_human_replies(self) -> None:
        builder = StrategyBuilder(board_width=2, engine_side=BLACK, progress_interval=0)
        result = builder.build()
        verification = verify_strategy(builder.entries, board_width=2, engine_side=BLACK)
        root = builder.entries[state_key(initial_state(2), board_width=2)]

        self.assertEqual(result.outcome, LOSS)
        self.assertEqual(result.dtm, 8)
        self.assertFalse(root.engine_turn)
        self.assertEqual(root.best_move, NO_MOVE)
        self.assertGreater(verification["human_edges"], 0)
        self.assertGreater(verification["engine_edges"], 0)

    def test_width_two_white_strategy_has_engine_move_at_root(self) -> None:
        builder = StrategyBuilder(board_width=2, engine_side=WHITE, progress_interval=0)
        builder.build()
        root = builder.entries[state_key(initial_state(2), board_width=2)]

        self.assertTrue(root.engine_turn)
        self.assertNotEqual(root.best_move, NO_MOVE)

    def test_export_strategy_writes_binary_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            metadata = export_strategy(
                board_width=2,
                engine_side=BLACK,
                output_dir=Path(tmp),
                progress_interval=0,
            )
            binary_path = Path(metadata.binary_path)
            data = binary_path.read_bytes()
            magic, version, width, side, record_bytes, rows = struct.unpack(
                "<4sBBBBQ",
                data[:16],
            )
            loaded = json.loads((Path(tmp) / "strategy_black.metadata.json").read_text())

            self.assertEqual(magic, STRATEGY_MAGIC)
            self.assertEqual(version, STRATEGY_VERSION)
            self.assertEqual(width, 2)
            self.assertEqual(side, BLACK)
            self.assertEqual(record_bytes, STRATEGY_RECORD_BYTES)
            self.assertEqual(rows, metadata.entries)
            self.assertEqual(len(data), 16 + metadata.entries * STRATEGY_RECORD_BYTES)
            self.assertEqual(loaded["entries"], metadata.entries)


if __name__ == "__main__":
    unittest.main()
