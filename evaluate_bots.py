from __future__ import annotations

import argparse
from pathlib import Path

from pawn_chess.arena import round_robin, write_results
from pawn_chess.bots import all_bot_names, create_bot
from pawn_chess.rules import validate_width


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate pawn-chess bots.")
    parser.add_argument("--width", type=int, default=4)
    parser.add_argument("--games", type=int, default=10, help="games per ordered bot pairing")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--bots",
        default="random,first",
        help="comma-separated bot names, or 'all'",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("results/latest"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    validate_width(args.width)
    names = all_bot_names() if args.bots == "all" else tuple(args.bots.split(","))
    bots = [create_bot(name.strip()) for name in names if name.strip()]
    games, stats = round_robin(
        bots,
        width=args.width,
        games_per_pair=args.games,
        seed=args.seed,
    )
    write_results(
        args.output_dir,
        width=args.width,
        games_per_pair=args.games,
        seed=args.seed,
        games=games,
        stats=stats,
    )
    for rank, item in enumerate(stats, start=1):
        print(
            f"{rank:02d}. {item.bot:16s} "
            f"win_rate={item.win_rate:.3f} "
            f"wins={item.wins}/{item.games} "
            f"avg_plies={item.average_plies:.1f}"
        )
    print(f"wrote {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
