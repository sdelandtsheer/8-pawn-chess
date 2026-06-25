import unittest

from measure import measure_reachable, measure_solve, remaining_potential
from rules import initial_state, play_coord_moves


class MeasurementTests(unittest.TestCase):
    def test_initial_potential(self) -> None:
        self.assertEqual(remaining_potential(initial_state()), 96)

    def test_potential_decreases_after_non_capture_move(self) -> None:
        state = play_coord_moves(initial_state(), ["e2e4"])
        self.assertEqual(remaining_potential(state), 94)

    def test_potential_decreases_after_capture(self) -> None:
        before_capture = play_coord_moves(initial_state(), ["e2e4", "d7d5"])
        after_capture = play_coord_moves(before_capture, ["e4d5"])
        self.assertLess(remaining_potential(after_capture), remaining_potential(before_capture))

    def test_bounded_reachability_measurement(self) -> None:
        measurement = measure_reachable(initial_state(), max_states=100)
        self.assertFalse(measurement.complete)
        self.assertEqual(measurement.unique_states, 100)
        self.assertGreater(measurement.max_depth, 0)
        self.assertGreater(measurement.peak_memory_bytes, 0)
        self.assertGreater(sum(measurement.potential_counts.values()), 0)

    def test_reachability_rejects_invalid_bound(self) -> None:
        with self.assertRaises(ValueError):
            measure_reachable(initial_state(), max_states=0)

    def test_bounded_solver_measurement(self) -> None:
        measurement = measure_solve(initial_state(), max_entered_states=100)
        self.assertFalse(measurement.complete)
        self.assertGreaterEqual(measurement.states_entered, 100)
        self.assertIsNone(measurement.initial_outcome)
        self.assertIsNone(measurement.initial_dtm)
        self.assertIsNone(measurement.initial_best_move)


if __name__ == "__main__":
    unittest.main()
