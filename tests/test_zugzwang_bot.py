import unittest

from pawn_chess.arena import round_robin
from pawn_chess.bots import TempoBot, ZugzwangBot, all_bot_names


class ZugzwangBotTests(unittest.TestCase):
    def test_registered(self) -> None:
        self.assertIn("zugzwang", all_bot_names())

    def test_can_complete_small_match(self) -> None:
        games, stats = round_robin([ZugzwangBot(), TempoBot()], width=4, games_per_pair=2, seed=31)
        self.assertEqual(len(games), 8)
        self.assertEqual({item.bot for item in stats}, {"zugzwang", "tempo"})


if __name__ == "__main__":
    unittest.main()
