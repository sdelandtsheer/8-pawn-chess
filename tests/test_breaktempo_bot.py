import unittest

from pawn_chess.arena import round_robin
from pawn_chess.bots import BreakTempoBot, ZugzwangBot, all_bot_names


class BreakTempoBotTests(unittest.TestCase):
    def test_registered(self) -> None:
        self.assertIn("breaktempo", all_bot_names())

    def test_can_complete_small_match(self) -> None:
        games, stats = round_robin(
            [BreakTempoBot(search_depth=3), ZugzwangBot()],
            width=4,
            games_per_pair=2,
            seed=44,
        )
        self.assertEqual(len(games), 8)
        self.assertEqual({item.bot for item in stats}, {"breaktempo", "zugzwang"})


if __name__ == "__main__":
    unittest.main()
