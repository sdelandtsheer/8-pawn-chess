# 8-Pawn Chess Bot

Pawn-only chess experiments and a standalone browser bot.

## Playable HTML

Main deliverable:

```text
browser/wix_width8_zugzwang.html
```

It is a self-contained width-8 browser game using the `zugzwang` bot. Paste the
whole file into a Wix HTML embed.

Previous width-4 exact strategy page:

```text
browser/wix_width4_strategy.html
```

## Bot Idea

The current best practical bot is `zugzwang`. It does not use a full tablebase.
It prioritizes:

- immediate wins;
- avoiding immediate losses;
- minimizing the opponent's safe replies;
- preserving our own safe replies;
- using passed pawns, captures, clear paths, and progress only as tie-breakers.

This came from the width-4 benchmark where direct safe-reply minimization beat a
broader weighted evaluation.

## Local Checks

```powershell
py -m unittest discover -s tests
py -m ruff check .
py -m ruff format --check .
```

## Benchmark

Run a width-4 bot tournament:

```powershell
py evaluate_bots.py --width 4 --games 200 --bots all --seed 20260628 --progress 2000 --output-dir reports/width4-benchmark-10x
```

Latest summary:

```text
reports/width4-benchmark-10x/README.md
reports/width4-benchmark-10x/summary.json
```

Raw per-game CSV files are ignored to keep the repo small.
