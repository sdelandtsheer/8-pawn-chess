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

Run a smaller board width. Supported widths are `2`, `4`, `6`, and `8`; width `2`
uses files `a` and `b`, width `4` uses `a` through `d`, and so on.

```powershell
py solve.py --board-width 2 --progress 10 --trace-depth 1 --log-moves
```

Trace output includes the current tree path, side to move, normalized key, pawn
locations, legal moves, and each move being considered within the selected depth.

Use the compact width-specific backend for width `6` and larger measurements:

```powershell
py compact_solve.py --board-width 6 --progress 1000000 --progress-path-depth 20
```

The compact backend stores only active files internally but still exports the
standard 8x8 tablebase keys. Progress includes a deeper current search path:

```text
entered=5000000 solved=4999977 cache_hits=4216934 max_depth=40 path=a2a3 a7a5 b2b3 a5a4 c2c3 a4b3 d2d3 b7b5 e2e3 b5b4 f2f3 c7c5 a3b4 c5c4 e3e4 d7d5 f3f4 d5d4 c3d4 f7f6 ...(+2) elapsed=61.74s
```

For bounded measurement runs while the full initial solve is still being optimized:

```powershell
py solve.py --board-width 8 --progress 10000 --max-entered 100000
```

Measure reachable state-space properties:

```powershell
py measure.py --max-states 10000
py measure.py --board-width 2 --max-states 1000 --solve --solve-max-entered 1000 --progress 500
```

## Tablebase Export Pipeline

Run the full local pipeline:

```powershell
py -m unittest discover -s tests
py -m ruff check .
py -m ruff format --check .
py export_tablebase.py --backend compact --board-width 8 --output-dir dist/w8 --skip-jsonl --binary --progress 1000000 --export-progress 1000000 --progress-path-depth 20 --checkpoint dist/w8/checkpoint.pkl --checkpoint-interval 5000000 --log-file dist/w8/export.log
```

The exporter solves the initial position exactly, then writes:

- `dist/w8/tablebase.bin`
- `dist/w8/tablebase.metadata.json`
- `dist/w8/checkpoint.pkl`
- `dist/w8/export.log`

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
py export_tablebase.py --backend compact --board-width 6 --output-dir dist/w6 --skip-jsonl --binary --progress 1000000 --max-entered 5000000 --progress-path-depth 20 --checkpoint dist/w6/checkpoint.pkl --checkpoint-interval 1000000 --log-file dist/w6/export.log
```

Bounded runs exit nonzero and intentionally do not write final tablebase
artifacts. With `--checkpoint`, they do write a resumable `checkpoint.pkl`.

Resume a compact run from the checkpoint:

```powershell
py export_tablebase.py --backend compact --board-width 6 --output-dir dist/w6 --skip-jsonl --binary --progress 1000000 --export-progress 1000000 --progress-path-depth 20 --checkpoint dist/w6/checkpoint.pkl --checkpoint-interval 5000000 --resume --log-file dist/w6/export.log
```

The binary tablebase format is fixed-width and uses standard 8x8 keys:

- 16-byte header: `PWTB`, version, board width, key bytes, record bytes, row count.
- Each row is 22 bytes: 17 little-endian key bytes, signed outcome byte, 16-bit DTM, 16-bit best move.

## Browser Width 4

Generate the paste-ready Wix HTML:

```powershell
py browser/build_wix_html.py
```

Verify browser keying and width 4 tablebase lookup:

```powershell
node tests/browser_core_smoke.js
node browser/verify_width4_tablebase.js
```

Paste-ready file:

```text
browser/wix_width4_tablebase.html
```
