"""Width-specific compact solver backend.

The public tablebase format still uses the standard 8x8 square numbering, but
this solver stores active files densely as `rank * board_width + file`. That
keeps keys smaller for width 2/4/6 and removes inactive-file checks from the hot
move generator.
"""

from __future__ import annotations

import argparse
import pickle
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from rules import (
    BLACK,
    FLAG_CAPTURE,
    FLAG_DOUBLE,
    FLAG_EN_PASSANT,
    FLAG_WINNING,
    NO_EP,
    WHITE,
    State,
    initial_state,
    square_to_algebraic,
    validate_board_width,
)
from solve import (
    LOSS,
    NO_MOVE,
    WIN,
    Result,
    SolveLimitReachedError,
    _pack_result,
    _unpack_result,
    _unpack_result_parts,
)


@dataclass(slots=True)
class CompactSolverStats:
    states_entered: int = 0
    states_solved: int = 0
    cache_hits: int = 0
    max_depth: int = 0


CHECKPOINT_VERSION = 1


class CompactSolver:
    """Memoized exact DFS using dense board-width-specific bitboards."""

    def __init__(
        self,
        *,
        board_width: int,
        progress_interval: int = 0,
        max_entered_states: int | None = None,
        trace_depth: int = -1,
        log_moves: bool = False,
        progress_path_depth: int = 8,
        checkpoint_path: Path | None = None,
        checkpoint_interval: int = 0,
        resume: bool = False,
        progress_stream=sys.stderr,
    ) -> None:
        validate_board_width(board_width)
        if progress_interval < 0:
            raise ValueError("progress_interval must be non-negative")
        if max_entered_states is not None and max_entered_states < 1:
            raise ValueError("max_entered_states must be positive when set")
        if trace_depth < -1:
            raise ValueError("trace_depth must be -1 or greater")
        if progress_path_depth < 0:
            raise ValueError("progress_path_depth must be non-negative")
        if checkpoint_interval < 0:
            raise ValueError("checkpoint_interval must be non-negative")

        self.board_width = board_width
        self.cells = board_width * 8
        self.mask = (1 << self.cells) - 1
        self.memo: dict[int, int] = {}
        self.stats = CompactSolverStats()
        self.progress_interval = progress_interval
        self.max_entered_states = max_entered_states
        self.trace_depth = trace_depth
        self.log_moves = log_moves
        self.progress_path_depth = progress_path_depth
        self.checkpoint_path = checkpoint_path
        self.checkpoint_interval = checkpoint_interval
        self.progress_stream = progress_stream
        self._started_at = time.perf_counter()
        self._last_progress_entered = 0
        self._last_checkpoint_solved = 0
        self._path: list[int] = []
        if resume:
            if checkpoint_path is None:
                raise ValueError("resume requires checkpoint_path")
            self.load_checkpoint(checkpoint_path)

    def solve(self, state: State) -> Result:
        return _unpack_result(self._solve_key(self.state_to_key(state), depth=0))

    def state_to_key(self, state: State) -> int:
        white = _standard_bitboard_to_dense(state.white, self.board_width)
        black = _standard_bitboard_to_dense(state.black, self.board_width)
        ep_square = (
            NO_EP
            if state.ep_square == NO_EP
            else _standard_to_dense_square(state.ep_square, self.board_width)
        )
        return self._pack_key(white, black, state.turn, ep_square)

    def initial_key(self) -> int:
        return self.state_to_key(initial_state(self.board_width))

    def initial_result(self) -> Result | None:
        packed = self.memo.get(self.initial_key())
        return None if packed is None else _unpack_result(packed)

    def iter_standard_entries(self):
        for key, packed_result in self.memo.items():
            yield self.standard_key_from_compact_key(key), packed_result

    def save_checkpoint(self, path: Path | None = None) -> None:
        target = path if path is not None else self.checkpoint_path
        if target is None:
            raise ValueError("checkpoint path is not configured")
        target.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target.with_suffix(target.suffix + ".tmp")
        payload = {
            "version": CHECKPOINT_VERSION,
            "board_width": self.board_width,
            "memo": self.memo,
            "stats": self.stats,
            "saved_at": time.time(),
        }
        try:
            with temp_path.open("wb") as file:
                pickle.dump(payload, file, protocol=pickle.HIGHEST_PROTOCOL)
            temp_path.replace(target)
            self._last_checkpoint_solved = self.stats.states_solved
            print(
                f"checkpoint={target} states={self.stats.states_solved}",
                file=self.progress_stream,
                flush=True,
            )
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

    def load_checkpoint(self, path: Path) -> None:
        with path.open("rb") as file:
            payload = pickle.load(file)
        if payload.get("version") != CHECKPOINT_VERSION:
            raise ValueError(f"unsupported checkpoint version in {path}")
        if payload.get("board_width") != self.board_width:
            raise ValueError(
                f"checkpoint board width {payload.get('board_width')} does not match "
                f"{self.board_width}"
            )
        memo = payload.get("memo")
        stats = payload.get("stats")
        if not isinstance(memo, dict) or not isinstance(stats, CompactSolverStats):
            raise ValueError(f"invalid checkpoint payload in {path}")
        self.memo = memo
        self.stats = stats
        self._last_checkpoint_solved = self.stats.states_solved
        print(
            f"resumed_checkpoint={path} states={self.stats.states_solved}",
            file=self.progress_stream,
            flush=True,
        )

    def standard_key_from_compact_key(self, key: int) -> int:
        white, black, turn, ep_square = self._unpack_key(key)
        standard_white = _dense_bitboard_to_standard(white, self.board_width)
        standard_black = _dense_bitboard_to_standard(black, self.board_width)
        standard_ep = (
            NO_EP if ep_square == NO_EP else _dense_to_standard_square(ep_square, self.board_width)
        )
        ep_code = 0 if standard_ep == NO_EP else standard_ep + 1
        return standard_white | (standard_black << 64) | (turn << 128) | (ep_code << 129)

    def _solve_key(self, key: int, *, depth: int) -> int:
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

        white, black, turn, ep_square = self._unpack_key(key)
        self._trace_state(key, depth, white, black, turn, ep_square)
        if self._is_terminal(white, black):
            return self._store(key, _pack_result(LOSS, 0, NO_MOVE))

        moves = self._legal_move_codes(white, black, turn, ep_square)
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
            child_key = self._make_move_key(white, black, turn, move_code)
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
            return self._store(key, _pack_result(WIN, best_win_dtm, best_winning_move))

        if best_losing_move == NO_MOVE:
            raise RuntimeError("non-terminal state had moves but no best move was selected")

        return self._store(key, _pack_result(LOSS, best_loss_dtm, best_losing_move))

    def _pack_key(self, white: int, black: int, turn: int, ep_square: int) -> int:
        ep_square = self._normalize_ep_square(white, black, turn, ep_square)
        ep_code = 0 if ep_square == NO_EP else ep_square + 1
        return (
            white
            | (black << self.cells)
            | (turn << (self.cells * 2))
            | (ep_code << (self.cells * 2 + 1))
        )

    def _unpack_key(self, key: int) -> tuple[int, int, int, int]:
        white = key & self.mask
        black = (key >> self.cells) & self.mask
        turn = (key >> (self.cells * 2)) & 1
        ep_code = key >> (self.cells * 2 + 1)
        ep_square = NO_EP if ep_code == 0 else ep_code - 1
        return white, black, turn, ep_square

    def _normalize_ep_square(self, white: int, black: int, turn: int, ep_square: int) -> int:
        if ep_square == NO_EP:
            return NO_EP
        if not self._ep_capture_exists(white, black, turn, ep_square):
            return NO_EP
        return ep_square

    def _ep_capture_exists(self, white: int, black: int, turn: int, ep_square: int) -> bool:
        ep_file = ep_square % self.board_width
        ep_rank = ep_square // self.board_width
        if turn == WHITE:
            captured_square = ep_square - self.board_width
            if captured_square < 0 or not (black & (1 << captured_square)):
                return False
            pawns = white
            from_rank = ep_rank - 1
        else:
            captured_square = ep_square + self.board_width
            if captured_square >= self.cells or not (white & (1 << captured_square)):
                return False
            pawns = black
            from_rank = ep_rank + 1

        if not 0 <= from_rank < 8:
            return False

        for from_file in (ep_file - 1, ep_file + 1):
            if not 0 <= from_file < self.board_width:
                continue
            from_square = from_rank * self.board_width + from_file
            if pawns & (1 << from_square):
                return True
        return False

    def _is_terminal(self, white: int, black: int) -> bool:
        rank_8 = ((1 << self.board_width) - 1) << (7 * self.board_width)
        rank_1 = (1 << self.board_width) - 1
        return bool((white & rank_8) or (black & rank_1))

    def _legal_move_codes(self, white: int, black: int, turn: int, ep_square: int) -> list[int]:
        if self._is_terminal(white, black):
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
                file_ = from_square % self.board_width

                if file_ > 0:
                    self._append_capture_or_ep(
                        moves,
                        from_square,
                        from_square + self.board_width - 1,
                        enemies,
                        ep_square,
                        True,
                    )

                one_step = from_square + self.board_width
                one_step_empty = one_step < self.cells and not (occupied & (1 << one_step))
                if one_step_empty:
                    flags = FLAG_WINNING if one_step // self.board_width == 7 else 0
                    moves.append(self._encode_dense_move(from_square, one_step, flags))

                if file_ < self.board_width - 1:
                    self._append_capture_or_ep(
                        moves,
                        from_square,
                        from_square + self.board_width + 1,
                        enemies,
                        ep_square,
                        True,
                    )

                if one_step_empty and from_square // self.board_width == 1:
                    two_step = from_square + 2 * self.board_width
                    if not (occupied & (1 << two_step)):
                        moves.append(self._encode_dense_move(from_square, two_step, FLAG_DOUBLE))
        else:
            pawns = black
            enemies = white
            while pawns:
                pawn_bit = pawns & -pawns
                from_square = pawn_bit.bit_length() - 1
                pawns ^= pawn_bit
                file_ = from_square % self.board_width

                one_step = from_square - self.board_width
                one_step_empty = one_step >= 0 and not (occupied & (1 << one_step))
                if one_step_empty and from_square // self.board_width == 6:
                    two_step = from_square - 2 * self.board_width
                    if not (occupied & (1 << two_step)):
                        moves.append(self._encode_dense_move(from_square, two_step, FLAG_DOUBLE))

                if file_ > 0:
                    self._append_capture_or_ep(
                        moves,
                        from_square,
                        from_square - self.board_width - 1,
                        enemies,
                        ep_square,
                        False,
                    )

                if one_step_empty:
                    flags = FLAG_WINNING if one_step // self.board_width == 0 else 0
                    moves.append(self._encode_dense_move(from_square, one_step, flags))

                if file_ < self.board_width - 1:
                    self._append_capture_or_ep(
                        moves,
                        from_square,
                        from_square - self.board_width + 1,
                        enemies,
                        ep_square,
                        False,
                    )

        return moves

    def _append_capture_or_ep(
        self,
        moves: list[int],
        from_square: int,
        to_square: int,
        enemies: int,
        ep_square: int,
        white_to_move: bool,
    ) -> None:
        target_bit = 1 << to_square
        if enemies & target_bit:
            goal_rank = 7 if white_to_move else 0
            flags = FLAG_CAPTURE | (
                FLAG_WINNING if to_square // self.board_width == goal_rank else 0
            )
            moves.append(self._encode_dense_move(from_square, to_square, flags))
        elif to_square == ep_square:
            moves.append(
                self._encode_dense_move(
                    from_square,
                    to_square,
                    FLAG_CAPTURE | FLAG_EN_PASSANT,
                )
            )

    def _make_move_key(self, white: int, black: int, turn: int, move_code: int) -> int:
        from_square = self._standard_to_dense(_move_from(move_code))
        to_square = self._standard_to_dense(_move_to(move_code))
        flags = _move_flags(move_code)
        from_bit = 1 << from_square
        to_bit = 1 << to_square
        ep_square = NO_EP

        if turn == WHITE:
            white = (white & ~from_bit) | to_bit
            if flags & FLAG_EN_PASSANT:
                black &= ~(1 << (to_square - self.board_width))
            else:
                black &= ~to_bit
            if flags & FLAG_DOUBLE:
                ep_square = from_square + self.board_width
            return self._pack_key(white, black, BLACK, ep_square)

        black = (black & ~from_bit) | to_bit
        if flags & FLAG_EN_PASSANT:
            white &= ~(1 << (to_square + self.board_width))
        else:
            white &= ~to_bit
        if flags & FLAG_DOUBLE:
            ep_square = from_square - self.board_width
        return self._pack_key(white, black, WHITE, ep_square)

    def _encode_dense_move(self, from_square: int, to_square: int, flags: int) -> int:
        return (
            self._dense_to_standard(from_square)
            | (self._dense_to_standard(to_square) << 6)
            | (flags << 12)
        )

    def _dense_to_standard(self, square: int) -> int:
        return _dense_to_standard_square(square, self.board_width)

    def _standard_to_dense(self, square: int) -> int:
        return _standard_to_dense_square(square, self.board_width)

    def _store(self, key: int, result: int) -> int:
        self.memo[key] = result
        self.stats.states_solved += 1
        self._log_progress()
        self._maybe_checkpoint()
        return result

    def _maybe_checkpoint(self) -> None:
        if self.checkpoint_path is None or not self.checkpoint_interval:
            return
        if self.stats.states_solved - self._last_checkpoint_solved < self.checkpoint_interval:
            return
        self.save_checkpoint()

    def _log_progress(self) -> None:
        if (
            self.progress_interval
            and self.stats.states_entered
            and self.stats.states_entered % self.progress_interval == 0
            and self.stats.states_entered != self._last_progress_entered
        ):
            self._last_progress_entered = self.stats.states_entered
            elapsed = time.perf_counter() - self._started_at
            path = _path_to_text(self._path, self.progress_path_depth)
            print(
                f"entered={self.stats.states_entered} "
                f"solved={self.stats.states_solved} "
                f"cache_hits={self.stats.cache_hits} "
                f"max_depth={self.stats.max_depth} "
                f"path={path} "
                f"elapsed={elapsed:.2f}s",
                file=self.progress_stream,
                flush=True,
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
        ep_text = (
            "none"
            if ep_square == NO_EP
            else square_to_algebraic(self._dense_to_standard(ep_square))
        )
        pieces_text = (
            f"white={self._bitboard_to_text(white)} "
            f"black={self._bitboard_to_text(black)} ep={ep_text}"
        )
        print(
            f"tree depth={depth} path={_path_to_text(self._path)} "
            f"turn={'white' if turn == WHITE else 'black'} key={key:x} "
            f"{pieces_text}",
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

    def _bitboard_to_text(self, bitboard: int) -> str:
        squares: list[str] = []
        remaining = bitboard
        while remaining:
            square_bit = remaining & -remaining
            dense_square = square_bit.bit_length() - 1
            squares.append(square_to_algebraic(self._dense_to_standard(dense_square)))
            remaining ^= square_bit
        return ",".join(squares) or "-"


def _standard_to_dense_square(square: int, board_width: int) -> int:
    file_ = square & 7
    if file_ >= board_width:
        raise ValueError(f"square is outside board width {board_width}: {square}")
    return (square >> 3) * board_width + file_


def _dense_to_standard_square(square: int, board_width: int) -> int:
    return (square // board_width) * 8 + (square % board_width)


def _standard_bitboard_to_dense(bitboard: int, board_width: int) -> int:
    dense = 0
    remaining = bitboard
    while remaining:
        square_bit = remaining & -remaining
        square = square_bit.bit_length() - 1
        file_ = square & 7
        if file_ < board_width:
            dense |= 1 << _standard_to_dense_square(square, board_width)
        remaining ^= square_bit
    return dense


def _dense_bitboard_to_standard(bitboard: int, board_width: int) -> int:
    standard = 0
    remaining = bitboard
    while remaining:
        square_bit = remaining & -remaining
        square = square_bit.bit_length() - 1
        standard |= 1 << _dense_to_standard_square(square, board_width)
        remaining ^= square_bit
    return standard


def _move_from(move_code: int) -> int:
    return move_code & 0x3F


def _move_to(move_code: int) -> int:
    return (move_code >> 6) & 0x3F


def _move_flags(move_code: int) -> int:
    return (move_code >> 12) & 0xF


def _move_to_text(move_code: int) -> str:
    if move_code == NO_MOVE:
        return "none"
    return f"{square_to_algebraic(_move_from(move_code))}{square_to_algebraic(_move_to(move_code))}"


def _path_to_text(path: list[int], max_depth: int | None = None) -> str:
    if not path:
        return "(root)"
    shown = path if max_depth is None or max_depth == 0 else path[:max_depth]
    suffix = "" if len(shown) == len(path) else f" ...(+{len(path) - len(shown)})"
    return " ".join(_move_to_text(move) for move in shown) + suffix


def solve_initial(
    *,
    board_width: int,
    progress_interval: int = 0,
    max_entered_states: int | None = None,
    trace_depth: int = -1,
    log_moves: bool = False,
    progress_path_depth: int = 8,
    checkpoint_path: Path | None = None,
    checkpoint_interval: int = 0,
    resume: bool = False,
) -> tuple[Result, CompactSolver, float]:
    solver = CompactSolver(
        board_width=board_width,
        progress_interval=progress_interval,
        max_entered_states=max_entered_states,
        trace_depth=trace_depth,
        log_moves=log_moves,
        progress_path_depth=progress_path_depth,
        checkpoint_path=checkpoint_path,
        checkpoint_interval=checkpoint_interval,
        resume=resume,
    )
    started = time.perf_counter()
    result = solver.solve(initial_state(board_width))
    elapsed = time.perf_counter() - started
    return result, solver, elapsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Solve using compact width-specific keys.")
    parser.add_argument("--board-width", type=int, required=True)
    parser.add_argument("--progress", type=int, default=100_000)
    parser.add_argument("--max-entered", type=int, default=None)
    parser.add_argument("--trace-depth", type=int, default=-1)
    parser.add_argument("--log-moves", action="store_true")
    parser.add_argument("--progress-path-depth", type=int, default=8)
    parser.add_argument("--checkpoint", type=Path, default=None)
    parser.add_argument("--checkpoint-interval", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result, solver, elapsed = solve_initial(
            board_width=args.board_width,
            progress_interval=args.progress,
            max_entered_states=args.max_entered,
            trace_depth=args.trace_depth,
            log_moves=args.log_moves,
            progress_path_depth=args.progress_path_depth,
            checkpoint_path=args.checkpoint,
            checkpoint_interval=args.checkpoint_interval,
            resume=args.resume,
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
    print(f"initial best move: {_move_to_text(result.best_move)}")
    print(f"initial DTM: {result.dtm}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
