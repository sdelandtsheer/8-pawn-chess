"""Bot implementations and registry."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Protocol

from pawn_chess.rules import Move, State, legal_moves


class Bot(Protocol):
    name: str

    def choose_move(
        self,
        state: State,
        moves: tuple[Move, ...],
        width: int,
        rng: random.Random,
    ) -> Move:
        """Choose one legal move."""


@dataclass(frozen=True, slots=True)
class RandomBot:
    name: str = "random"

    def choose_move(
        self,
        state: State,
        moves: tuple[Move, ...],
        width: int,
        rng: random.Random,
    ) -> Move:
        del state, width
        return rng.choice(moves)


@dataclass(frozen=True, slots=True)
class FirstLegalBot:
    name: str = "first"

    def choose_move(
        self,
        state: State,
        moves: tuple[Move, ...],
        width: int,
        rng: random.Random,
    ) -> Move:
        del state, width, rng
        return moves[0]


def bot_registry() -> dict[str, Bot]:
    return {
        "first": FirstLegalBot(),
        "random": RandomBot(),
    }


def create_bot(name: str) -> Bot:
    registry = bot_registry()
    try:
        return registry[name]
    except KeyError as exc:
        known = ", ".join(sorted(registry))
        raise ValueError(f"unknown bot {name!r}; known bots: {known}") from exc


def all_bot_names() -> tuple[str, ...]:
    return tuple(sorted(bot_registry()))


def choose_or_first(
    bot: Bot,
    state: State,
    width: int,
    rng: random.Random,
) -> Move | None:
    moves = legal_moves(state, width)
    if not moves:
        return None
    move = bot.choose_move(state, moves, width, rng)
    if move not in moves:
        raise ValueError(f"bot {bot.name} returned an illegal move: {move}")
    return move
