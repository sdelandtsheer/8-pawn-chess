"""State-space measurement tools for 8-pawn chess."""

from __future__ import annotations

import argparse
import sys
import time
import tracemalloc
from collections import Counter
from dataclasses import dataclass

from rules import (
    BLACK,
    WHITE,
    State,
    initial_state,
    iter_squares,
    legal_moves,
    make_move,
    normalize_state,
    rank_index,
    state_key,
    terminal_winner,
)
from solve import LOSS, WIN, SolveLimitReachedError, Solver, _unpack_result


@dataclass(frozen=True, slots=True)
class ReachabilityMeasurement:
    complete: bool
    unique_states: int
    max_depth: int
    elapsed_seconds: float
    peak_memory_bytes: int
    potential_counts: dict[int, int]
    terminal_states: int
    no_move_loss_states: int
    white_win_terminals: int
    black_win_terminals: int


@dataclass(frozen=True, slots=True)
class SolveMeasurement:
    complete: bool
    elapsed_seconds: float
    states_entered: int
    states_solved: int
    cache_hits: int
    max_depth: int
    win_states: int
    loss_states: int
    initial_outcome: int | None
    initial_dtm: int | None
    initial_best_move: int | None


def remaining_potential(state: State) -> int:
    normalized = normalize_state(state)
    white_distance = sum(7 - rank_index(square) for square in iter_squares(normalized.white))
    black_distance = sum(rank_index(square) for square in iter_squares(normalized.black))
    return white_distance + black_distance


def measure_reachable(start: State, *, max_states: int | None = None) -> ReachabilityMeasurement:
    if max_states is not None and max_states < 1:
        raise ValueError("max_states must be positive when set")

    started = time.perf_counter()
    tracemalloc.start()
    visited: set[int] = set()
    stack: list[tuple[State, int]] = [(normalize_state(start), 0)]
    potential_counts: Counter[int] = Counter()
    max_depth = 0
    terminal_states = 0
    no_move_loss_states = 0
    white_win_terminals = 0
    black_win_terminals = 0
    complete = True

    while stack:
        state, depth = stack.pop()
        key = state_key(state)
        if key in visited:
            continue
        if max_states is not None and len(visited) >= max_states:
            complete = False
            break

        visited.add(key)
        max_depth = max(max_depth, depth)
        potential_counts[remaining_potential(state)] += 1

        winner = terminal_winner(state)
        moves = legal_moves(state)
        if winner is not None:
            terminal_states += 1
            if winner == WHITE:
                white_win_terminals += 1
            elif winner == BLACK:
                black_win_terminals += 1
        elif not moves:
            no_move_loss_states += 1

        if winner is None and moves:
            for move in reversed(moves):
                stack.append((make_move(state, move, validate=False), depth + 1))

    _, peak_memory_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    elapsed = time.perf_counter() - started
    return ReachabilityMeasurement(
        complete=complete,
        unique_states=len(visited),
        max_depth=max_depth,
        elapsed_seconds=elapsed,
        peak_memory_bytes=peak_memory_bytes,
        potential_counts=dict(sorted(potential_counts.items())),
        terminal_states=terminal_states,
        no_move_loss_states=no_move_loss_states,
        white_win_terminals=white_win_terminals,
        black_win_terminals=black_win_terminals,
    )


def measure_solve(
    start: State,
    *,
    progress_interval: int = 0,
    max_entered_states: int | None = None,
) -> SolveMeasurement:
    solver = Solver(
        progress_interval=progress_interval,
        max_entered_states=max_entered_states,
    )
    started = time.perf_counter()
    try:
        result = solver.solve(start)
        complete = True
    except SolveLimitReachedError:
        result = None
        complete = False

    elapsed = time.perf_counter() - started
    outcomes = Counter(_unpack_result(result).outcome for result in solver.memo.values())
    return SolveMeasurement(
        complete=complete,
        elapsed_seconds=elapsed,
        states_entered=solver.stats.states_entered,
        states_solved=solver.stats.states_solved,
        cache_hits=solver.stats.cache_hits,
        max_depth=solver.stats.max_depth,
        win_states=outcomes[WIN],
        loss_states=outcomes[LOSS],
        initial_outcome=None if result is None else result.outcome,
        initial_dtm=None if result is None else result.dtm,
        initial_best_move=None if result is None else result.best_move,
    )


def _print_reachability(measurement: ReachabilityMeasurement) -> None:
    print(f"complete: {measurement.complete}")
    print(f"unique states: {measurement.unique_states}")
    print(f"max depth: {measurement.max_depth}")
    print(f"elapsed: {measurement.elapsed_seconds:.3f}s")
    print(f"peak memory: {measurement.peak_memory_bytes} bytes")
    print(f"terminal states: {measurement.terminal_states}")
    print(f"no-move loss states: {measurement.no_move_loss_states}")
    print(f"white win terminals: {measurement.white_win_terminals}")
    print(f"black win terminals: {measurement.black_win_terminals}")
    print("states by potential:")
    for potential, count in measurement.potential_counts.items():
        print(f"  {potential}: {count}")


def _print_solve(measurement: SolveMeasurement) -> None:
    print(f"solve complete: {measurement.complete}")
    print(f"solve elapsed: {measurement.elapsed_seconds:.3f}s")
    print(f"states entered: {measurement.states_entered}")
    print(f"states solved: {measurement.states_solved}")
    print(f"cache hits: {measurement.cache_hits}")
    print(f"max recursion depth: {measurement.max_depth}")
    print(f"WIN states: {measurement.win_states}")
    print(f"LOSS states: {measurement.loss_states}")
    print(f"initial outcome: {measurement.initial_outcome}")
    print(f"initial DTM: {measurement.initial_dtm}")
    print(f"initial best move: {measurement.initial_best_move}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Measure 8-pawn chess state space.")
    parser.add_argument(
        "--max-states",
        type=int,
        default=None,
        help="stop reachability traversal after this many unique states",
    )
    parser.add_argument(
        "--solve",
        action="store_true",
        help="also run the recursive solver measurement",
    )
    parser.add_argument(
        "--solve-max-entered",
        type=int,
        default=None,
        help="stop solver after this many entered uncached states",
    )
    parser.add_argument(
        "--progress",
        type=int,
        default=100_000,
        help="solver progress interval when --solve is used",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    reachability = measure_reachable(initial_state(), max_states=args.max_states)
    _print_reachability(reachability)
    if args.solve:
        print()
        solve_measurement = measure_solve(
            initial_state(),
            progress_interval=args.progress,
            max_entered_states=args.solve_max_entered,
        )
        _print_solve(solve_measurement)
        if not solve_measurement.complete:
            return 2
    return 0 if reachability.complete else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
