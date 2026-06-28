import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from pawn_chess.arena import round_robin, write_results
from pawn_chess.bots import FirstLegalBot, RandomBot


class ArenaTests(unittest.TestCase):
    def test_round_robin_is_deterministic(self) -> None:
        bots = [RandomBot(), FirstLegalBot()]
        games_a, stats_a = round_robin(bots, width=4, games_per_pair=2, seed=7)
        games_b, stats_b = round_robin(bots, width=4, games_per_pair=2, seed=7)
        self.assertEqual(games_a, games_b)
        self.assertEqual([item.win_rate for item in stats_a], [item.win_rate for item in stats_b])

    def test_progress_does_not_change_results(self) -> None:
        bots = [RandomBot(), FirstLegalBot()]
        games_a, _ = round_robin(bots, width=4, games_per_pair=2, seed=9)
        games_b, _ = round_robin(bots, width=4, games_per_pair=2, seed=9, progress_interval=3)
        self.assertEqual(games_a, games_b)

    def test_writes_results(self) -> None:
        bots = [RandomBot(), FirstLegalBot()]
        games, stats = round_robin(bots, width=4, games_per_pair=1, seed=3)
        with TemporaryDirectory() as directory:
            write_results(
                Path(directory),
                width=4,
                games_per_pair=1,
                seed=3,
                games=games,
                stats=stats,
            )
            summary_path = Path(directory) / "summary.json"
            self.assertTrue(summary_path.exists())
            self.assertTrue((Path(directory) / "games.csv").exists())
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            first_bot = summary["bots"][0]
            self.assertIn("white_win_rate", first_bot)
            self.assertIn("black_win_rate", first_bot)


if __name__ == "__main__":
    unittest.main()
