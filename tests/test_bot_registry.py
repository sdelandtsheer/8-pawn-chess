import random
import unittest

from pawn_chess.bots import all_bot_names, create_bot
from pawn_chess.rules import initial_state, legal_moves


class BotRegistryTests(unittest.TestCase):
    def test_has_expected_bot_suite(self) -> None:
        self.assertEqual(
            set(all_bot_names()),
            {
                "advance",
                "breaktempo",
                "capture",
                "center",
                "double",
                "edge",
                "first",
                "last",
                "mirror",
                "passer",
                "principle",
                "random",
                "safe",
                "tactical1",
                "tempo",
                "zugzwang",
            },
        )

    def test_all_bots_choose_legal_initial_move(self) -> None:
        state = initial_state(4)
        moves = legal_moves(state, 4)
        for name in all_bot_names():
            with self.subTest(name=name):
                bot = create_bot(name)
                move = bot.choose_move(state, moves, 4, random.Random(5))
                self.assertIn(move, moves)


if __name__ == "__main__":
    unittest.main()
