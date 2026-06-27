"""Export exact strategy certificates for browser play.

A strategy certificate is smaller than a full tablebase. It covers every state
reachable when the human may choose any legal move and the engine follows one
certified exact reply at each engine turn.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TextIO

from compact_solve import CompactSolver
from rules import (
    BLACK,
    WHITE,
    Move,
    decode_move,
    initial_state,
    is_terminal,
    legal_moves,
    make_move,
    state_from_key,
    state_key,
    validate_board_width,
)
from solve import LOSS, NO_MOVE, WIN, Result, best_move_to_text

STRATEGY_MAGIC = b"PWST"
STRATEGY_VERSION = 1
STANDARD_KEY_BYTES = 17
STRATEGY_RECORD_BYTES = 23
NO_MOVE_BINARY = 0xFFFF
FLAG_ENGINE_TURN = 1
FLAG_TERMINAL = 2


@dataclass(frozen=True, slots=True)
class StrategyEntry:
    key: int
    outcome: int
    dtm: int
    best_move: int
    engine_turn: bool
    terminal: bool


@dataclass(frozen=True, slots=True)
class StrategyMetadata:
    board_width: int
    engine_side: str
    entries: int
    engine_turn_entries: int
    human_turn_entries: int
    terminal_entries: int
    outcome: int
    dtm: int
    best_move: int
    best_move_coord: str
    elapsed_seconds: float
    solver_states: int
    solver_cache_hits: int
    binary_path: str
    jsonl_path: str | None
    verification: dict[str, int]


class Tee:
    def __init__(self, *streams: TextIO) -> None:
        self.streams = streams

    def write(self, text: str) -> int:
        for stream in self.streams:
            stream.write(text)
        return len(text)

    def flush(self) -> None:
        for stream in self.streams:
            stream.flush()


class StrategyBuilder:
    def __init__(
        self,
        *,
        board_width: int,
        engine_side: int,
        use_symmetry: bool = True,
        progress_interval: int = 0,
        max_entered_states: int | None = None,
        trace_depth: int = -1,
        log_moves: bool = False,
        progress_path_depth: int = 8,
        progress_stream=sys.stderr,
    ) -> None:
        validate_board_width(board_width)
        self.board_width = board_width
        self.engine_side = engine_side
        self.solver = CompactSolver(
            board_width=board_width,
            use_symmetry=use_symmetry,
            prune=True,
            progress_interval=progress_interval,
            max_entered_states=max_entered_states,
            trace_depth=trace_depth,
            log_moves=log_moves,
            progress_path_depth=progress_path_depth,
            progress_stream=progress_stream,
        )
        self.entries: dict[int, StrategyEntry] = {}
        self.progress_interval = progress_interval
        self.progress_stream = progress_stream
        self.started_at = time.perf_counter()

    def build(self) -> Result:
        root = initial_state(self.board_width)
        result = self._build_state(root)
        return result

    def _build_state(self, state) -> Result:
        key = state_key(state, self.board_width)
        existing = self.entries.get(key)
        if existing is not None:
            return Result(existing.outcome, existing.dtm, existing.best_move)

        result = self.solver.solve(state)
        moves = legal_moves(state, self.board_width)
        terminal = is_terminal(state) or not moves
        engine_turn = state.turn == self.engine_side
        best_move = result.best_move if engine_turn and not terminal else NO_MOVE

        self.entries[key] = StrategyEntry(
            key=key,
            outcome=result.outcome,
            dtm=result.dtm,
            best_move=best_move,
            engine_turn=engine_turn,
            terminal=terminal,
        )
        self._log_progress()

        if terminal:
            return result

        if engine_turn:
            move = _decode_required_legal_move(best_move, moves)
            self._build_state(make_move(state, move, validate=False, board_width=self.board_width))
            return result

        for move in moves:
            self._build_state(make_move(state, move, validate=False, board_width=self.board_width))
        return result

    def _log_progress(self) -> None:
        if not self.progress_interval:
            return
        count = len(self.entries)
        if count % self.progress_interval != 0:
            return
        elapsed = time.perf_counter() - self.started_at
        print(
            f"strategy_entries={count} solver_states={self.solver.stats.states_solved} "
            f"cache_hits={self.solver.stats.cache_hits} elapsed={elapsed:.2f}s",
            file=self.progress_stream,
            flush=True,
        )


def verify_strategy(
    entries: dict[int, StrategyEntry],
    *,
    board_width: int,
    engine_side: int,
) -> dict[str, int]:
    checked_edges = 0
    engine_edges = 0
    human_edges = 0

    for key, entry in entries.items():
        state = state_from_key(key, board_width)
        moves = legal_moves(state, board_width)
        terminal = is_terminal(state) or not moves
        if terminal != entry.terminal:
            raise ValueError(f"terminal mismatch for key {key:x}")
        if (state.turn == engine_side) != entry.engine_turn:
            raise ValueError(f"engine-turn mismatch for key {key:x}")
        if terminal:
            if entry.best_move != NO_MOVE:
                raise ValueError(f"terminal entry has a best move for key {key:x}")
            continue

        if entry.engine_turn:
            move = _decode_required_legal_move(entry.best_move, moves)
            child = make_move(state, move, validate=False, board_width=board_width)
            child_entry = entries.get(state_key(child, board_width))
            if child_entry is None:
                raise ValueError(f"missing engine child after {key:x}")
            _verify_dtm_edge(entry, child_entry, key)
            checked_edges += 1
            engine_edges += 1
        else:
            if entry.best_move != NO_MOVE:
                raise ValueError(f"human-turn entry has an engine move for key {key:x}")
            for move in moves:
                child = make_move(state, move, validate=False, board_width=board_width)
                if state_key(child, board_width) not in entries:
                    raise ValueError(f"missing human reply child after {key:x}")
                checked_edges += 1
                human_edges += 1

    return {
        "checked_entries": len(entries),
        "checked_edges": checked_edges,
        "engine_edges": engine_edges,
        "human_edges": human_edges,
    }


def write_strategy_binary(
    entries: dict[int, StrategyEntry],
    path: Path,
    *,
    board_width: int,
    engine_side: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        with temp_path.open("wb") as file:
            file.write(
                struct.pack(
                    "<4sBBBBQ",
                    STRATEGY_MAGIC,
                    STRATEGY_VERSION,
                    board_width,
                    engine_side,
                    STRATEGY_RECORD_BYTES,
                    len(entries),
                )
            )
            for key, entry in sorted(entries.items()):
                flags = 0
                if entry.engine_turn:
                    flags |= FLAG_ENGINE_TURN
                if entry.terminal:
                    flags |= FLAG_TERMINAL
                best_move = NO_MOVE_BINARY if entry.best_move == NO_MOVE else entry.best_move
                file.write(key.to_bytes(STANDARD_KEY_BYTES, "little"))
                file.write(struct.pack("<bHHB", entry.outcome, entry.dtm, best_move, flags))
        temp_path.replace(path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def write_strategy_jsonl(entries: dict[int, StrategyEntry], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as file:
            for key, entry in sorted(entries.items()):
                file.write(
                    json.dumps(
                        {
                            "key": f"{key:x}",
                            "outcome": entry.outcome,
                            "dtm": entry.dtm,
                            "best_move": entry.best_move,
                            "engine_turn": entry.engine_turn,
                            "terminal": entry.terminal,
                        },
                        separators=(",", ":"),
                    )
                    + "\n"
                )
        temp_path.replace(path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def export_strategy(
    *,
    board_width: int,
    engine_side: int,
    output_dir: Path,
    use_symmetry: bool = True,
    write_jsonl: bool = False,
    progress_interval: int = 0,
    max_entered_states: int | None = None,
    trace_depth: int = -1,
    log_moves: bool = False,
    progress_path_depth: int = 8,
    progress_stream=sys.stderr,
) -> StrategyMetadata:
    side_name = _side_name(engine_side)
    builder = StrategyBuilder(
        board_width=board_width,
        engine_side=engine_side,
        use_symmetry=use_symmetry,
        progress_interval=progress_interval,
        max_entered_states=max_entered_states,
        trace_depth=trace_depth,
        log_moves=log_moves,
        progress_path_depth=progress_path_depth,
        progress_stream=progress_stream,
    )
    started = time.perf_counter()
    root_result = builder.build()
    root_entry = builder.entries[state_key(initial_state(board_width), board_width)]
    elapsed = time.perf_counter() - started
    verification = verify_strategy(
        builder.entries,
        board_width=board_width,
        engine_side=engine_side,
    )

    binary_path = output_dir / f"strategy_{side_name}.bin"
    write_strategy_binary(
        builder.entries,
        binary_path,
        board_width=board_width,
        engine_side=engine_side,
    )

    jsonl_path = None
    if write_jsonl:
        jsonl_path = output_dir / f"strategy_{side_name}.jsonl"
        write_strategy_jsonl(builder.entries, jsonl_path)

    metadata = StrategyMetadata(
        board_width=board_width,
        engine_side=side_name,
        entries=len(builder.entries),
        engine_turn_entries=sum(1 for entry in builder.entries.values() if entry.engine_turn),
        human_turn_entries=sum(
            1 for entry in builder.entries.values() if not entry.engine_turn and not entry.terminal
        ),
        terminal_entries=sum(1 for entry in builder.entries.values() if entry.terminal),
        outcome=root_result.outcome,
        dtm=root_result.dtm,
        best_move=root_entry.best_move,
        best_move_coord=best_move_to_text(
            Result(root_entry.outcome, root_entry.dtm, root_entry.best_move)
        ),
        elapsed_seconds=elapsed,
        solver_states=builder.solver.stats.states_solved,
        solver_cache_hits=builder.solver.stats.cache_hits,
        binary_path=str(binary_path),
        jsonl_path=None if jsonl_path is None else str(jsonl_path),
        verification=verification,
    )
    write_metadata(metadata, output_dir / f"strategy_{side_name}.metadata.json")
    return metadata


def write_metadata(metadata: StrategyMetadata, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(metadata), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _decode_required_legal_move(move_code: int, moves: tuple[Move, ...]) -> Move:
    if move_code == NO_MOVE:
        raise ValueError("expected a legal best move, got none")
    move = decode_move(move_code)
    if move not in moves:
        raise ValueError(f"strategy move is not legal: {move}")
    return move


def _verify_dtm_edge(parent: StrategyEntry, child: StrategyEntry, key: int) -> None:
    if parent.outcome == WIN:
        if child.outcome != LOSS or child.dtm != parent.dtm - 1:
            raise ValueError(f"winning DTM edge failed for key {key:x}")
    elif parent.outcome == LOSS:
        if child.outcome != WIN or child.dtm != parent.dtm - 1:
            raise ValueError(f"losing DTM edge failed for key {key:x}")
    else:
        raise ValueError(f"invalid outcome for key {key:x}: {parent.outcome}")


def _side_name(side: int) -> str:
    if side == WHITE:
        return "white"
    if side == BLACK:
        return "black"
    raise ValueError(f"invalid side: {side}")


def _parse_side(name: str) -> int:
    if name == "white":
        return WHITE
    if name == "black":
        return BLACK
    raise ValueError(f"invalid side: {name}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export exact strategy certificates.")
    parser.add_argument("--board-width", type=int, required=True)
    parser.add_argument("--engine-side", choices=("white", "black", "both"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--no-symmetry", action="store_true")
    parser.add_argument("--jsonl", action="store_true")
    parser.add_argument("--progress", type=int, default=10_000)
    parser.add_argument(
        "--max-entered",
        type=int,
        default=None,
        help="stop after entering this many uncached solver states",
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
    parser.add_argument(
        "--progress-path-depth",
        type=int,
        default=8,
        help="include this many current-path plies in solver progress output",
    )
    parser.add_argument("--log-file", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    log_file = None
    progress_stream = sys.stderr
    if args.log_file is not None:
        args.log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file = args.log_file.open("w", encoding="utf-8")
        progress_stream = Tee(sys.stderr, log_file)

    try:
        sides = (WHITE, BLACK) if args.engine_side == "both" else (_parse_side(args.engine_side),)
        metadatas = []
        for side in sides:
            metadata = export_strategy(
                board_width=args.board_width,
                engine_side=side,
                output_dir=args.output_dir,
                use_symmetry=not args.no_symmetry,
                write_jsonl=args.jsonl,
                progress_interval=args.progress,
                max_entered_states=args.max_entered,
                trace_depth=args.trace_depth,
                log_moves=args.log_moves,
                progress_path_depth=args.progress_path_depth,
                progress_stream=progress_stream,
            )
            metadatas.append(asdict(metadata))
            print(json.dumps(asdict(metadata), indent=2, sort_keys=True))
        if len(metadatas) > 1:
            (args.output_dir / "strategy.metadata.json").write_text(
                json.dumps(metadatas, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        return 0
    finally:
        if log_file is not None:
            log_file.close()


if __name__ == "__main__":
    raise SystemExit(main())
