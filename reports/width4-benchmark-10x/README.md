# Width 4 Bot Benchmark 10x

Command:

```powershell
py evaluate_bots.py --width 4 --games 200 --bots all --seed 20260628 --progress 2000 --output-dir reports/width4-benchmark-10x
```

Settings:

- Board width: `4`
- Bots: all registered bots, including `zugzwang`
- Pairing: ordered round robin including self-play
- Games per ordered pairing: `200`
- Total games: `39,200`
- Seed: `20260628`

## Ranking

| Rank | Bot | Wins | Games | Win Rate | Avg Plies |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | zugzwang | 5,374 | 5,600 | 0.960 | 15.9 |
| 2 | tempo | 4,152 | 5,600 | 0.741 | 13.7 |
| 3 | center | 4,110 | 5,600 | 0.734 | 16.5 |
| 4 | principle | 3,978 | 5,600 | 0.710 | 13.5 |
| 5 | capture | 3,727 | 5,600 | 0.666 | 14.2 |
| 6 | passer | 3,341 | 5,600 | 0.597 | 14.1 |
| 7 | tactical1 | 2,304 | 5,600 | 0.411 | 14.0 |
| 8 | double | 2,088 | 5,600 | 0.373 | 14.0 |
| 9 | advance | 2,066 | 5,600 | 0.369 | 14.0 |
| 10 | edge | 2,014 | 5,600 | 0.360 | 14.0 |
| 11 | random | 1,617 | 5,600 | 0.289 | 16.2 |
| 12 | safe | 1,616 | 5,600 | 0.289 | 13.2 |
| 13 | first | 1,613 | 5,600 | 0.288 | 13.3 |
| 14 | last | 1,200 | 5,600 | 0.214 | 16.7 |

## Interpretation

`zugzwang` is currently the strongest width-4 bot by a wide margin. The result
supports the hypothesis that move safety and opponent-safe-reply minimization
should be treated as primary ordering criteria, not as terms blended into a
general positional score.

Raw files:

- `summary.json`
- `games.csv`
