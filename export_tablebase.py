"""Solve and export the 8-pawn chess tablebase."""

from __future__ import annotations

import argparse
import gzip
import json
import struct
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TextIO

from compact_solve import CompactSolver
from rules import initial_state, state_key, validate_board_width
from solve import (
    LOSS,
    NO_MOVE,
    WIN,
    SolveLimitReachedError,
    Solver,
    _unpack_result,
    best_move_to_text,
)

BINARY_MAGIC = b"PWTB"
BINARY_VERSION = 1
STANDARD_KEY_BYTES = 17
NO_MOVE_BINARY = 0xFFFF


@dataclass(frozen=True, slots=True)
class ExportMetadata:
    complete: bool
    board_width: int
    states: int
    elapsed_seconds: float
    outcome: int | None
    dtm: int | None
    best_move: int | None
    best_move_coord: str | None
    win_states: int
    loss_states: int
    jsonl_path: str | None
    gzip_path: str | None
    binary_path: str | None


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


def solve_tablebase(
    *,
    progress_interval: int,
    max_entered_states: int | None = None,
    board_width: int = 8,
    backend: str = "classic",
    use_symmetry: bool = False,
    trace_depth: int = -1,
    log_moves: bool = False,
    progress_path_depth: int = 8,
    checkpoint_path: Path | None = None,
    checkpoint_interval: int = 0,
    resume: bool = False,
    progress_stream=sys.stderr,
) -> tuple[Solver | CompactSolver, float, bool]:
    validate_board_width(board_width)
    if backend == "compact":
        if use_symmetry:
            raise ValueError("--symmetry is only supported by --backend classic")
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
            progress_stream=progress_stream,
        )
    elif resume or checkpoint_path is not None or checkpoint_interval:
        raise ValueError("checkpointing is only supported by --backend compact")
    elif backend == "classic":
        solver = Solver(
            progress_interval=progress_interval,
            max_entered_states=max_entered_states,
            board_width=board_width,
            use_symmetry=use_symmetry,
            trace_depth=trace_depth,
            log_moves=log_moves,
            progress_stream=progress_stream,
        )
    else:
        raise ValueError(f"unknown backend: {backend}")
    started = time.perf_counter()
    complete = True
    try:
        solver.solve(initial_state(board_width))
    except SolveLimitReachedError as exc:
        complete = False
        print(str(exc), file=progress_stream)
        if isinstance(solver, CompactSolver) and checkpoint_path is not None:
            solver.save_checkpoint(checkpoint_path)
    except KeyboardInterrupt:
        if isinstance(solver, CompactSolver) and checkpoint_path is not None:
            solver.save_checkpoint(checkpoint_path)
        raise
    elapsed = time.perf_counter() - started
    return solver, elapsed, complete


def write_jsonl(
    solver: Solver | CompactSolver,
    path: Path,
    *,
    export_progress_interval: int,
    progress_stream=sys.stderr,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as file:
            entries = (
                solver.iter_standard_entries()
                if isinstance(solver, CompactSolver)
                else solver.memo.items()
            )
            for index, (key, packed_result) in enumerate(entries, start=1):
                result = _unpack_result(packed_result)
                file.write(
                    json.dumps(
                        {
                            "key": f"{key:x}",
                            "outcome": result.outcome,
                            "dtm": result.dtm,
                            "best_move": result.best_move,
                        },
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                if export_progress_interval and index % export_progress_interval == 0:
                    print(f"exported={index}", file=progress_stream, flush=True)
        temp_path.replace(path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def gzip_file(source: Path, target: Path) -> None:
    temp_path = target.with_suffix(target.suffix + ".tmp")
    try:
        with (
            source.open("rb") as input_file,
            gzip.open(temp_path, "wb", compresslevel=9) as output_file,
        ):
            while chunk := input_file.read(1024 * 1024):
                output_file.write(chunk)
        temp_path.replace(target)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def _iter_standard_entries(solver: Solver | CompactSolver):
    if isinstance(solver, CompactSolver):
        yield from solver.iter_standard_entries()
    else:
        yield from solver.memo.items()


def write_binary(
    solver: Solver | CompactSolver,
    path: Path,
    *,
    board_width: int,
    export_progress_interval: int,
    progress_stream=sys.stderr,
) -> None:
    """Write a fixed-record binary tablebase using standard 8x8 keys.

    Header:
    - 4 bytes: PWTB
    - 1 byte: version
    - 1 byte: board width
    - 1 byte: key bytes, currently 17
    - 1 byte: record bytes
    - 8 bytes: row count, little endian

    Each row:
    - 17 bytes: standard tablebase key, little endian
    - 1 byte: signed outcome
    - 2 bytes: DTM, little endian
    - 2 bytes: best move, little endian, 0xffff for none
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    record_bytes = STANDARD_KEY_BYTES + 5
    try:
        with temp_path.open("wb") as file:
            file.write(
                BINARY_MAGIC
                + bytes([BINARY_VERSION, board_width, STANDARD_KEY_BYTES, record_bytes])
                + struct.pack("<Q", len(solver.memo))
            )
            for index, (key, packed_result) in enumerate(_iter_standard_entries(solver), start=1):
                result = _unpack_result(packed_result)
                best_move = NO_MOVE_BINARY if result.best_move == NO_MOVE else result.best_move
                file.write(key.to_bytes(STANDARD_KEY_BYTES, "little"))
                file.write(struct.pack("<bHH", result.outcome, result.dtm, best_move))
                if export_progress_interval and index % export_progress_interval == 0:
                    print(f"binary_exported={index}", file=progress_stream, flush=True)
        temp_path.replace(path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def build_metadata(
    solver: Solver | CompactSolver,
    *,
    complete: bool,
    elapsed_seconds: float,
    jsonl_path: Path | None,
    gzip_path: Path | None,
    binary_path: Path | None = None,
    board_width: int = 8,
) -> ExportMetadata:
    if isinstance(solver, CompactSolver):
        initial_result = solver.initial_result() if complete else None
    else:
        initial_key = state_key(initial_state(board_width), board_width)
        initial_packed_result = solver.memo.get(initial_key) if complete else None
        initial_result = (
            None if initial_packed_result is None else _unpack_result(initial_packed_result)
        )
    unpacked_results = (_unpack_result(result) for result in solver.memo.values())
    win_states = 0
    loss_states = 0
    for result in unpacked_results:
        if result.outcome == WIN:
            win_states += 1
        elif result.outcome == LOSS:
            loss_states += 1

    return ExportMetadata(
        complete=complete,
        board_width=board_width,
        states=len(solver.memo),
        elapsed_seconds=elapsed_seconds,
        outcome=None if initial_result is None else initial_result.outcome,
        dtm=None if initial_result is None else initial_result.dtm,
        best_move=None if initial_result is None else initial_result.best_move,
        best_move_coord=None if initial_result is None else best_move_to_text(initial_result),
        win_states=win_states,
        loss_states=loss_states,
        jsonl_path=None if jsonl_path is None else str(jsonl_path),
        gzip_path=None if gzip_path is None else str(gzip_path),
        binary_path=None if binary_path is None else str(binary_path),
    )


def write_metadata(metadata: ExportMetadata, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        temp_path.write_text(
            json.dumps(asdict(metadata), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Solve and export the 8-pawn chess tablebase.")
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    parser.add_argument("--jsonl-name", default="tablebase.jsonl")
    parser.add_argument("--skip-jsonl", action="store_true", help="do not write debug JSONL")
    parser.add_argument("--metadata-name", default="tablebase.metadata.json")
    parser.add_argument("--gzip", action="store_true", help="also write tablebase.jsonl.gz")
    parser.add_argument("--binary", action="store_true", help="write compact binary tablebase")
    parser.add_argument("--binary-name", default="tablebase.bin")
    parser.add_argument(
        "--board-width",
        type=int,
        default=8,
        help="active board width: 2, 4, 6, or 8 files starting at a-file",
    )
    parser.add_argument(
        "--backend",
        choices=("classic", "compact"),
        default="classic",
        help="solver backend; compact uses dense width-specific keys internally",
    )
    parser.add_argument(
        "--progress",
        type=int,
        default=100_000,
        help="print solve progress every N entered uncached states",
    )
    parser.add_argument(
        "--export-progress",
        type=int,
        default=100_000,
        help="print export progress every N written table rows",
    )
    parser.add_argument(
        "--max-entered",
        type=int,
        default=None,
        help="stop after entering this many uncached states; does not export partial tables",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="also write progress logs to this file",
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
    parser.add_argument(
        "--progress-path-depth",
        type=int,
        default=8,
        help="with --backend compact, include this many current-path plies in progress output",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="compact backend checkpoint path",
    )
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=0,
        help="save compact backend checkpoint every N solved states",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="resume compact backend from --checkpoint",
    )
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
        solver, elapsed, complete = solve_tablebase(
            progress_interval=args.progress,
            max_entered_states=args.max_entered,
            board_width=args.board_width,
            backend=args.backend,
            use_symmetry=args.symmetry,
            trace_depth=args.trace_depth,
            log_moves=args.log_moves,
            progress_path_depth=args.progress_path_depth,
            checkpoint_path=args.checkpoint,
            checkpoint_interval=args.checkpoint_interval,
            resume=args.resume,
            progress_stream=progress_stream,
        )
        if not complete:
            return 2

        jsonl_path = None if args.skip_jsonl else args.output_dir / args.jsonl_name
        gzip_path = (
            jsonl_path.with_suffix(jsonl_path.suffix + ".gz")
            if args.gzip and jsonl_path is not None
            else None
        )
        binary_path = args.output_dir / args.binary_name if args.binary else None

        if jsonl_path is not None:
            write_jsonl(
                solver,
                jsonl_path,
                export_progress_interval=args.export_progress,
                progress_stream=progress_stream,
            )
        if gzip_path is not None:
            print(f"gzip={gzip_path}", file=progress_stream, flush=True)
            gzip_file(jsonl_path, gzip_path)
        if binary_path is not None:
            print(f"binary={binary_path}", file=progress_stream, flush=True)
            write_binary(
                solver,
                binary_path,
                board_width=args.board_width,
                export_progress_interval=args.export_progress,
                progress_stream=progress_stream,
            )

        metadata = build_metadata(
            solver,
            complete=complete,
            elapsed_seconds=elapsed,
            jsonl_path=jsonl_path,
            gzip_path=gzip_path,
            binary_path=binary_path,
            board_width=args.board_width,
        )
        metadata_path = args.output_dir / args.metadata_name
        write_metadata(metadata, metadata_path)
        print(json.dumps(asdict(metadata), indent=2, sort_keys=True))
        return 0
    finally:
        if log_file is not None:
            log_file.close()


if __name__ == "__main__":
    raise SystemExit(main())
