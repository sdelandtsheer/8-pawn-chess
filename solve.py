"""Exact recursive solver prototype for 8-pawn chess."""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from typing import NamedTuple

from rules import (
    ALL_SQUARES,
    BLACK,
    FLAG_CAPTURE,
    FLAG_DOUBLE,
    FLAG_EN_PASSANT,
    FLAG_WINNING,
    NO_EP,
    RANK_1,
    RANK_8,
    WHITE,
    State,
    decode_move,
    initial_state,
    move_to_coord,
    normalize_state,
    square_to_algebraic,
    state_key,
    validate_board_width,
)

WIN = 1
LOSS = -1
NO_MOVE = -1
MOVE_SORT_MASK = 0x3F
EP_CODE_MASK = 0x7F
NO_MOVE_CODE = 0
MIRRORED_BYTES = tuple(
    sum(((value >> source_file) & 1) << (7 - source_file) for source_file in range(8))
    for value in range(256)
)


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
        board_width: int = 8,
        use_symmetry: bool = False,
        trace_depth: int = -1,
        log_moves: bool = False,
        progress_stream=sys.stderr,
    ) -> None:
        validate_board_width(board_width)
        if progress_interval < 0:
            raise ValueError("progress_interval must be non-negative")
        if max_entered_states is not None and max_entered_states < 1:
            raise ValueError("max_entered_states must be positive when set")
        if trace_depth < -1:
            raise ValueError("trace_depth must be -1 or greater")
        self.memo: dict[int, int] = {}
        self.stats = SolverStats()
        self.progress_interval = progress_interval
        self.max_entered_states = max_entered_states
        self.board_width = board_width
        self.use_symmetry = use_symmetry
        self.trace_depth = trace_depth
        self.log_moves = log_moves
        self.progress_stream = progress_stream
        self._started_at = time.perf_counter()
        self._last_progress_entered = 0
        self._path: list[int] = []

    def solve(self, state: State) -> Result:
        normalized = normalize_state(state, self.board_width)
        return _unpack_result(self._solve_key(state_key(normalized, self.board_width), depth=0))

    def _solve_key(self, key: int, *, depth: int) -> int:
        if not self.use_symmetry:
            return self._solve_canonical_key(key, depth=depth)
        canonical_key, mirrored = _canonicalize_key(key, self.board_width)
        result = self._solve_canonical_key(canonical_key, depth=depth)
        return _mirror_result(result, self.board_width) if mirrored else result

    def _solve_canonical_key(self, key: int, *, depth: int) -> int:
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

        white, black, turn, ep_square = _unpack_key(key)
        self._trace_state(key, depth, white, black, turn, ep_square)
        if _is_terminal_parts(white, black):
            return self._store(key, _pack_result(LOSS, 0, NO_MOVE))

        moves = _legal_move_codes(white, black, turn, ep_square, self.board_width)
        self._trace_moves(depth, moves)
        if not moves:
            return self._store(key, _pack_result(LOSS, 0, NO_MOVE))

        for move_code in moves:
            if _move_flags(move_code) & FLAG_WINNING:
                return self._store(key, _pack_result(WIN, 1, move_code))

        best_winning_move = NO_MOVE
        best_win_dtm = sys.maxsize
        best_losing_move = NO_MOVE
        best_loss_dtm = -1

        for move_code in moves:
            self._trace_considered_move(depth, move_code)
            child_key = _make_move_key(white, black, turn, move_code, self.board_width)
            self._path.append(move_code)
            child_outcome, child_dtm, _ = _unpack_result_parts(
                self._solve_key(child_key, depth=depth + 1)
            )
            self._path.pop()

            current_dtm = child_dtm + 1
            if child_outcome == LOSS:
                if current_dtm == 1:
                    return self._store(key, _pack_result(WIN, 1, move_code))
                if current_dtm < best_win_dtm:
                    best_win_dtm = current_dtm
                    best_winning_move = move_code
            elif current_dtm > best_loss_dtm:
                best_loss_dtm = current_dtm
                best_losing_move = move_code

        if best_winning_move != NO_MOVE:
            return self._store(
                key,
                _pack_result(WIN, best_win_dtm, best_winning_move),
            )

        if best_losing_move == NO_MOVE:
            raise RuntimeError("non-terminal state had moves but no best move was selected")

        return self._store(
            key,
            _pack_result(LOSS, best_loss_dtm, best_losing_move),
        )

    def _trace_state(
        self,
        key: int,
        depth: int,
        white: int,
        black: int,
        turn: int,
        ep_square: int,
    ) -> None:
        if self.trace_depth < 0 or depth > self.trace_depth:
            return
        print(
            f"tree depth={depth} path={_path_to_text(self._path)} "
            f"turn={'white' if turn == WHITE else 'black'} "
            f"key={key:x} white={_bitboard_to_text(white)} black={_bitboard_to_text(black)} "
            f"ep={'none' if ep_square == NO_EP else square_to_algebraic(ep_square)}",
            file=self.progress_stream,
            flush=True,
        )

    def _trace_moves(self, depth: int, moves: list[int]) -> None:
        if self.trace_depth < 0 or depth > self.trace_depth:
            return
        move_text = ",".join(_move_to_text(move) for move in moves) or "none"
        print(
            f"tree depth={depth} legal_moves={move_text}",
            file=self.progress_stream,
            flush=True,
        )

    def _trace_considered_move(self, depth: int, move_code: int) -> None:
        if not self.log_moves:
            return
        if self.trace_depth >= 0 and depth > self.trace_depth:
            return
        print(
            f"tree depth={depth} considering={_move_to_text(move_code)} "
            f"path={_path_to_text([*self._path, move_code])}",
            file=self.progress_stream,
            flush=True,
        )

    def _store(self, key: int, result: int) -> int:
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


def _pack_result(outcome: int, dtm: int, best_move: int) -> int:
    if outcome not in (WIN, LOSS):
        raise ValueError(f"invalid outcome: {outcome}")
    if dtm < 0:
        raise ValueError(f"dtm must be non-negative: {dtm}")
    move_field = NO_MOVE_CODE if best_move == NO_MOVE else best_move + 1
    if move_field < 0 or move_field > 0x10000:
        raise ValueError(f"invalid best move: {best_move}")
    outcome_bit = 1 if outcome == WIN else 0
    return outcome_bit | (dtm << 1) | (move_field << 17)


def _unpack_result_parts(packed: int) -> tuple[int, int, int]:
    outcome = WIN if packed & 1 else LOSS
    dtm = (packed >> 1) & 0xFFFF
    move_field = packed >> 17
    best_move = NO_MOVE if move_field == NO_MOVE_CODE else move_field - 1
    return outcome, dtm, best_move


def _unpack_result(packed: int) -> Result:
    return Result(*_unpack_result_parts(packed))


def _move_to_text(move_code: int) -> str:
    if move_code == NO_MOVE:
        return "none"
    return f"{square_to_algebraic(_move_from(move_code))}{square_to_algebraic(_move_to(move_code))}"


def _path_to_text(path: list[int]) -> str:
    return "(root)" if not path else " ".join(_move_to_text(move) for move in path)


def _bitboard_to_text(bitboard: int) -> str:
    squares: list[str] = []
    remaining = bitboard
    while remaining:
        square_bit = remaining & -remaining
        square = square_bit.bit_length() - 1
        squares.append(square_to_algebraic(square))
        remaining ^= square_bit
    return ",".join(squares) or "-"


def _mirror_square(square: int, board_width: int = 8) -> int:
    validate_board_width(board_width)
    rank = square & ~7
    file_ = square & 7
    return rank + board_width - 1 - file_


def _mirror_bitboard(bitboard: int, board_width: int = 8) -> int:
    validate_board_width(board_width)
    if board_width == 8:
        return (
            MIRRORED_BYTES[bitboard & 0xFF]
            | (MIRRORED_BYTES[(bitboard >> 8) & 0xFF] << 8)
            | (MIRRORED_BYTES[(bitboard >> 16) & 0xFF] << 16)
            | (MIRRORED_BYTES[(bitboard >> 24) & 0xFF] << 24)
            | (MIRRORED_BYTES[(bitboard >> 32) & 0xFF] << 32)
            | (MIRRORED_BYTES[(bitboard >> 40) & 0xFF] << 40)
            | (MIRRORED_BYTES[(bitboard >> 48) & 0xFF] << 48)
            | (MIRRORED_BYTES[(bitboard >> 56) & 0xFF] << 56)
        )
    mirrored = 0
    remaining = bitboard
    while remaining:
        square_bit = remaining & -remaining
        square = square_bit.bit_length() - 1
        mirrored |= 1 << _mirror_square(square, board_width)
        remaining ^= square_bit
    return mirrored


def _mirror_move(move_code: int, board_width: int = 8) -> int:
    if move_code == NO_MOVE:
        return NO_MOVE
    return _encode_move_parts(
        _mirror_square(_move_from(move_code), board_width),
        _mirror_square(_move_to(move_code), board_width),
        _move_flags(move_code),
    )


def _mirror_result(packed: int, board_width: int = 8) -> int:
    outcome, dtm, best_move = _unpack_result_parts(packed)
    return _pack_result(outcome, dtm, _mirror_move(best_move, board_width))


def _mirror_key(key: int, board_width: int = 8) -> int:
    white, black, turn, ep_square = _unpack_key(key)
    mirrored_ep = NO_EP if ep_square == NO_EP else _mirror_square(ep_square, board_width)
    return _pack_key(
        _mirror_bitboard(white, board_width),
        _mirror_bitboard(black, board_width),
        turn,
        mirrored_ep,
        board_width,
    )


def _canonicalize_key(key: int, board_width: int = 8) -> tuple[int, bool]:
    mirrored = _mirror_key(key, board_width)
    if mirrored < key:
        return mirrored, True
    return key, False


def _pack_key(white: int, black: int, turn: int, ep_square: int, board_width: int = 8) -> int:
    ep_square = _normalize_ep_square(white, black, turn, ep_square, board_width)
    ep_code = 0 if ep_square == NO_EP else ep_square + 1
    return white | (black << 64) | (turn << 128) | (ep_code << 129)


def _unpack_key(key: int) -> tuple[int, int, int, int]:
    white = key & ALL_SQUARES
    black = (key >> 64) & ALL_SQUARES
    turn = (key >> 128) & 1
    ep_code = (key >> 129) & EP_CODE_MASK
    ep_square = NO_EP if ep_code == 0 else ep_code - 1
    return white, black, turn, ep_square


def _normalize_ep_square(
    white: int,
    black: int,
    turn: int,
    ep_square: int,
    board_width: int = 8,
) -> int:
    if ep_square == NO_EP:
        return NO_EP
    if not _ep_capture_exists(white, black, turn, ep_square, board_width):
        return NO_EP
    return ep_square


def _ep_capture_exists(
    white: int,
    black: int,
    turn: int,
    ep_square: int,
    board_width: int = 8,
) -> bool:
    ep_file = ep_square & 7
    if ep_file >= board_width:
        return False
    if turn == WHITE:
        captured_square = ep_square - 8
        if captured_square < 0 or not (black & (1 << captured_square)):
            return False
        pawns = white
        candidates = (ep_square - 9, ep_square - 7)
    else:
        captured_square = ep_square + 8
        if captured_square >= 64 or not (white & (1 << captured_square)):
            return False
        pawns = black
        candidates = (ep_square + 7, ep_square + 9)

    for from_square in candidates:
        if (
            0 <= from_square < 64
            and abs((from_square & 7) - ep_file) == 1
            and pawns & (1 << from_square)
        ):
            return True
    return False


def _is_terminal_parts(white: int, black: int) -> bool:
    return bool((white & RANK_8) or (black & RANK_1))


def _encode_move_parts(from_square: int, to_square: int, flags: int) -> int:
    return from_square | (to_square << 6) | (flags << 12)


def _move_from(move_code: int) -> int:
    return move_code & MOVE_SORT_MASK


def _move_to(move_code: int) -> int:
    return (move_code >> 6) & MOVE_SORT_MASK


def _move_flags(move_code: int) -> int:
    return (move_code >> 12) & 0xF


def _move_sort_key(move_code: int) -> tuple[int, int, int]:
    return (_move_from(move_code), _move_to(move_code), _move_flags(move_code))


def _legal_move_codes(
    white: int,
    black: int,
    turn: int,
    ep_square: int,
    board_width: int = 8,
) -> list[int]:
    if _is_terminal_parts(white, black):
        return []

    occupied = white | black
    moves: list[int] = []
    if turn == WHITE:
        pawns = white
        enemies = black
        while pawns:
            pawn_bit = pawns & -pawns
            from_square = pawn_bit.bit_length() - 1
            pawns ^= pawn_bit

            file_ = from_square & 7
            if file_ > 0:
                target = from_square + 7
                target_bit = 1 << target
                if enemies & target_bit:
                    flags = FLAG_CAPTURE | (FLAG_WINNING if target >= 56 else 0)
                    moves.append(_encode_move_parts(from_square, target, flags))
                elif target == ep_square:
                    moves.append(
                        _encode_move_parts(
                            from_square,
                            target,
                            FLAG_CAPTURE | FLAG_EN_PASSANT,
                        )
                    )

            one_step = from_square + 8
            one_step_is_empty = one_step < 64 and not (occupied & (1 << one_step))
            if one_step_is_empty:
                flags = FLAG_WINNING if one_step >= 56 else 0
                moves.append(_encode_move_parts(from_square, one_step, flags))

            if file_ < board_width - 1:
                target = from_square + 9
                target_bit = 1 << target
                if enemies & target_bit:
                    flags = FLAG_CAPTURE | (FLAG_WINNING if target >= 56 else 0)
                    moves.append(_encode_move_parts(from_square, target, flags))
                elif target == ep_square:
                    moves.append(
                        _encode_move_parts(
                            from_square,
                            target,
                            FLAG_CAPTURE | FLAG_EN_PASSANT,
                        )
                    )

            if one_step_is_empty:
                two_step = from_square + 16
                if 8 <= from_square <= 15 and not (occupied & (1 << two_step)):
                    moves.append(_encode_move_parts(from_square, two_step, FLAG_DOUBLE))
    else:
        pawns = black
        enemies = white
        while pawns:
            pawn_bit = pawns & -pawns
            from_square = pawn_bit.bit_length() - 1
            pawns ^= pawn_bit

            one_step = from_square - 8
            one_step_is_empty = one_step >= 0 and not (occupied & (1 << one_step))
            if one_step_is_empty:
                two_step = from_square - 16
                if 48 <= from_square <= 55 and not (occupied & (1 << two_step)):
                    moves.append(_encode_move_parts(from_square, two_step, FLAG_DOUBLE))

            file_ = from_square & 7
            if file_ > 0:
                target = from_square - 9
                target_bit = 1 << target
                if enemies & target_bit:
                    flags = FLAG_CAPTURE | (FLAG_WINNING if target <= 7 else 0)
                    moves.append(_encode_move_parts(from_square, target, flags))
                elif target == ep_square:
                    moves.append(
                        _encode_move_parts(
                            from_square,
                            target,
                            FLAG_CAPTURE | FLAG_EN_PASSANT,
                        )
                    )

            if one_step_is_empty:
                flags = FLAG_WINNING if one_step <= 7 else 0
                moves.append(_encode_move_parts(from_square, one_step, flags))

            if file_ < board_width - 1:
                target = from_square - 7
                target_bit = 1 << target
                if enemies & target_bit:
                    flags = FLAG_CAPTURE | (FLAG_WINNING if target <= 7 else 0)
                    moves.append(_encode_move_parts(from_square, target, flags))
                elif target == ep_square:
                    moves.append(
                        _encode_move_parts(
                            from_square,
                            target,
                            FLAG_CAPTURE | FLAG_EN_PASSANT,
                        )
                    )

    return moves


def _make_move_key(
    white: int,
    black: int,
    turn: int,
    move_code: int,
    board_width: int = 8,
) -> int:
    from_square = _move_from(move_code)
    to_square = _move_to(move_code)
    flags = _move_flags(move_code)
    from_bit = 1 << from_square
    to_bit = 1 << to_square
    ep_square = NO_EP

    if turn == WHITE:
        white = (white & ~from_bit) | to_bit
        if flags & FLAG_EN_PASSANT:
            black &= ~(1 << (to_square - 8))
        else:
            black &= ~to_bit
        if flags & FLAG_DOUBLE:
            ep_square = from_square + 8
        return _pack_key(white, black, BLACK, ep_square, board_width)

    black = (black & ~from_bit) | to_bit
    if flags & FLAG_EN_PASSANT:
        white &= ~(1 << (to_square + 8))
    else:
        white &= ~to_bit
    if flags & FLAG_DOUBLE:
        ep_square = from_square - 8
    return _pack_key(white, black, WHITE, ep_square, board_width)


def best_move_to_text(result: Result) -> str:
    if result.best_move == NO_MOVE:
        return "none"
    return move_to_coord(decode_move(result.best_move))


def solve_initial(
    progress_interval: int,
    max_entered_states: int | None = None,
    board_width: int = 8,
    use_symmetry: bool = False,
    trace_depth: int = -1,
    log_moves: bool = False,
) -> tuple[Result, Solver, float]:
    solver = Solver(
        progress_interval=progress_interval,
        max_entered_states=max_entered_states,
        board_width=board_width,
        use_symmetry=use_symmetry,
        trace_depth=trace_depth,
        log_moves=log_moves,
    )
    started = time.perf_counter()
    result = solver.solve(initial_state(board_width))
    elapsed = time.perf_counter() - started
    return result, solver, elapsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Solve the 8-pawn chess initial position.")
    parser.add_argument(
        "--board-width",
        type=int,
        default=8,
        help="active board width: 2, 4, 6, or 8 files starting at a-file",
    )
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
    parser.add_argument(
        "--symmetry",
        action="store_true",
        help="canonicalize horizontal mirror positions internally",
    )
    parser.add_argument(
        "--trace-depth",
        type=int,
        default=-1,
        help="print tree state and legal moves down to this depth; -1 disables tracing",
    )
    parser.add_argument(
        "--log-moves",
        action="store_true",
        help="print each move considered within trace depth",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result, solver, elapsed = solve_initial(
            args.progress,
            args.max_entered,
            args.board_width,
            args.symmetry,
            args.trace_depth,
            args.log_moves,
        )
    except SolveLimitReachedError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"states entered: {solver.stats.states_entered}")
    print(f"states solved: {solver.stats.states_solved}")
    print(f"cache hits: {solver.stats.cache_hits}")
    print(f"max recursion depth: {solver.stats.max_depth}")
    print(f"time used: {elapsed:.3f}s")
    print(f"board width: {args.board_width}")
    print(f"initial outcome: {'WIN' if result.outcome == WIN else 'LOSS'}")
    print(f"initial best move: {best_move_to_text(result)}")
    print(f"initial DTM: {result.dtm}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
