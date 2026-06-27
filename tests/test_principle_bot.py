import random
import unittest

from pawn_chess.bots import PrincipleBot, all_bot_names
from pawn_chess.rules import WHITE, State, bit, legal_moves, move_coord, parse_square


class PrincipleBotTests(unittest.TestCase):
    def test_registered(self) -> None:
        self.assertIn("principle", all_bot_names())

    def test_takes_immediate_promotion(self) -> None:
        state = State(
            white=bit(parse_square("a7")) | bit(parse_square("b2")),
            black=bit(parse_square("d7")),
            turn=WHITE,
        )
        bot = PrincipleBot()
        move = bot.choose_move(state, legal_moves(state, 4), 4, random.Random(1))
        self.assertEqual(move_coord(move), "a7a8")


if __name__ == "__main__":
    unittest.main()
