# 8-Pawn Chess Bot

This repo is now reset around the working Wix width-4 implementation and the
next goal: build a strong practical bot for the full pawn-only game.

## Current Working File

```text
browser/wix_width4_strategy.html
```

That file is self-contained and can be pasted into Wix.

## Next Direction

The previous full tablebase approach solved width 4 but did not scale cleanly to
width 6 in Python. The next implementation should be a strong bot based on game
principles, tactical proof search, and zugzwang/tempo accounting rather than a
complete offline tablebase.

Start from:

```text
BOT_PRINCIPLES.md
```
