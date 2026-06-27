# Mirror Copycat Check

Hypothesis:

```text
Black copies White's move by vertical mirror symmetry, so Black should win.
```

Result:

The hypothesis failed in direct tests. A `mirror` bot was added to restore
vertical symmetry as Black whenever legal. Against the current bot suite on
width 8, Black mirror-copy lost the tested games.

Representative line:

```text
1. h4 h5 2. g4 g5 3. hxg5 hxg4 4. g6 g3 5. g7 g2 6. g8
```

Interpretation:

- Copying preserves the board pattern.
- It does not remove White's first-move tempo.
- Once White creates a mirrored race, White promotes first and the game ends
  immediately.
- Black does not get the copied promotion reply.

Conclusion:

Mirror-copy is a useful test bot, but it is not a winning strategy. A strong
Black bot must know when to break symmetry.
