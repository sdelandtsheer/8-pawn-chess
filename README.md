# 8-Pawn Chess Tablebase

Exact solver and browser tablebase tooling for an 8x8 pawn-only chess variant.

## Rules

- White starts with pawns on `a2` through `h2`; Black starts with pawns on `a7` through `h7`.
- White moves first.
- Pawns move as in chess: one step, initial two-step if clear, diagonal capture, and en passant.
- There are no kings, checks, castling, or promotion.
- A pawn reaching the opposite back rank wins immediately.
- If the side to move has no legal move, that side loses.

## State Encoding

Squares use `0 = a1`, `1 = b1`, ..., `63 = h8`.

A state is:

- `white`: 64-bit bitboard
- `black`: 64-bit bitboard
- `turn`: `0` for White, `1` for Black
- `ep_square`: `-1` or `0..63`

Normalized tablebase keys are packed as:

```text
white | (black << 64) | (turn << 128) | (ep_code << 129)
```

where `ep_code` is `0` for no en passant square, otherwise `square + 1`.

## Development

Run the current verification suite:

```powershell
py -m unittest discover -s tests
```

Run the slow tactical solver regressions explicitly:

```powershell
$env:RUN_SLOW_SOLVER_TESTS = "1"
py -m unittest tests.test_validation
```

Run linting and formatting checks when `ruff` is installed:

```powershell
py -m ruff check .
py -m ruff format --check .
```

Run the recursive solver:

```powershell
py solve.py --progress 100000
```

For bounded measurement runs while the full initial solve is still being optimized:

```powershell
py solve.py --progress 10000 --max-entered 100000
```

Measure reachable state-space properties:

```powershell
py measure.py --max-states 10000
py measure.py --max-states 1000 --solve --solve-max-entered 1000 --progress 500
```

## Tablebase Export Pipeline

Run the full local pipeline:

```powershell
py -m unittest discover -s tests
py -m ruff check .
py -m ruff format --check .
py export_tablebase.py --output-dir dist --gzip --progress 1000000 --export-progress 1000000 --log-file dist/export.log
```

The exporter solves the initial position exactly, then writes:

- `dist/tablebase.jsonl`
- `dist/tablebase.jsonl.gz`
- `dist/tablebase.metadata.json`
- `dist/export.log`

Console progress is printed during solving as:

```text
entered=1000000 solved=999959 cache_hits=646671 max_depth=47 elapsed=11.53s
```

Export progress is printed as:

```text
exported=1000000
```

Use a bounded dry run to verify logging without producing a partial table:

```powershell
py export_tablebase.py --output-dir dist --progress 1000 --max-entered 3000 --log-file dist/export.log --gzip
```

Bounded runs exit nonzero and intentionally do not write tablebase artifacts.
