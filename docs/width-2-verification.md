# Width 2 Verification

Command:

```powershell
py export_tablebase.py --board-width 2 --output-dir dist/w2 --gzip --progress 50 --export-progress 100 --trace-depth 1 --log-moves --log-file dist/w2/export.log
```

Result:

```json
{
  "best_move": 1032,
  "best_move_coord": "a2a3",
  "board_width": 2,
  "complete": true,
  "dtm": 8,
  "gzip_path": "dist\\w2\\tablebase.jsonl.gz",
  "jsonl_path": "dist\\w2\\tablebase.jsonl",
  "loss_states": 220,
  "outcome": -1,
  "states": 515,
  "win_states": 295
}
```

Interpretation:

- The width 2 initial position is a forced loss for White.
- Deterministic best move under the loss-delay convention is `a2a3`.
- The loss distance is `8` plies.
- The exported debug table has `515` JSONL rows.
- The gzip-compressed JSONL file was `3134` bytes in the local run.

The root legal moves are:

```text
a2a3,a2a4,b2b3,b2b4
```

The `b`-file moves are mirror-equivalent to the `a`-file moves.
