import os
import unittest

from rules import (
    find_legal_move,
    initial_state,
    legal_moves,
    move_to_coord,
    perft,
    play_coord_moves,
)
from solve import LOSS, Solver, best_move_to_text
from validation import assert_state_invariants, perft_divide, random_playout, snapshot

TACTICAL_BAD_BROWSER_LINE = (
    "e2e4",
    "c7c5",
    "c2c4",
    "d7d5",
    "e4d5",
    "e7e5",
    "d5e6",
)

DELAY_LOSS_LINE = (
    "d2d4",
    "a7a5",
    "c2c3",
    "b7b5",
    "b2b3",
    "c7c5",
    "d4c5",
    "e7e5",
    "e2e4",
    "f7f5",
    "e4f5",
    "h7h5",
    "h2h4",
    "b5b4",
    "c3b4",
)


class ValidationTests(unittest.TestCase):
    def test_snapshot_contains_normalized_key_and_deterministic_moves(self) -> None:
        snap = snapshot(initial_state())
        self.assertFalse(snap.terminal)
        self.assertEqual(len(snap.legal_move_codes), 16)
        self.assertEqual(snap.legal_move_coords[:4], ("a2a3", "a2a4", "b2b3", "b2b4"))

    def test_perft_divide_sums_to_perft(self) -> None:
        divide = perft_divide(initial_state(), 2)
        self.assertEqual(len(divide), 16)
        self.assertEqual(sum(count for _, count in divide), perft(initial_state(), 2))

    def test_perft_divide_rejects_depth_zero(self) -> None:
        with self.assertRaises(ValueError):
            perft_divide(initial_state(), 0)

    def test_random_playouts_are_deterministic_for_seed(self) -> None:
        first = random_playout(initial_state(), seed=20260625, max_plies=30)
        second = random_playout(initial_state(), seed=20260625, max_plies=30)
        self.assertEqual(first.moves, second.moves)
        self.assertEqual(first.states, second.states)

    def test_random_reachable_positions_keep_invariants(self) -> None:
        for seed in range(20):
            with self.subTest(seed=seed):
                playout = random_playout(initial_state(), seed=seed, max_plies=60)
                for state in playout.states:
                    assert_state_invariants(state)

    def test_tactical_bad_browser_position_has_critical_capture_available(self) -> None:
        state = play_coord_moves(initial_state(), TACTICAL_BAD_BROWSER_LINE)
        coords = [move_to_coord(move) for move in legal_moves(state)]
        self.assertIn("f7e6", coords)
        self.assertIn("f7f5", coords)
        capture = find_legal_move(state, "f7e6")
        self.assertNotEqual(capture.flags, 0)

    def test_delay_loss_regression_position_is_reachable(self) -> None:
        state = play_coord_moves(initial_state(), DELAY_LOSS_LINE)
        assert_state_invariants(state)
        self.assertGreater(len(legal_moves(state)), 0)

    @unittest.skipUnless(
        os.getenv("RUN_SLOW_SOLVER_TESTS") == "1",
        "set RUN_SLOW_SOLVER_TESTS=1 to run expensive tactical solver regressions",
    )
    def test_slow_solver_rejects_bad_browser_f5_move_if_losing(self) -> None:
        state = play_coord_moves(initial_state(), TACTICAL_BAD_BROWSER_LINE)
        result = Solver(progress_interval=100_000).solve(state)
        self.assertNotEqual(best_move_to_text(result), "f7f5")

    @unittest.skipUnless(
        os.getenv("RUN_SLOW_SOLVER_TESTS") == "1",
        "set RUN_SLOW_SOLVER_TESTS=1 to run expensive tactical solver regressions",
    )
    def test_slow_solver_delay_loss_position_uses_loss_dtm_convention(self) -> None:
        state = play_coord_moves(initial_state(), DELAY_LOSS_LINE)
        solver = Solver(progress_interval=100_000)
        result = solver.solve(state)
        if result.outcome == LOSS:
            best = find_legal_move(state, best_move_to_text(result))
            child = solver.solve(__import__("rules").make_move(state, best, validate=False))
            self.assertEqual(child.dtm, result.dtm - 1)


if __name__ == "__main__":
    unittest.main()
