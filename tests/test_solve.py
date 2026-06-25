import unittest

from rules import (
    algebraic_to_square,
    bit,
    encode_move,
    find_legal_move,
    initial_state,
    legal_moves,
    make_move,
    state_key,
)
from solve import (
    LOSS,
    NO_MOVE,
    WIN,
    SolveLimitReachedError,
    Solver,
    _legal_move_codes,
    _make_move_key,
    _unpack_key,
    best_move_to_text,
)
from validation import random_playout


def state_with(white: list[str], black: list[str], turn: int):
    from rules import State

    white_bits = sum(bit(algebraic_to_square(square)) for square in white)
    black_bits = sum(bit(algebraic_to_square(square)) for square in black)
    return State(white_bits, black_bits, turn)


class SolverTests(unittest.TestCase):
    def test_terminal_state_is_loss_for_side_to_move(self) -> None:
        solver = Solver()
        state = state_with(["a8"], [], 1)
        result = solver.solve(state)
        self.assertEqual(result.outcome, LOSS)
        self.assertEqual(result.dtm, 0)
        self.assertEqual(result.best_move, NO_MOVE)

    def test_no_legal_move_is_loss(self) -> None:
        solver = Solver()
        state = state_with(["a2"], ["a3"], 0)
        result = solver.solve(state)
        self.assertEqual(result.outcome, LOSS)
        self.assertEqual(result.dtm, 0)
        self.assertEqual(result.best_move, NO_MOVE)

    def test_immediate_goal_move_is_fastest_win(self) -> None:
        solver = Solver()
        state = state_with(["a7", "b6"], ["h7"], 0)
        result = solver.solve(state)
        self.assertEqual(result.outcome, WIN)
        self.assertEqual(result.dtm, 1)
        self.assertEqual(best_move_to_text(result), "a7a8")

    def test_immediate_goal_move_does_not_search_siblings(self) -> None:
        solver = Solver()
        state = state_with(["a7", "b6"], ["h7"], 0)
        solver.solve(state)
        self.assertEqual(solver.stats.states_entered, 1)
        self.assertEqual(solver.stats.states_solved, 1)

    def test_solver_result_is_cached_by_normalized_key(self) -> None:
        solver = Solver()
        state = state_with(["a7"], [], 0)
        first = solver.solve(state)
        solved_after_first = solver.stats.states_solved
        second = solver.solve(state)
        self.assertEqual(first, second)
        self.assertEqual(solver.stats.states_solved, solved_after_first)
        self.assertEqual(solver.stats.cache_hits, 1)
        self.assertGreaterEqual(solver.stats.states_entered, 1)

    def test_solver_can_stop_at_measurement_limit(self) -> None:
        solver = Solver(max_entered_states=1)
        with self.assertRaises(SolveLimitReachedError):
            solver.solve(initial_state())

    def test_winning_move_leaves_opponent_with_loss_at_previous_dtm(self) -> None:
        solver = Solver()
        state = state_with(["a6"], [], 0)
        result = solver.solve(state)
        self.assertEqual(result.outcome, WIN)
        self.assertEqual(best_move_to_text(result), "a6a7")

        child = make_move(state, find_legal_move(state, best_move_to_text(result)))
        child_result = solver.solve(child)
        self.assertEqual(child_result.outcome, LOSS)
        self.assertEqual(child_result.dtm, result.dtm - 1)

    def test_solver_starts_with_empty_memo_for_initial_position(self) -> None:
        solver = Solver()
        state = initial_state()
        self.assertEqual(state.turn, 0)
        self.assertEqual(solver.memo, {})


class FastSolverParityTests(unittest.TestCase):
    def test_fast_move_generation_matches_rules_engine(self) -> None:
        samples = [initial_state()]
        samples.extend(
            random_playout(initial_state(), seed=seed, max_plies=20).states[-1]
            for seed in range(20)
        )

        for state in samples:
            with self.subTest(state=state):
                white, black, turn, ep_square = _unpack_key(state_key(state))
                self.assertEqual(
                    _legal_move_codes(white, black, turn, ep_square),
                    [encode_move(move) for move in legal_moves(state)],
                )

    def test_fast_make_move_matches_rules_engine_keys(self) -> None:
        samples = [initial_state()]
        samples.extend(
            random_playout(initial_state(), seed=seed, max_plies=30).states[-1]
            for seed in range(20)
        )

        for state in samples:
            white, black, turn, _ = _unpack_key(state_key(state))
            for move in legal_moves(state):
                with self.subTest(state=state, move=move):
                    self.assertEqual(
                        _make_move_key(white, black, turn, encode_move(move)),
                        state_key(make_move(state, move, validate=False)),
                    )


if __name__ == "__main__":
    unittest.main()
