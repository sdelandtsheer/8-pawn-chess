import unittest

from rules import (
    BLACK,
    FLAG_CAPTURE,
    FLAG_DOUBLE,
    FLAG_EN_PASSANT,
    FLAG_WINNING,
    NO_EP,
    WHITE,
    Move,
    State,
    algebraic_to_square,
    bit,
    decode_move,
    encode_move,
    file_index,
    find_legal_move,
    initial_state,
    is_terminal,
    iter_squares,
    legal_moves,
    make_move,
    move_to_coord,
    normalize_state,
    occupied,
    opponent_pawns,
    pawns_for_turn,
    perft,
    play_coord_moves,
    rank_index,
    square_to_algebraic,
    state_from_key,
    state_key,
    terminal_winner,
    validate_board_width,
)


def state_with(
    white: list[str], black: list[str], turn: int, ep_square: str | None = None
) -> State:
    white_bits = sum(bit(algebraic_to_square(square)) for square in white)
    black_bits = sum(bit(algebraic_to_square(square)) for square in black)
    ep = NO_EP if ep_square is None else algebraic_to_square(ep_square)
    return State(white_bits, black_bits, turn, ep)


class SquareTests(unittest.TestCase):
    def test_square_indexing_and_algebraic_conversion(self) -> None:
        cases = {"a1": 0, "h1": 7, "a2": 8, "e4": 28, "h8": 63}
        for name, square in cases.items():
            with self.subTest(name=name):
                self.assertEqual(algebraic_to_square(name), square)
                self.assertEqual(square_to_algebraic(square), name)

    def test_square_helpers_reject_invalid_input(self) -> None:
        for bad_square in (-1, 64):
            with self.subTest(square=bad_square):
                with self.assertRaises(ValueError):
                    bit(bad_square)
                with self.assertRaises(ValueError):
                    file_index(bad_square)
                with self.assertRaises(ValueError):
                    rank_index(bad_square)

        for bad_name in ("", "a", "i1", "a9", "11"):
            with self.subTest(name=bad_name), self.assertRaises(ValueError):
                algebraic_to_square(bad_name)

    def test_file_and_rank_indexes(self) -> None:
        self.assertEqual(file_index(algebraic_to_square("a1")), 0)
        self.assertEqual(file_index(algebraic_to_square("h8")), 7)
        self.assertEqual(rank_index(algebraic_to_square("a1")), 0)
        self.assertEqual(rank_index(algebraic_to_square("h8")), 7)


class MoveEncodingTests(unittest.TestCase):
    def test_move_code_round_trip(self) -> None:
        move = Move(
            algebraic_to_square("e5"),
            algebraic_to_square("d6"),
            FLAG_CAPTURE | FLAG_EN_PASSANT,
        )
        self.assertEqual(decode_move(encode_move(move)), move)

    def test_move_to_coord(self) -> None:
        self.assertEqual(
            move_to_coord(Move(algebraic_to_square("a2"), algebraic_to_square("a4"), FLAG_DOUBLE)),
            "a2a4",
        )

    def test_decode_rejects_out_of_range_codes(self) -> None:
        for code in (-1, 1 << 16):
            with self.subTest(code=code), self.assertRaises(ValueError):
                decode_move(code)


class StateTests(unittest.TestCase):
    def test_initial_state_bitboards(self) -> None:
        state = initial_state()
        self.assertEqual(state.turn, WHITE)
        self.assertEqual(state.ep_square, NO_EP)
        self.assertEqual(len(iter_squares(state.white)), 8)
        self.assertEqual(len(iter_squares(state.black)), 8)
        self.assertEqual(square_to_algebraic(iter_squares(state.white)[0]), "a2")
        self.assertEqual(square_to_algebraic(iter_squares(state.black)[-1]), "h7")

    def test_initial_state_supports_even_board_widths(self) -> None:
        for board_width in (2, 4, 6, 8):
            with self.subTest(board_width=board_width):
                state = initial_state(board_width)
                self.assertEqual(len(iter_squares(state.white)), board_width)
                self.assertEqual(len(iter_squares(state.black)), board_width)

    def test_board_width_rejects_invalid_values(self) -> None:
        for board_width in (0, 1, 3, 5, 7, 9):
            with self.subTest(board_width=board_width), self.assertRaises(ValueError):
                validate_board_width(board_width)

    def test_state_rejects_overlapping_pawns(self) -> None:
        with self.assertRaises(ValueError):
            State(bit(algebraic_to_square("a2")), bit(algebraic_to_square("a2")), WHITE)

    def test_state_key_round_trip_normalized(self) -> None:
        state = state_with(["d5"], ["e5"], WHITE, "e6")
        self.assertEqual(state_from_key(state_key(state)), normalize_state(state))

    def test_state_key_normalizes_irrelevant_en_passant(self) -> None:
        state = State(
            initial_state().white, initial_state().black, BLACK, algebraic_to_square("e3")
        )
        self.assertEqual(normalize_state(state).ep_square, NO_EP)
        self.assertEqual(state_key(state), state_key(normalize_state(state)))

    def test_en_passant_square_kept_when_capture_exists(self) -> None:
        state = state_with(["e4"], ["d4"], BLACK, "e3")
        self.assertEqual(normalize_state(state).ep_square, algebraic_to_square("e3"))

    def test_occupancy_and_side_helpers(self) -> None:
        state = state_with(["a2", "c4"], ["b7"], BLACK)
        self.assertEqual(occupied(state), state.white | state.black)
        self.assertEqual(pawns_for_turn(state), state.black)
        self.assertEqual(opponent_pawns(state), state.white)

    def test_iter_squares_is_sorted(self) -> None:
        board = bit(algebraic_to_square("h8")) | bit(algebraic_to_square("a1"))
        self.assertEqual(
            tuple(square_to_algebraic(square) for square in iter_squares(board)),
            ("a1", "h8"),
        )


class MoveGenerationTests(unittest.TestCase):
    def test_initial_position_has_16_legal_moves(self) -> None:
        moves = legal_moves(initial_state())
        self.assertEqual(len(moves), 16)
        self.assertEqual(sum(1 for move in moves if move.flags & FLAG_DOUBLE), 8)
        self.assertIn("a2a3", [move_to_coord(move) for move in moves])
        self.assertIn("h2h4", [move_to_coord(move) for move in moves])

    def test_width_two_initial_position_has_four_legal_moves(self) -> None:
        moves = legal_moves(initial_state(2), board_width=2)
        self.assertEqual([move_to_coord(move) for move in moves], ["a2a3", "a2a4", "b2b3", "b2b4"])

    def test_after_e4_black_has_16_legal_moves(self) -> None:
        state = play_coord_moves(initial_state(), ["e2e4"])
        self.assertEqual(len(legal_moves(state)), 16)

    def test_normal_capture_after_e4_d5(self) -> None:
        state = play_coord_moves(initial_state(), ["e2e4", "d7d5"])
        moves = legal_moves(state)
        capture = find_legal_move(state, "e4d5")
        self.assertIn(capture, moves)
        self.assertTrue(capture.flags & FLAG_CAPTURE)
        self.assertFalse(capture.flags & FLAG_EN_PASSANT)

    def test_en_passant_after_e4_d5_exd5_e5(self) -> None:
        state = play_coord_moves(initial_state(), ["e2e4", "d7d5", "e4d5", "e7e5"])
        ep_move = find_legal_move(state, "d5e6")
        self.assertTrue(ep_move.flags & FLAG_EN_PASSANT)
        next_state = make_move(state, ep_move)
        self.assertIn(algebraic_to_square("e6"), iter_squares(next_state.white))
        self.assertNotIn(algebraic_to_square("e5"), iter_squares(next_state.black))

    def test_en_passant_only_immediately_following_move(self) -> None:
        state = play_coord_moves(initial_state(), ["e2e4", "a7a6", "e4e5", "d7d5"])
        self.assertTrue(find_legal_move(state, "e5d6").flags & FLAG_EN_PASSANT)

        state = play_coord_moves(state, ["a2a3", "a6a5"])
        self.assertNotIn("e5d6", [move_to_coord(move) for move in legal_moves(state)])

    def test_a_file_and_h_file_captures_do_not_wrap(self) -> None:
        a_file_state = state_with(["a2"], ["h3"], WHITE)
        h_file_state = state_with(["h2"], ["a3"], WHITE)
        self.assertNotIn("a2h3", [move_to_coord(move) for move in legal_moves(a_file_state)])
        self.assertNotIn("h2a3", [move_to_coord(move) for move in legal_moves(h_file_state)])

    def test_width_two_right_edge_captures_do_not_enter_c_file(self) -> None:
        state = state_with(["b2"], ["c3"], WHITE)
        coords = [move_to_coord(move) for move in legal_moves(state, board_width=2)]
        self.assertNotIn("b2c3", coords)

    def test_edge_file_captures_to_adjacent_files_are_legal(self) -> None:
        state = state_with(["a2", "h2"], ["b3", "g3"], WHITE)
        coords = [move_to_coord(move) for move in legal_moves(state)]
        self.assertIn("a2b3", coords)
        self.assertIn("h2g3", coords)

    def test_deterministic_move_ordering(self) -> None:
        coords = [move_to_coord(move) for move in legal_moves(initial_state())]
        self.assertEqual(coords[:4], ["a2a3", "a2a4", "b2b3", "b2b4"])
        self.assertEqual(coords[-2:], ["h2h3", "h2h4"])


class MakeMoveAndTerminalTests(unittest.TestCase):
    def test_make_double_move_sets_ep_only_if_capturable_after_normalization(self) -> None:
        state = state_with(["e2"], ["d4"], WHITE)
        next_state = make_move(state, find_legal_move(state, "e2e4"))
        self.assertEqual(next_state.turn, BLACK)
        self.assertEqual(next_state.ep_square, algebraic_to_square("e3"))

        initial_after_e4 = make_move(initial_state(), find_legal_move(initial_state(), "e2e4"))
        self.assertEqual(initial_after_e4.ep_square, NO_EP)

    def test_make_move_rejects_illegal_move_by_default(self) -> None:
        with self.assertRaises(ValueError):
            make_move(
                initial_state(),
                Move(algebraic_to_square("e2"), algebraic_to_square("e5")),
            )

    def test_pawn_reaching_final_rank_ends_game_immediately(self) -> None:
        state = state_with(["a7"], [], WHITE)
        move = find_legal_move(state, "a7a8")
        self.assertTrue(move.flags & FLAG_WINNING)
        final_state = make_move(state, move)
        self.assertTrue(is_terminal(final_state))
        self.assertEqual(terminal_winner(final_state), WHITE)
        self.assertEqual(legal_moves(final_state), ())

    def test_black_pawn_reaching_final_rank_ends_game_immediately(self) -> None:
        state = state_with([], ["h2"], BLACK)
        move = find_legal_move(state, "h2h1")
        self.assertTrue(move.flags & FLAG_WINNING)
        final_state = make_move(state, move)
        self.assertTrue(is_terminal(final_state))
        self.assertEqual(terminal_winner(final_state), BLACK)
        self.assertEqual(legal_moves(final_state), ())

    def test_player_with_no_legal_move_has_empty_move_list(self) -> None:
        state = state_with(["a2"], ["a3"], WHITE)
        self.assertFalse(is_terminal(state))
        self.assertEqual(legal_moves(state), ())


class PerftTests(unittest.TestCase):
    def test_perft_depth_zero(self) -> None:
        self.assertEqual(perft(initial_state(), 0), 1)

    def test_perft_initial_depths(self) -> None:
        self.assertEqual(perft(initial_state(), 1), 16)
        self.assertEqual(perft(initial_state(), 2), 256)

    def test_width_two_perft_initial_depths(self) -> None:
        self.assertEqual(perft(initial_state(2), 1, board_width=2), 4)
        self.assertEqual(perft(initial_state(2), 2, board_width=2), 16)

    def test_perft_rejects_negative_depth(self) -> None:
        with self.assertRaises(ValueError):
            perft(initial_state(), -1)


if __name__ == "__main__":
    unittest.main()
