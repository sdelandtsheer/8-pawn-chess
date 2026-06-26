# Width 6 Attempt

## Classic Backend Attempt

Command:

```powershell
py export_tablebase.py --board-width 6 --output-dir dist/w6 --gzip --progress 1000000 --export-progress 1000000 --trace-depth 1 --log-moves --log-file dist/w6/export.log
```

Result:

- Did not complete within the one-hour command timeout.
- The process was still running after the command timeout and was stopped manually to avoid OOM.
- Last recorded direct-DFS progress:

```text
entered=142000000 solved=141999981 cache_hits=212186029 max_depth=44 elapsed=3616.61s
```

Resource usage before stopping:

```text
WorkingSet64:        8,605,245,440 bytes
PrivateMemorySize64: 16,848,633,856 bytes
VirtualMemorySize64: 21,174,640,640 bytes
```

Tree progress:

```text
tree depth=0 considering=a2a3 path=a2a3
```

The run was still inside the first root move after `142M` entered states.

Symmetry/canonicalized bounded run:

```powershell
py solve.py --board-width 6 --symmetry --progress 1000000 --max-entered 20000000
```

Result:

```text
entered=20000000 solved=19999976 cache_hits=23763970 max_depth=42 elapsed=561.69s
stopped after entering 20000001 uncached states
```

Classic conclusion:

- Width 6 is too large for the original sparse Python dict-backed DFS/exporter.
- A compact width-specific backend is required before a practical width 6 export.

## Compact Backend Measurement

Command:

```powershell
py compact_solve.py --board-width 6 --progress 5000000 --max-entered 20000000 --progress-path-depth 20
```

Result:

```text
entered=5000000 solved=4999977 cache_hits=4216934 max_depth=40 path=a2a3 a7a5 b2b3 a5a4 c2c3 a4b3 d2d3 b7b5 e2e3 b5b4 f2f3 c7c5 a3b4 c5c4 e3e4 d7d5 f3f4 d5d4 c3d4 f7f6 ...(+2) elapsed=61.74s
entered=10000000 solved=9999977 cache_hits=9981238 max_depth=41 path=a2a3 a7a5 b2b3 a5a4 c2c3 a4b3 d2d3 b7b5 e2e3 b5b4 f2f3 d7d5 c3b4 e7e5 e3e4 f7f5 f3f4 e5f4 b4b5 f4f3 ...(+2) elapsed=133.55s
entered=15000000 solved=14999975 cache_hits=16785436 max_depth=42 path=a2a3 a7a5 b2b3 a5a4 c2c3 a4b3 d2d3 b7b5 e2e3 b5b4 c3c4 b4a3 d3d4 c7c5 e3e4 d7d5 c4d5 c5c4 e4e5 e7e6 ...(+4) elapsed=215.41s
entered=20000000 solved=19999972 cache_hits=23443375 max_depth=42 path=a2a3 a7a5 b2b3 a5a4 c2c3 a4b3 d2d3 b7b5 e2e3 c7c6 f2f4 c6c5 a3a4 e7e6 d3d4 c5d4 c3d4 e6e5 a4a5 e5f4 ...(+7) elapsed=297.31s
stopped after entering 20000001 uncached states
```

Correctness checks:

- Width 2 compact and classic memo sets match exactly: `515` states, no missing or extra standard keys.
- Width 4 compact result matches the existing tablebase: `WIN`, DTM `21`, best move `b2b4`, `1,033,490` states.
- Compact export writes standard 8x8 tablebase keys, not dense internal keys.

Full width 6 export command:

```powershell
py export_tablebase.py --backend compact --board-width 6 --output-dir dist/w6 --gzip --progress 1000000 --export-progress 1000000 --progress-path-depth 20 --log-file dist/w6/export.log
```

Current remaining backend requirements:

- Compact table storage instead of Python `dict[int, int]`.
- Root/progress checkpointing so long runs can resume.
- Browser export that does not require JSONL as the final artifact.
- If width 8 remains too large, port the compact backend to Rust/C++ or implement retrograde/topological solving.
