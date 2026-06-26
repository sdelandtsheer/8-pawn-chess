# Width 6 Attempt

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

Conclusion:

- Width 6 is too large for the current Python dict-backed DFS/exporter.
- The next required milestone is a compact backend before width 6 tablebase export.
- A compiled or disk-aware retrograde/topological solver should replace the current Python full-table path for width 6 and width 8.

Recommended next backend requirements:

- Width-specific compact key with no inactive-file gaps.
- Compact table storage instead of Python `dict[int, int]`.
- Root/progress checkpointing so long runs can resume.
- Browser export that does not require JSONL as the final artifact.
