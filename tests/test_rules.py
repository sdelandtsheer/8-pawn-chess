import unittest

from pawn_chess.rules import BLACK, WHITE, State, initial_state, legal_moves, make_move, move_coord


class RulesTests(unittest.TestCase):
    def test_initial_width_four_has_twelve_moves(self) -> None:
        state = initial_state(6)
        self.assertEqual(len(legal_moves(state, 6)), 12)

    def test_basic_opening_and_capture(self) -> None:
        state = initial_state(4)
        e4 = next(move for move in legal_moves(state, 4) if move_coord(move) == "a2a4")
        state = make_move(state, e4, 4)
        self.assertEqual(state.turn, BLACK)
        a5 = next(move for move in legal_moves(state, 4) if move_coord(move) == "b7b5")
        state = make_move(state, a5, 4)
        self.assertIn("a4b5", [move_coord(move) for move in legal_moves(state, 4)])

    def test_en_passant(self) -> None:
        white = 1 << 35  # d5
        black = 1 << 50  # c7
        state = State(white=white, black=black, turn=BLACK)
        move = next(move for move in legal_moves(state, 4) if move_coord(move) == "c7c5")
        state = make_move(state, move, 4)
        self.assertIn("d5c6e.p.", [move_coord(move) for move in legal_moves(state, 4)])

    def test_no_edge_wrap(self) -> None:
        state = State(white=1 << 8, black=1 << 17, turn=WHITE)
        self.assertNotIn("a2h3", [move_coord(move) for move in legal_moves(state, 2)])


if __name__ == "__main__":
    unittest.main()
