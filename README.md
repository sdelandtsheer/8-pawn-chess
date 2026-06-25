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

Run the recursive solver prototype:

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
