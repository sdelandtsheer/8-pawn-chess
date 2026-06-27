"""Bot implementations and registry."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Protocol

from pawn_chess.rules import (
    BLACK,
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

_PROOF_CACHE: dict[tuple[State, int, int], tuple[int, int]] = {}


class Bot(Protocol):
    name: str
    deterministic: bool

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
    deterministic: bool = False

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


@dataclass(frozen=True, slots=True)
class LastLegalBot:
    name: str = "last"

    def choose_move(
        self,
        state: State,
        moves: tuple[Move, ...],
        width: int,
        rng: random.Random,
    ) -> Move:
        del state, width, rng
        return moves[-1]


@dataclass(frozen=True, slots=True)
class CaptureBot:
    name: str = "capture"

    def choose_move(
        self,
        state: State,
        moves: tuple[Move, ...],
        width: int,
        rng: random.Random,
    ) -> Move:
        del state, width, rng
        return _best(moves, lambda move: 100 * move.capture + 20 * move.en_passant + move.winning)


@dataclass(frozen=True, slots=True)
class AdvanceBot:
    name: str = "advance"

    def choose_move(
        self,
        state: State,
        moves: tuple[Move, ...],
        width: int,
        rng: random.Random,
    ) -> Move:
        del width, rng
        return _best(moves, lambda move: 1000 * move.winning + _advance_delta(move, state.turn))


@dataclass(frozen=True, slots=True)
class CenterBot:
    name: str = "center"

    def choose_move(
        self,
        state: State,
        moves: tuple[Move, ...],
        width: int,
        rng: random.Random,
    ) -> Move:
        del state, rng
        center = (width - 1) / 2
        return _best(
            moves, lambda move: 1000 * move.winning - abs(file_of(move.to_square) - center)
        )


@dataclass(frozen=True, slots=True)
class EdgeBot:
    name: str = "edge"

    def choose_move(
        self,
        state: State,
        moves: tuple[Move, ...],
        width: int,
        rng: random.Random,
    ) -> Move:
        del state, rng
        return _best(
            moves,
            lambda move: (
                1000 * move.winning
                + max(file_of(move.to_square), width - 1 - file_of(move.to_square))
            ),
        )


@dataclass(frozen=True, slots=True)
class DoublePushBot:
    name: str = "double"

    def choose_move(
        self,
        state: State,
        moves: tuple[Move, ...],
        width: int,
        rng: random.Random,
    ) -> Move:
        del state, width, rng
        return _best(moves, lambda move: 1000 * move.winning + 50 * move.double)


@dataclass(frozen=True, slots=True)
class SafeBot:
    name: str = "safe"

    def choose_move(
        self,
        state: State,
        moves: tuple[Move, ...],
        width: int,
        rng: random.Random,
    ) -> Move:
        del rng
        side = state.turn
        return _best(
            moves,
            lambda move: (
                1000 * move.winning - 500 * _allows_immediate_win(state, move, width, side)
            ),
        )


@dataclass(frozen=True, slots=True)
class TempoBot:
    name: str = "tempo"

    def choose_move(
        self,
        state: State,
        moves: tuple[Move, ...],
        width: int,
        rng: random.Random,
    ) -> Move:
        del rng
        side = state.turn
        return _best(
            moves,
            lambda move: (
                1000 * move.winning + _tempo_score(make_move(state, move, width), side, width)
            ),
        )


@dataclass(frozen=True, slots=True)
class PassedPawnBot:
    name: str = "passer"

    def choose_move(
        self,
        state: State,
        moves: tuple[Move, ...],
        width: int,
        rng: random.Random,
    ) -> Move:
        del rng
        side = state.turn
        return _best(
            moves,
            lambda move: (
                1000 * move.winning
                + 100 * _creates_passed_after_move(state, move, width, side)
                + 30 * _path_clear(make_move(state, move, width), side, move.to_square, width)
            ),
        )


@dataclass(frozen=True, slots=True)
class OnePlyTacticalBot:
    name: str = "tactical1"

    def choose_move(
        self,
        state: State,
        moves: tuple[Move, ...],
        width: int,
        rng: random.Random,
    ) -> Move:
        del rng
        side = state.turn
        return _best(
            moves,
            lambda move: (
                10000 * move.winning
                - 9000 * _allows_immediate_win(state, move, width, side)
                + 100 * move.capture
                + 30 * _advance_delta(move, side)
            ),
        )


@dataclass(frozen=True, slots=True)
class ZugzwangBot:
    name: str = "zugzwang"

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
            key=lambda move: _zugzwang_key(state, move, width, side),
        )


@dataclass(frozen=True, slots=True)
class BreakTempoBot:
    name: str = "breaktempo"
    deterministic: bool = False
    search_depth: int = 2

    def choose_move(
        self,
        state: State,
        moves: tuple[Move, ...],
        width: int,
        rng: random.Random,
    ) -> Move:
        side = state.turn
        memo: dict[tuple[State, int], tuple[int, int]] = {}
        proven_wins: list[tuple[int, Move]] = []
        proven_losses: list[tuple[int, Move]] = []
        default_candidates: list[tuple[tuple[int, ...], Move]] = []

        for move in moves:
            child = make_move(state, move, width)
            proof_outcome, proof_dtm = _proof_search(
                child,
                width,
                self.search_depth - 1,
                memo,
            )
            if proof_outcome == -1:
                proven_wins.append((proof_dtm + 1, move))
            elif proof_outcome == 1:
                proven_losses.append((proof_dtm + 1, move))
            else:
                default_candidates.append((_breaktempo_key(state, move, width, side), move))

        if proven_wins:
            best_dtm = min(dtm for dtm, _ in proven_wins)
            return rng.choice([move for dtm, move in proven_wins if dtm == best_dtm])

        if default_candidates:
            best_key = max(key for key, _ in default_candidates)
            return rng.choice([move for key, move in default_candidates if key == best_key])

        best_delay = max(dtm for dtm, _ in proven_losses)
        return rng.choice([move for dtm, move in proven_losses if dtm == best_delay])


@dataclass(frozen=True, slots=True)
class MirrorBot:
    name: str = "mirror"

    def choose_move(
        self,
        state: State,
        moves: tuple[Move, ...],
        width: int,
        rng: random.Random,
    ) -> Move:
        del rng
        if state.turn == BLACK:
            for move in moves:
                if _restores_vertical_mirror(make_move(state, move, width), width):
                    return move
        side = state.turn
        return max(
            moves,
            key=lambda move: _zugzwang_key(state, move, width, side),
        )


def bot_registry() -> dict[str, Bot]:
    return {
        "advance": AdvanceBot(),
        "breaktempo": BreakTempoBot(),
        "capture": CaptureBot(),
        "center": CenterBot(),
        "double": DoublePushBot(),
        "edge": EdgeBot(),
        "first": FirstLegalBot(),
        "last": LastLegalBot(),
        "mirror": MirrorBot(),
        "passer": PassedPawnBot(),
        "principle": PrincipleBot(),
        "random": RandomBot(),
        "safe": SafeBot(),
        "tactical1": OnePlyTacticalBot(),
        "tempo": TempoBot(),
        "zugzwang": ZugzwangBot(),
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


def _best(moves: tuple[Move, ...], score) -> Move:
    return max(moves, key=lambda move: (score(move), -move.from_square, -move.to_square))


def _advance_delta(move: Move, side: str) -> int:
    if side == WHITE:
        return rank_of(move.to_square) - rank_of(move.from_square)
    return rank_of(move.from_square) - rank_of(move.to_square)


def _allows_immediate_win(state: State, move: Move, width: int, side: str) -> bool:
    child = make_move(state, move, width)
    if terminal_winner(child, width) == side:
        return False
    return any(reply.winning for reply in legal_moves(child, width))


def _tempo_score(state: State, side: str, width: int) -> int:
    return 10 * _safe_move_count(state, side, width) - 12 * _safe_move_count(
        state, opposite(side), width
    )


def _creates_passed_after_move(state: State, move: Move, width: int, side: str) -> bool:
    return _creates_passed_pawn(make_move(state, move, width), side, move.to_square, width)


def _zugzwang_key(state: State, move: Move, width: int, side: str) -> tuple[int, ...]:
    child = make_move(state, move, width)
    winner = terminal_winner(child, width)
    if winner == side:
        return (5, -_promotion_distance_after_move(move, side), move.capture, -move.to_square)
    if winner == opposite(side):
        return (-5, -move.to_square)

    opponent_replies = legal_moves(child, width)
    opponent_winning_replies = [
        reply
        for reply in opponent_replies
        if terminal_winner(make_move(child, reply, width), width) == opposite(side)
    ]
    allows_immediate_loss = bool(opponent_winning_replies)

    opponent_safe_replies = []
    worst_our_followup_safe_count = 99
    for reply in opponent_replies:
        grandchild = make_move(child, reply, width)
        if terminal_winner(grandchild, width) == opposite(side):
            continue
        if any(answer.winning for answer in legal_moves(grandchild, width)):
            continue
        opponent_safe_replies.append(reply)
        worst_our_followup_safe_count = min(
            worst_our_followup_safe_count,
            _safe_move_count(grandchild, side, width),
        )

    if worst_our_followup_safe_count == 99:
        worst_our_followup_safe_count = 0

    child_safe_moves = _safe_move_count(child, side, width)
    opponent_safe_count = len(opponent_safe_replies)
    forcing_bonus = 1 if opponent_safe_count == 0 else 0
    passer_bonus = int(_creates_passed_pawn(child, side, move.to_square, width))
    clear_path_bonus = int(_path_clear(child, side, move.to_square, width))
    tactical_bonus = 2 * int(move.capture) + 3 * int(move.en_passant)
    progress = _advance_delta(move, side)
    double_penalty = int(move.double) + 3 * int(
        _double_is_en_passant_exposed(child, move, side, width)
    )

    return (
        2 - int(allows_immediate_loss),
        -opponent_safe_count,
        worst_our_followup_safe_count,
        child_safe_moves,
        forcing_bonus,
        passer_bonus,
        clear_path_bonus,
        tactical_bonus,
        progress,
        -double_penalty,
        -move.from_square,
        -move.to_square,
    )


def _breaktempo_key(state: State, move: Move, width: int, side: str) -> tuple[int, ...]:
    child = make_move(state, move, width)
    winner = terminal_winner(child, width)
    zugzwang_key = _zugzwang_key(state, move, width, side)
    if winner == side:
        return (10, -_promotion_distance_after_move(move, side), 0, *zugzwang_key)
    if winner == opposite(side):
        return (-10, 0, 0, *zugzwang_key)

    opponent_immediate_wins = sum(1 for reply in legal_moves(child, width) if reply.winning)
    our_unstoppable = _unstoppable_count(child, side, width)
    opponent_unstoppable = _unstoppable_count(child, opposite(side), width)
    our_safe = _safe_move_count(child, side, width)
    opponent_safe = _safe_move_count(child, opposite(side), width)
    tempo_delta = our_safe - opponent_safe
    break_score = _break_score(state, child, move, width, side)

    if opponent_immediate_wins:
        return (
            -2,
            -opponent_immediate_wins,
            our_unstoppable,
            break_score,
            -opponent_safe,
            our_safe,
            *zugzwang_key,
        )

    if our_unstoppable > opponent_unstoppable:
        return (
            8,
            our_unstoppable - opponent_unstoppable,
            -_best_distance(child, side),
            -opponent_safe,
            our_safe,
            *zugzwang_key,
        )

    if opponent_unstoppable > our_unstoppable:
        return (
            -1,
            break_score,
            our_unstoppable,
            -opponent_unstoppable,
            -opponent_safe,
            our_safe,
            *zugzwang_key,
        )

    if tempo_delta >= 0:
        return (
            5,
            -opponent_safe,
            our_safe,
            tempo_delta,
            -_quiet_breakiness(move),
            -_best_distance(child, side),
            *zugzwang_key,
        )

    return (
        3,
        break_score,
        -opponent_safe,
        our_safe,
        tempo_delta,
        -_best_distance(child, side),
        *zugzwang_key,
    )


def _proof_search(
    state: State,
    width: int,
    depth: int,
    memo: dict[tuple[State, int], tuple[int, int]],
) -> tuple[int, int]:
    global_key = (state, width, depth)
    global_cached = _PROOF_CACHE.get(global_key)
    if global_cached is not None:
        return global_cached

    winner = terminal_winner(state, width)
    if winner == state.turn:
        result = (1, 0)
        _PROOF_CACHE[global_key] = result
        return result
    if winner == opposite(state.turn):
        result = (-1, 0)
        _PROOF_CACHE[global_key] = result
        return result
    if depth <= 0:
        result = (0, 0)
        _PROOF_CACHE[global_key] = result
        return result

    key = (state, depth)
    cached = memo.get(key)
    if cached is not None:
        return cached

    unknown = False
    longest_loss = -1
    for move in _ordered_for_proof(state, width):
        child_outcome, child_dtm = _proof_search(
            make_move(state, move, width), width, depth - 1, memo
        )
        current_dtm = child_dtm + 1
        if child_outcome == -1:
            result = (1, current_dtm)
            memo[key] = result
            _PROOF_CACHE[global_key] = result
            return result
        if child_outcome == 0:
            unknown = True
        elif child_outcome == 1:
            longest_loss = max(longest_loss, current_dtm)

    result = (0, 0) if unknown else (-1, longest_loss)
    memo[key] = result
    _PROOF_CACHE[global_key] = result
    return result


def _ordered_for_proof(state: State, width: int) -> tuple[Move, ...]:
    side = state.turn
    return tuple(
        sorted(
            legal_moves(state, width),
            key=lambda move: _breaktempo_key(state, move, width, side),
            reverse=True,
        )
    )


def _unstoppable_count(state: State, side: str, width: int) -> int:
    return sum(
        1
        for square in _iter_side(state, side)
        if _creates_passed_pawn(state, side, square, width)
        and _path_clear(state, side, square, width)
    )


def _break_score(state: State, child: State, move: Move, width: int, side: str) -> int:
    del state
    score = 0
    score += 8 * int(_creates_passed_pawn(child, side, move.to_square, width))
    score += 5 * int(_path_clear(child, side, move.to_square, width))
    score += 4 * int(move.capture)
    score += 6 * int(move.en_passant)
    score += 2 * _advance_delta(move, side)
    score -= 5 * int(_double_is_en_passant_exposed(child, move, side, width))
    return score


def _quiet_breakiness(move: Move) -> int:
    return int(move.capture) + int(move.en_passant) + int(move.double)


def _restores_vertical_mirror(state: State, width: int) -> bool:
    return state.black == _mirror_bitboard(state.white, width)


def _mirror_bitboard(bitboard: int, width: int) -> int:
    mirrored = 0
    for square in _iter_raw_bits(bitboard):
        file_ = file_of(square)
        if file_ >= width:
            continue
        mirrored |= bit(_mirror_square(square))
    return mirrored


def _mirror_square(square: int) -> int:
    return (7 - rank_of(square)) * 8 + file_of(square)


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
    yield from _iter_raw_bits(bitboard)


def _iter_raw_bits(bitboard: int):
    while bitboard:
        pawn = bitboard & -bitboard
        yield pawn.bit_length() - 1
        bitboard ^= pawn
