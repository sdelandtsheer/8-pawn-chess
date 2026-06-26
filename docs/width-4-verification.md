# Width 4 Verification

Command:

```powershell
py export_tablebase.py --board-width 4 --output-dir dist/w4 --gzip --progress 10000 --export-progress 10000 --trace-depth 1 --log-moves --log-file dist/w4/export.log
```

Result:

```json
{
  "best_move": 9801,
  "best_move_coord": "b2b4",
  "board_width": 4,
  "complete": true,
  "dtm": 21,
  "gzip_path": "dist\\w4\\tablebase.jsonl.gz",
  "jsonl_path": "dist\\w4\\tablebase.jsonl",
  "loss_states": 389938,
  "outcome": 1,
  "states": 1033490,
  "win_states": 643552
}
```

Interpretation:

- The width 4 initial position is a forced win for White.
- Deterministic best move under the shortest-win convention is `b2b4`.
- The win distance is `21` plies.
- The exported debug table has `1,033,490` JSONL rows.
- The local JSONL file was `81,605,663` bytes.
- The gzip-compressed JSONL file was `6,372,278` bytes.

The root legal moves are:

```text
a2a3,a2a4,b2b3,b2b4,c2c3,c2c4,d2d3,d2d4
```

The `c`-file and `d`-file moves mirror the `b`-file and `a`-file moves respectively.
