"""Bot implementations and registry."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Protocol

from pawn_chess.rules import (
    NO_EP,
    WHITE,
    Move,
    State,
    active,
    bit,
    count_pawns,
    file_of,
    legal_moves,
    make_move,
    opposite,
    pawns,
    rank_of,
    terminal_winner,
)


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


@dataclass(frozen=True, slots=True)
class PrincipleBot:
    name: str = "principle"

    def choose_move(
        self,
        state: State,
        moves: tuple[Move, ...],
        width: int,
        rng: random.Random,
    ) -> Move:
        del rng
        side = state.turn
        return max(
            moves,
            key=lambda move: (_principle_move_score(state, move, width, side), -move.to_square),
        )


def bot_registry() -> dict[str, Bot]:
    return {
        "first": FirstLegalBot(),
        "principle": PrincipleBot(),
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


def _principle_move_score(state: State, move: Move, width: int, side: str) -> int:
    child = make_move(state, move, width)
    winner = terminal_winner(child, width)
    if winner == side:
        return 1_000_000 - _promotion_distance_after_move(move, side)
    if winner == opposite(side):
        return -1_000_000

    opponent_moves = legal_moves(child, width)
    opponent_wins = sum(1 for reply in opponent_moves if reply.winning)
    opponent_danger = _dangerous_pawns(child, opposite(side), width)
    our_danger = _dangerous_pawns(child, side, width)
    our_safe_moves = _safe_move_count(child, side, width)
    opponent_safe_moves = _safe_move_count(child, opposite(side), width)

    score = _static_eval(child, side, width)
    score += 4_000 * our_danger
    score -= 5_000 * opponent_danger
    score += 120 * our_safe_moves
    score -= 160 * opponent_safe_moves
    score -= 80_000 * opponent_wins

    if move.capture:
        score += 1_000
    if move.en_passant:
        score += 1_800
    if move.double:
        score -= 350
        if _double_is_en_passant_exposed(child, move, side, width):
            score -= 7_500
    if _creates_passed_pawn(child, side, move.to_square, width):
        score += 3_500
    if _path_clear(child, side, move.to_square, width):
        score += 1_250
    if _moved_blocker(state, move, width, side):
        score -= 2_000

    return score


def _static_eval(state: State, side: str, width: int) -> int:
    other = opposite(side)
    score = 600 * (count_pawns(state, side) - count_pawns(state, other))
    score += 120 * (_advancement(state, side) - _advancement(state, other))
    score += 800 * (_passed_count(state, side, width) - _passed_count(state, other, width))
    score -= 300 * (_best_distance(state, side) - _best_distance(state, other))
    return score


def _advancement(state: State, side: str) -> int:
    total = 0
    for square in _iter_side(state, side):
        total += rank_of(square) if side == WHITE else 7 - rank_of(square)
    return total


def _best_distance(state: State, side: str) -> int:
    distances = [
        (7 - rank_of(square)) if side == WHITE else rank_of(square)
        for square in _iter_side(state, side)
    ]
    return min(distances, default=8)


def _promotion_distance_after_move(move: Move, side: str) -> int:
    return (7 - rank_of(move.to_square)) if side == WHITE else rank_of(move.to_square)


def _dangerous_pawns(state: State, side: str, width: int) -> int:
    danger = 0
    for square in _iter_side(state, side):
        distance = (7 - rank_of(square)) if side == WHITE else rank_of(square)
        if distance <= 2:
            danger += 3 - distance
        if _creates_passed_pawn(state, side, square, width):
            danger += 1
    return danger


def _safe_move_count(state: State, side: str, width: int) -> int:
    ep_square = state.ep_square if state.turn == side else NO_EP
    side_state = State(state.white, state.black, side, ep_square)
    count = 0
    for move in legal_moves(side_state, width):
        child = make_move(side_state, move, width)
        if terminal_winner(child, width) == opposite(side):
            continue
        replies = legal_moves(child, width)
        if any(reply.winning for reply in replies):
            continue
        count += 1
    return count


def _passed_count(state: State, side: str, width: int) -> int:
    return sum(
        1 for square in _iter_side(state, side) if _creates_passed_pawn(state, side, square, width)
    )


def _creates_passed_pawn(state: State, side: str, square: int, width: int) -> bool:
    enemy = pawns(state, opposite(side))
    file_ = file_of(square)
    rank = rank_of(square)
    rank_range = range(rank + 1, 8) if side == WHITE else range(rank - 1, -1, -1)
    for ahead_rank in rank_range:
        for ahead_file in (file_ - 1, file_, file_ + 1):
            if ahead_file < 0 or ahead_file >= width:
                continue
            if enemy & bit(ahead_rank * 8 + ahead_file):
                return False
    return True


def _path_clear(state: State, side: str, square: int, width: int) -> bool:
    del width
    all_pawns = state.white | state.black
    direction = 8 if side == WHITE else -8
    cursor = square + direction
    while 0 <= cursor < 64:
        if all_pawns & bit(cursor):
            return False
        cursor += direction
    return True


def _double_is_en_passant_exposed(state: State, move: Move, side: str, width: int) -> bool:
    if not move.double or state.ep_square == -1:
        return False
    enemy = pawns(state, opposite(side))
    ep_file = file_of(state.ep_square)
    enemy_rank = rank_of(move.to_square)
    for file_delta in (-1, 1):
        from_file = ep_file + file_delta
        if from_file < 0 or from_file >= width:
            continue
        if enemy & bit(enemy_rank * 8 + from_file):
            return True
    return False


def _moved_blocker(state: State, move: Move, width: int, side: str) -> bool:
    direction = 8 if side == WHITE else -8
    blocked_square = move.from_square + direction
    if not active(blocked_square, width):
        return False
    return bool(pawns(state, opposite(side)) & bit(blocked_square))


def _iter_side(state: State, side: str):
    bitboard = pawns(state, side)
    while bitboard:
        pawn = bitboard & -bitboard
        yield pawn.bit_length() - 1
        bitboard ^= pawn
