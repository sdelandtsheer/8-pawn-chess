"""Deterministic bot-vs-bot evaluation arena."""

from __future__ import annotations

import csv
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from pawn_chess.bots import Bot, choose_or_first
from pawn_chess.rules import BLACK, WHITE, initial_state, make_move, move_coord, terminal_winner


@dataclass(frozen=True, slots=True)
class GameRecord:
    game_id: int
    white_bot: str
    black_bot: str
    winner: str
    winner_bot: str
    plies: int
    reason: str
    moves: str


@dataclass(slots=True)
class BotStats:
    bot: str
    games: int = 0
    wins: int = 0
    losses: int = 0
    white_games: int = 0
    white_wins: int = 0
    black_games: int = 0
    black_wins: int = 0
    total_plies: int = 0

    @property
    def win_rate(self) -> float:
        return 0.0 if self.games == 0 else self.wins / self.games

    @property
    def average_plies(self) -> float:
        return 0.0 if self.games == 0 else self.total_plies / self.games


def play_game(
    *,
    white_bot: Bot,
    black_bot: Bot,
    width: int,
    game_id: int,
    seed: int,
    max_plies: int = 256,
) -> GameRecord:
    rng = random.Random(seed)
    state = initial_state(width)
    played: list[str] = []

    for ply in range(max_plies + 1):
        winner = terminal_winner(state, width)
        if winner is not None:
            return _record(game_id, white_bot, black_bot, winner, ply, "terminal", played)
        if ply == max_plies:
            return _record(game_id, white_bot, black_bot, BLACK, ply, "max_plies", played)

        bot = white_bot if state.turn == WHITE else black_bot
        move = choose_or_first(bot, state, width, rng)
        if move is None:
            return _record(
                game_id,
                white_bot,
                black_bot,
                BLACK if state.turn == WHITE else WHITE,
                ply,
                "blocked",
                played,
            )
        played.append(move_coord(move))
        state = make_move(state, move, width)

    raise RuntimeError("unreachable")


def round_robin(
    bots: list[Bot],
    *,
    width: int,
    games_per_pair: int,
    seed: int,
) -> tuple[list[GameRecord], list[BotStats]]:
    games: list[GameRecord] = []
    game_id = 0
    for white in bots:
        for black in bots:
            for repeat in range(games_per_pair):
                game_seed = seed + game_id * 7919 + repeat
                games.append(
                    play_game(
                        white_bot=white,
                        black_bot=black,
                        width=width,
                        game_id=game_id,
                        seed=game_seed,
                    )
                )
                game_id += 1
    return games, summarize(games)


def summarize(games: list[GameRecord]) -> list[BotStats]:
    stats: dict[str, BotStats] = {}
    for game in games:
        white = stats.setdefault(game.white_bot, BotStats(game.white_bot))
        black = stats.setdefault(game.black_bot, BotStats(game.black_bot))
        white.games += 1
        white.white_games += 1
        white.total_plies += game.plies
        black.games += 1
        black.black_games += 1
        black.total_plies += game.plies

        if game.winner == WHITE:
            white.wins += 1
            white.white_wins += 1
            black.losses += 1
        else:
            black.wins += 1
            black.black_wins += 1
            white.losses += 1

    return sorted(stats.values(), key=lambda item: (-item.win_rate, item.bot))


def write_results(
    output_dir: Path,
    *,
    width: int,
    games_per_pair: int,
    seed: int,
    games: list[GameRecord],
    stats: list[BotStats],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_rows = [
        {
            **asdict(item),
            "win_rate": item.win_rate,
            "average_plies": item.average_plies,
        }
        for item in stats
    ]
    (output_dir / "summary.json").write_text(
        json.dumps(
            {
                "width": width,
                "games_per_pair": games_per_pair,
                "seed": seed,
                "total_games": len(games),
                "bots": summary_rows,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    with (output_dir / "games.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(asdict(games[0]).keys()))
        writer.writeheader()
        writer.writerows(asdict(game) for game in games)


def _record(
    game_id: int,
    white_bot: Bot,
    black_bot: Bot,
    winner: str,
    plies: int,
    reason: str,
    played: list[str],
) -> GameRecord:
    return GameRecord(
        game_id=game_id,
        white_bot=white_bot.name,
        black_bot=black_bot.name,
        winner=winner,
        winner_bot=white_bot.name if winner == WHITE else black_bot.name,
        plies=plies,
        reason=reason,
        moves=" ".join(played),
    )
