"""Validation helpers for rules, solver, and future browser parity checks."""

from __future__ import annotations

import random
from dataclasses import dataclass

from rules import (
    NO_EP,
    Move,
    State,
    encode_move,
    is_terminal,
    legal_moves,
    make_move,
    move_to_coord,
    normalize_state,
    occupied,
    perft,
    state_from_key,
    state_key,
)


@dataclass(frozen=True, slots=True)
class RuleSnapshot:
    """Serializable view for comparing independent rules engines."""

    key: int
    terminal: bool
    legal_move_codes: tuple[int, ...]
    legal_move_coords: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Playout:
    states: tuple[State, ...]
    moves: tuple[Move, ...]


def snapshot(state: State) -> RuleSnapshot:
    normalized = normalize_state(state)
    moves = legal_moves(normalized)
    return RuleSnapshot(
        key=state_key(normalized),
        terminal=is_terminal(normalized),
        legal_move_codes=tuple(encode_move(move) for move in moves),
        legal_move_coords=tuple(move_to_coord(move) for move in moves),
    )


def assert_state_invariants(state: State) -> None:
    normalized = normalize_state(state)
    if state != normalized:
        raise AssertionError(f"state is not normalized: {state!r} -> {normalized!r}")
    if state.white & state.black:
        raise AssertionError("white and black pawns overlap")
    if state.ep_square != NO_EP and occupied(state) & (1 << state.ep_square):
        raise AssertionError("en passant square must be empty")
    if state_from_key(state_key(state)) != state:
        raise AssertionError("state key does not round-trip")
    if is_terminal(state) and legal_moves(state):
        raise AssertionError("terminal states must not have legal moves")


def random_playout(
    start: State,
    *,
    seed: int,
    max_plies: int,
    stop_on_terminal: bool = True,
) -> Playout:
    if max_plies < 0:
        raise ValueError("max_plies must be non-negative")

    rng = random.Random(seed)
    states = [normalize_state(start)]
    moves: list[Move] = []
    current = states[0]

    for _ in range(max_plies):
        available = legal_moves(current)
        if not available or (stop_on_terminal and is_terminal(current)):
            break
        move = rng.choice(available)
        moves.append(move)
        current = make_move(current, move, validate=False)
        states.append(current)

    return Playout(tuple(states), tuple(moves))


def perft_divide(state: State, depth: int) -> tuple[tuple[str, int], ...]:
    if depth < 1:
        raise ValueError("depth must be at least 1")
    return tuple(
        (move_to_coord(move), perft(make_move(state, move, validate=False), depth - 1))
        for move in legal_moves(state)
    )
