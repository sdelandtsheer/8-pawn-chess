import random
import unittest

from pawn_chess.bots import MirrorBot
from pawn_chess.rules import BLACK, initial_state, legal_moves, make_move, move_coord


class MirrorBotTests(unittest.TestCase):
    def test_black_mirrors_every_initial_white_move(self) -> None:
        bot = MirrorBot()
        root = initial_state(8)
        for white_move in legal_moves(root, 8):
            with self.subTest(move=move_coord(white_move)):
                state = make_move(root, white_move, 8)
                self.assertEqual(state.turn, BLACK)
                black_move = bot.choose_move(state, legal_moves(state, 8), 8, random.Random(1))
                mirrored = make_move(state, black_move, 8)
                self.assertEqual(mirrored.black, _mirror_bitboard(mirrored.white))


def _mirror_bitboard(bitboard: int) -> int:
    mirrored = 0
    remaining = bitboard
    while remaining:
        pawn = remaining & -remaining
        square = pawn.bit_length() - 1
        mirrored |= 1 << ((7 - (square >> 3)) * 8 + (square & 7))
        remaining ^= pawn
    return mirrored


if __name__ == "__main__":
    unittest.main()
