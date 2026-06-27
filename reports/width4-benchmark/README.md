# Width 4 Bot Benchmark

Command:

```powershell
py evaluate_bots.py --width 4 --games 20 --bots all --seed 20260627 --output-dir reports/width4-benchmark
```

Settings:

- Board width: `4`
- Bots: all registered bots
- Pairing: ordered round robin including self-play
- Games per ordered pairing: `20`
- Total games: `3,380`
- Seed: `20260627`

## Ranking

| Rank | Bot | Wins | Games | Win Rate | Avg Plies |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | tempo | 415 | 520 | 0.798 | 13.7 |
| 2 | center | 412 | 520 | 0.792 | 16.7 |
| 3 | principle | 398 | 520 | 0.765 | 13.7 |
| 4 | capture | 372 | 520 | 0.715 | 13.9 |
| 5 | passer | 338 | 520 | 0.650 | 13.7 |
| 6 | tactical1 | 231 | 520 | 0.444 | 14.1 |
| 7 | double | 209 | 520 | 0.402 | 14.0 |
| 8 | advance | 208 | 520 | 0.400 | 14.0 |
| 9 | edge | 207 | 520 | 0.398 | 13.8 |
| 10 | safe | 166 | 520 | 0.319 | 13.1 |
| 11 | first | 165 | 520 | 0.317 | 13.1 |
| 12 | random | 138 | 520 | 0.265 | 16.4 |
| 13 | last | 121 | 520 | 0.233 | 16.5 |

## Notes

- `tempo` is the current best simple algorithm in this field.
- `principle` is strong but not yet dominant; its broader feature set needs
  tuning against the simpler tempo/center biases.
- `random`, `first`, and `last` are useful floor baselines.
- These are width-4 results only; they should not be assumed to transfer
  directly to width 8.

Raw files:

- `summary.json`
- `games.csv`
