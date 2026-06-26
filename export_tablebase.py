"""Solve and export the 8-pawn chess tablebase."""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TextIO

from rules import initial_state, state_key, validate_board_width
from solve import LOSS, WIN, SolveLimitReachedError, Solver, _unpack_result, best_move_to_text


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
    jsonl_path: str
    gzip_path: str | None


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
    use_symmetry: bool = False,
    trace_depth: int = -1,
    log_moves: bool = False,
    progress_stream=sys.stderr,
) -> tuple[Solver, float, bool]:
    validate_board_width(board_width)
    solver = Solver(
        progress_interval=progress_interval,
        max_entered_states=max_entered_states,
        board_width=board_width,
        use_symmetry=use_symmetry,
        trace_depth=trace_depth,
        log_moves=log_moves,
        progress_stream=progress_stream,
    )
    started = time.perf_counter()
    complete = True
    try:
        solver.solve(initial_state(board_width))
    except SolveLimitReachedError as exc:
        complete = False
        print(str(exc), file=progress_stream)
    elapsed = time.perf_counter() - started
    return solver, elapsed, complete


def write_jsonl(
    solver: Solver,
    path: Path,
    *,
    export_progress_interval: int,
    progress_stream=sys.stderr,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as file:
            for index, (key, packed_result) in enumerate(solver.memo.items(), start=1):
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


def build_metadata(
    solver: Solver,
    *,
    complete: bool,
    elapsed_seconds: float,
    jsonl_path: Path,
    gzip_path: Path | None,
    board_width: int = 8,
) -> ExportMetadata:
    initial_packed_result = (
        solver.memo.get(state_key(initial_state(board_width), board_width)) if complete else None
    )
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
        jsonl_path=str(jsonl_path),
        gzip_path=None if gzip_path is None else str(gzip_path),
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
    parser.add_argument("--metadata-name", default="tablebase.metadata.json")
    parser.add_argument("--gzip", action="store_true", help="also write tablebase.jsonl.gz")
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
            use_symmetry=args.symmetry,
            trace_depth=args.trace_depth,
            log_moves=args.log_moves,
            progress_stream=progress_stream,
        )
        if not complete:
            return 2

        jsonl_path = args.output_dir / args.jsonl_name
        gzip_path = jsonl_path.with_suffix(jsonl_path.suffix + ".gz") if args.gzip else None

        write_jsonl(
            solver,
            jsonl_path,
            export_progress_interval=args.export_progress,
            progress_stream=progress_stream,
        )
        if gzip_path is not None:
            print(f"gzip={gzip_path}", file=progress_stream, flush=True)
            gzip_file(jsonl_path, gzip_path)

        metadata = build_metadata(
            solver,
            complete=complete,
            elapsed_seconds=elapsed,
            jsonl_path=jsonl_path,
            gzip_path=gzip_path,
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
