"""Rules for pawn-only chess on active files a..width."""

from __future__ import annotations

from dataclasses import dataclass

WHITE = "w"
BLACK = "b"
NO_EP = -1

FILES = "abcdefgh"


@dataclass(frozen=True, slots=True)
class State:
    white: int
    black: int
    turn: str
    ep_square: int = NO_EP


@dataclass(frozen=True, slots=True, order=True)
class Move:
    from_square: int
    to_square: int
    capture: bool = False
    double: bool = False
    en_passant: bool = False
    winning: bool = False


def validate_width(width: int) -> None:
    if width not in (2, 4, 6, 8):
        raise ValueError("width must be one of 2, 4, 6, 8")


def opposite(side: str) -> str:
    return BLACK if side == WHITE else WHITE


def square(file_: int, rank: int) -> int:
    return rank * 8 + file_


def file_of(square_: int) -> int:
    return square_ & 7


def rank_of(square_: int) -> int:
    return square_ >> 3


def bit(square_: int) -> int:
    return 1 << square_


def algebraic(square_: int) -> str:
    return FILES[file_of(square_)] + str(rank_of(square_) + 1)


def parse_square(text: str) -> int:
    if len(text) != 2 or text[0] not in FILES or text[1] not in "12345678":
        raise ValueError(f"invalid square: {text}")
    return square(FILES.index(text[0]), int(text[1]) - 1)


def move_coord(move: Move) -> str:
    suffix = "e.p." if move.en_passant else ""
    return f"{algebraic(move.from_square)}{algebraic(move.to_square)}{suffix}"


def initial_state(width: int) -> State:
    validate_width(width)
    white = 0
    black = 0
    for file_ in range(width):
        white |= bit(square(file_, 1))
        black |= bit(square(file_, 6))
    return State(white=white, black=black, turn=WHITE, ep_square=NO_EP)


def occupied(state: State) -> int:
    return state.white | state.black


def pawns(state: State, side: str) -> int:
    return state.white if side == WHITE else state.black


def active(square_: int, width: int) -> bool:
    return 0 <= square_ < 64 and file_of(square_) < width


def goal_winner(state: State) -> str | None:
    if state.white & sum(bit(square(file_, 7)) for file_ in range(8)):
        return WHITE
    if state.black & sum(bit(square(file_, 0)) for file_ in range(8)):
        return BLACK
    return None


def legal_moves(state: State, width: int) -> tuple[Move, ...]:
    validate_width(width)
    if goal_winner(state) is not None:
        return ()

    own = state.white if state.turn == WHITE else state.black
    enemy = state.black if state.turn == WHITE else state.white
    all_pieces = own | enemy
    direction = 8 if state.turn == WHITE else -8
    start_rank = 1 if state.turn == WHITE else 6
    goal_rank = 7 if state.turn == WHITE else 0
    moves: list[Move] = []

    for from_square in _iter_bits(own):
        if not active(from_square, width):
            continue
        from_rank = rank_of(from_square)
        from_file = file_of(from_square)
        one = from_square + direction
        if active(one, width) and not (all_pieces & bit(one)):
            moves.append(
                Move(
                    from_square,
                    one,
                    winning=rank_of(one) == goal_rank,
                )
            )
            two = from_square + 2 * direction
            if from_rank == start_rank and active(two, width) and not (all_pieces & bit(two)):
                moves.append(Move(from_square, two, double=True))

        for file_delta in (-1, 1):
            to_file = from_file + file_delta
            if to_file < 0 or to_file >= width:
                continue
            to_square = one + file_delta
            if not active(to_square, width):
                continue
            if enemy & bit(to_square):
                moves.append(
                    Move(
                        from_square,
                        to_square,
                        capture=True,
                        winning=rank_of(to_square) == goal_rank,
                    )
                )
            elif to_square == state.ep_square:
                captured = to_square - direction
                if enemy & bit(captured):
                    moves.append(
                        Move(
                            from_square,
                            to_square,
                            capture=True,
                            en_passant=True,
                        )
                    )

    return tuple(sorted(moves))


def make_move(state: State, move: Move, width: int) -> State:
    if move not in legal_moves(state, width):
        raise ValueError(f"illegal move: {move_coord(move)}")

    moving_bit = bit(move.from_square)
    target_bit = bit(move.to_square)
    white = state.white
    black = state.black

    if state.turn == WHITE:
        white ^= moving_bit
        if move.en_passant:
            black ^= bit(move.to_square - 8)
        elif move.capture:
            black ^= target_bit
        white |= target_bit
    else:
        black ^= moving_bit
        if move.en_passant:
            white ^= bit(move.to_square + 8)
        elif move.capture:
            white ^= target_bit
        black |= target_bit

    ep_square = (move.from_square + move.to_square) // 2 if move.double else NO_EP
    return State(white=white, black=black, turn=opposite(state.turn), ep_square=ep_square)


def terminal_winner(state: State, width: int) -> str | None:
    winner = goal_winner(state)
    if winner is not None:
        return winner
    if not legal_moves(state, width):
        return opposite(state.turn)
    return None


def count_pawns(state: State, side: str) -> int:
    return pawns(state, side).bit_count()


def _iter_bits(bitboard: int):
    while bitboard:
        pawn = bitboard & -bitboard
        yield pawn.bit_length() - 1
        bitboard ^= pawn
