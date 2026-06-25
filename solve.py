"""Exact recursive solver prototype for 8-pawn chess."""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from typing import NamedTuple

from rules import (
    FLAG_WINNING,
    Move,
    State,
    decode_move,
    encode_move,
    initial_state,
    legal_moves,
    make_move,
    move_to_coord,
    normalize_state,
    state_from_key,
    state_key,
    terminal_winner,
)

WIN = 1
LOSS = -1
NO_MOVE = -1


class Result(NamedTuple):
    """Compact cached solver result."""

    outcome: int
    dtm: int
    best_move: int


class SolveLimitReachedError(RuntimeError):
    """Raised when an optional measurement limit stops the DFS."""


@dataclass(slots=True)
class SolverStats:
    states_entered: int = 0
    states_solved: int = 0
    cache_hits: int = 0
    max_depth: int = 0


class Solver:
    """Memoized depth-first exact solver.

    The game graph is acyclic because pawn motion only reduces the remaining
    distance-to-goal potential, so recursion does not need draw detection.
    """

    def __init__(
        self,
        *,
        progress_interval: int = 0,
        max_entered_states: int | None = None,
        progress_stream=sys.stderr,
    ) -> None:
        if progress_interval < 0:
            raise ValueError("progress_interval must be non-negative")
        if max_entered_states is not None and max_entered_states < 1:
            raise ValueError("max_entered_states must be positive when set")
        self.memo: dict[int, Result] = {}
        self.stats = SolverStats()
        self.progress_interval = progress_interval
        self.max_entered_states = max_entered_states
        self.progress_stream = progress_stream
        self._started_at = time.perf_counter()
        self._last_progress_entered = 0

    def solve(self, state: State) -> Result:
        return self._solve_key(state_key(normalize_state(state)), depth=0)

    def _solve_key(self, key: int, *, depth: int) -> Result:
        cached = self.memo.get(key)
        if cached is not None:
            self.stats.cache_hits += 1
            return cached

        self.stats.max_depth = max(self.stats.max_depth, depth)
        self.stats.states_entered += 1
        if (
            self.max_entered_states is not None
            and self.stats.states_entered > self.max_entered_states
        ):
            raise SolveLimitReachedError(
                f"stopped after entering {self.stats.states_entered} uncached states"
            )
        self._log_progress()
        state = state_from_key(key)

        if terminal_winner(state) is not None:
            return self._store(key, Result(LOSS, 0, NO_MOVE))

        moves = legal_moves(state)
        if not moves:
            return self._store(key, Result(LOSS, 0, NO_MOVE))

        for move in moves:
            if move.flags & FLAG_WINNING:
                return self._store(key, Result(WIN, 1, encode_move(move)))

        best_winning_move: Move | None = None
        best_win_dtm = sys.maxsize
        best_losing_move: Move | None = None
        best_loss_dtm = -1

        for move in moves:
            child = make_move(state, move, validate=False)
            child_result = self._solve_key(state_key(child), depth=depth + 1)

            current_dtm = child_result.dtm + 1
            if child_result.outcome == LOSS:
                if current_dtm == 1:
                    return self._store(key, Result(WIN, 1, encode_move(move)))
                if current_dtm < best_win_dtm:
                    best_win_dtm = current_dtm
                    best_winning_move = move
            elif current_dtm > best_loss_dtm:
                best_loss_dtm = current_dtm
                best_losing_move = move

        if best_winning_move is not None:
            return self._store(
                key,
                Result(WIN, best_win_dtm, encode_move(best_winning_move)),
            )

        if best_losing_move is None:
            raise RuntimeError("non-terminal state had moves but no best move was selected")

        return self._store(
            key,
            Result(LOSS, best_loss_dtm, encode_move(best_losing_move)),
        )

    def _store(self, key: int, result: Result) -> Result:
        self.memo[key] = result
        self.stats.states_solved += 1
        self._log_progress()
        return result

    def _log_progress(self) -> None:
        if (
            self.progress_interval
            and self.stats.states_entered
            and self.stats.states_entered % self.progress_interval == 0
            and self.stats.states_entered != self._last_progress_entered
        ):
            self._last_progress_entered = self.stats.states_entered
            elapsed = time.perf_counter() - self._started_at
            print(
                f"entered={self.stats.states_entered} "
                f"solved={self.stats.states_solved} "
                f"cache_hits={self.stats.cache_hits} "
                f"max_depth={self.stats.max_depth} "
                f"elapsed={elapsed:.2f}s",
                file=self.progress_stream,
                flush=True,
            )


def best_move_to_text(result: Result) -> str:
    if result.best_move == NO_MOVE:
        return "none"
    return move_to_coord(decode_move(result.best_move))


def solve_initial(
    progress_interval: int,
    max_entered_states: int | None = None,
) -> tuple[Result, Solver, float]:
    solver = Solver(
        progress_interval=progress_interval,
        max_entered_states=max_entered_states,
    )
    started = time.perf_counter()
    result = solver.solve(initial_state())
    elapsed = time.perf_counter() - started
    return result, solver, elapsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Solve the 8-pawn chess initial position.")
    parser.add_argument(
        "--progress",
        type=int,
        default=100_000,
        help="print progress every N entered uncached states; 0 disables progress logging",
    )
    parser.add_argument(
        "--max-entered",
        type=int,
        default=None,
        help="stop after entering this many uncached states; useful for bounded measurement",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result, solver, elapsed = solve_initial(args.progress, args.max_entered)
    except SolveLimitReachedError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"states entered: {solver.stats.states_entered}")
    print(f"states solved: {solver.stats.states_solved}")
    print(f"cache hits: {solver.stats.cache_hits}")
    print(f"max recursion depth: {solver.stats.max_depth}")
    print(f"time used: {elapsed:.3f}s")
    print(f"initial outcome: {'WIN' if result.outcome == WIN else 'LOSS'}")
    print(f"initial best move: {best_move_to_text(result)}")
    print(f"initial DTM: {result.dtm}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
