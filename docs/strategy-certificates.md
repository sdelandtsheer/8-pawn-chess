# Strategy Certificates

A strategy certificate is an exact play book for one engine side. It is not a
full tablebase.

It covers:

- every legal human reply from every reachable human-turn state;
- exactly one certified engine reply from every reachable engine-turn state;
- terminal states reached by either side.

This is enough for browser play because the browser only needs to avoid misses
along games where the engine follows the certified strategy.

## Width 4 Check

Command:

```powershell
py export_strategy.py --board-width 4 --engine-side both --output-dir dist/w4-strategy --progress 10000 --log-file dist/w4-strategy/export.log
```

For width 6 and larger, the exporter can also expose compact-solver progress:

```powershell
py export_strategy.py --board-width 6 --engine-side both --output-dir dist/w6-strategy --progress 100000 --progress-path-depth 20 --log-file dist/w6-strategy/export.log
```

Useful diagnostic flags:

- `--max-entered`: stop after a bounded number of uncached solver states.
- `--trace-depth`: print tree states and legal moves down to a shallow depth.
- `--log-moves`: include the move being considered inside the traced depth.
- `--progress-path-depth`: include this many plies in periodic progress lines.

Result:

```text
engine white entries: 10524
engine white binary: 242068 bytes
engine white root move: b2b4
engine black entries: 10995
engine black binary: 252901 bytes
```

For comparison, the corrected full width 4 tablebase binary is `22,736,796`
bytes.

## Verification

The exporter verifies:

- every stored engine move is legal;
- every human-turn node includes all legal human replies;
- every engine-turn edge satisfies DTM consistency:
  - `WIN -> LOSS` with child DTM `parent_dtm - 1`;
  - `LOSS -> WIN` with child DTM `parent_dtm - 1`;
- every referenced child is present.

Width 4 verification counts:

```text
engine white checked entries: 10524
engine white checked edges: 12961
engine black checked entries: 10995
engine black checked edges: 13609
```

## Browser Integration

Build the self-contained Wix page from the generated width 4 strategy binaries:

```powershell
py browser/build_wix_strategy_html.py
```

The output is:

```text
browser/wix_width4_strategy.html
```

If `dist/w4-strategy/strategy_white.bin` and `strategy_black.bin` exist, the
builder embeds both certificates as base64 constants, so the HTML can be pasted
into Wix without hosting a separate tablebase file.

Smoke tests:

```powershell
node tests/strategy_html_smoke.js
node browser/verify_width4_strategy.js
```

## Binary Format

Header:

- `4s`: magic `PWST`
- `u8`: version
- `u8`: board width
- `u8`: engine side, `0` white or `1` black
- `u8`: record bytes, currently `23`
- `u64le`: row count

Each record:

- `17 bytes`: standard 8x8 tablebase key, little endian
- `i8`: outcome
- `u16le`: DTM
- `u16le`: best move, `0xffff` for none
- `u8`: flags

Flags:

- bit `0`: engine-turn node
- bit `1`: terminal node
