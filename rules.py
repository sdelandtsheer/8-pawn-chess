"""Pure rules engine for the 8-pawn chess variant.

Square indexing is little-endian by rank: a1 is 0, h1 is 7, a8 is 56,
and h8 is 63. White moves toward larger square numbers; Black moves toward
smaller square numbers.
"""

from __future__ import annotations

from dataclasses import dataclass

WHITE = 0
BLACK = 1

NO_EP = -1
BOARD_SIZE = 64

FLAG_CAPTURE = 1
FLAG_DOUBLE = 2
FLAG_EN_PASSANT = 4
FLAG_WINNING = 8

RANK_1 = 0x00000000000000FF
RANK_2 = 0x000000000000FF00
RANK_7 = 0x00FF000000000000
RANK_8 = 0xFF00000000000000
ALL_SQUARES = (1 << BOARD_SIZE) - 1

FILES = "abcdefgh"
VALID_BOARD_WIDTHS = (2, 4, 6, 8)


@dataclass(frozen=True, slots=True)
class State:
    """Complete game state.

    `turn` is the side to move: `WHITE` (0) or `BLACK` (1).
    `ep_square` is normalized to `NO_EP` when no legal en passant capture exists.
    """

    white: int
    black: int
    turn: int
    ep_square: int = NO_EP

    def __post_init__(self) -> None:
        validate_state_fields(self)


@dataclass(frozen=True, slots=True, order=True)
class Move:
    """A legal move with compact bit flags."""

    from_square: int
    to_square: int
    flags: int = 0

    def __post_init__(self) -> None:
        validate_square(self.from_square)
        validate_square(self.to_square)
        if self.flags < 0 or self.flags > 15:
            raise ValueError(f"move flags must fit in four bits: {self.flags}")


def validate_square(square: int) -> None:
    if not 0 <= square < BOARD_SIZE:
        raise ValueError(f"square must be in 0..63: {square}")


def validate_state_fields(state: State) -> None:
    if state.white < 0 or state.black < 0:
        raise ValueError("bitboards must be non-negative")
    if state.white & ~ALL_SQUARES or state.black & ~ALL_SQUARES:
        raise ValueError("bitboards must fit in 64 bits")
    if state.white & state.black:
        raise ValueError("white and black bitboards overlap")
    if state.turn not in (WHITE, BLACK):
        raise ValueError(f"turn must be WHITE(0) or BLACK(1): {state.turn}")
    if state.ep_square != NO_EP:
        validate_square(state.ep_square)


def validate_board_width(board_width: int) -> None:
    if board_width not in VALID_BOARD_WIDTHS:
        raise ValueError(f"board_width must be one of {VALID_BOARD_WIDTHS}: {board_width}")


def bit(square: int) -> int:
    validate_square(square)
    return 1 << square


def file_index(square: int) -> int:
    validate_square(square)
    return square % 8


def rank_index(square: int) -> int:
    validate_square(square)
    return square // 8


def square_is_on_board(square: int, board_width: int = 8) -> bool:
    validate_square(square)
    validate_board_width(board_width)
    return file_index(square) < board_width


def square_to_algebraic(square: int) -> str:
    validate_square(square)
    return f"{FILES[file_index(square)]}{rank_index(square) + 1}"


def algebraic_to_square(name: str) -> int:
    if len(name) != 2:
        raise ValueError(f"square name must have length 2: {name!r}")
    file_char, rank_char = name[0].lower(), name[1]
    if file_char not in FILES or rank_char not in "12345678":
        raise ValueError(f"invalid square name: {name!r}")
    return FILES.index(file_char) + (int(rank_char) - 1) * 8


def move_to_coord(move: Move) -> str:
    return f"{square_to_algebraic(move.from_square)}{square_to_algebraic(move.to_square)}"


def encode_move(move: Move) -> int:
    return move.from_square | (move.to_square << 6) | (move.flags << 12)


def decode_move(code: int) -> Move:
    if code < 0 or code >= (1 << 16):
        raise ValueError(f"move code must fit in 16 bits: {code}")
    return Move(code & 0x3F, (code >> 6) & 0x3F, (code >> 12) & 0xF)


def _rank_width_mask(rank: int, board_width: int) -> int:
    validate_board_width(board_width)
    if not 0 <= rank <= 7:
        raise ValueError(f"rank must be in 0..7: {rank}")
    return sum(1 << (rank * 8 + file_) for file_ in range(board_width))


def initial_state(board_width: int = 8) -> State:
    validate_board_width(board_width)
    return State(_rank_width_mask(1, board_width), _rank_width_mask(6, board_width), WHITE, NO_EP)


def occupied(state: State) -> int:
    return state.white | state.black


def pawns_for_turn(state: State) -> int:
    return state.white if state.turn == WHITE else state.black


def opponent_pawns(state: State) -> int:
    return state.black if state.turn == WHITE else state.white


def terminal_winner(state: State) -> int | None:
    if state.white & RANK_8:
        return WHITE
    if state.black & RANK_1:
        return BLACK
    return None


def is_terminal(state: State) -> bool:
    return terminal_winner(state) is not None


def iter_squares(bitboard: int) -> tuple[int, ...]:
    if bitboard < 0 or bitboard & ~ALL_SQUARES:
        raise ValueError("bitboard must fit in 64 bits")

    squares: list[int] = []
    remaining = bitboard
    while remaining:
        least = remaining & -remaining
        squares.append(least.bit_length() - 1)
        remaining ^= least
    return tuple(squares)


def _ep_capture_exists(state: State, board_width: int = 8) -> bool:
    validate_board_width(board_width)
    if state.ep_square == NO_EP:
        return False

    ep = state.ep_square
    if not square_is_on_board(ep, board_width):
        return False
    ep_file = file_index(ep)
    pawns = pawns_for_turn(state)

    if state.turn == WHITE:
        captured_square = ep - 8
        if not (0 <= captured_square < BOARD_SIZE and state.black & bit(captured_square)):
            return False
        candidate_offsets = (-9, -7)
    else:
        captured_square = ep + 8
        if not (0 <= captured_square < BOARD_SIZE and state.white & bit(captured_square)):
            return False
        candidate_offsets = (7, 9)

    for offset in candidate_offsets:
        from_square = ep + offset
        if not 0 <= from_square < BOARD_SIZE:
            continue
        if (
            square_is_on_board(from_square, board_width)
            and abs(file_index(from_square) - ep_file) == 1
            and pawns & bit(from_square)
        ):
            return True
    return False


def normalize_state(state: State, board_width: int = 8) -> State:
    validate_board_width(board_width)
    validate_state_fields(state)
    if state.ep_square == NO_EP or _ep_capture_exists(state, board_width):
        return state
    return State(state.white, state.black, state.turn, NO_EP)


def state_key(state: State, board_width: int = 8) -> int:
    normalized = normalize_state(state, board_width)
    ep_code = 0 if normalized.ep_square == NO_EP else normalized.ep_square + 1
    return normalized.white | (normalized.black << 64) | (normalized.turn << 128) | (ep_code << 129)


def state_from_key(key: int, board_width: int = 8) -> State:
    validate_board_width(board_width)
    if key < 0:
        raise ValueError("state key must be non-negative")
    white = key & ALL_SQUARES
    black = (key >> 64) & ALL_SQUARES
    turn = (key >> 128) & 1
    ep_code = (key >> 129) & 0x7F
    if ep_code > 64:
        raise ValueError(f"invalid ep code in state key: {ep_code}")
    ep_square = NO_EP if ep_code == 0 else ep_code - 1
    return normalize_state(State(white, black, turn, ep_square), board_width)


def _single_push(state: State, from_square: int, board_width: int = 8) -> int | None:
    validate_board_width(board_width)
    direction = 8 if state.turn == WHITE else -8
    to_square = from_square + direction
    if not 0 <= to_square < BOARD_SIZE:
        return None
    if not square_is_on_board(to_square, board_width):
        return None
    if occupied(state) & bit(to_square):
        return None
    return to_square


def _is_start_rank(turn: int, square: int) -> bool:
    start_rank = 1 if turn == WHITE else 6
    return rank_index(square) == start_rank


def _is_goal_rank(turn: int, square: int) -> bool:
    goal_rank = 7 if turn == WHITE else 0
    return rank_index(square) == goal_rank


def _capture_targets(state: State, from_square: int, board_width: int = 8) -> tuple[int, ...]:
    validate_board_width(board_width)
    from_file = file_index(from_square)
    if state.turn == WHITE:
        pairs = (
            (from_file > 0, from_square + 7),
            (from_file < board_width - 1, from_square + 9),
        )
    else:
        pairs = (
            (from_file > 0, from_square - 9),
            (from_file < board_width - 1, from_square - 7),
        )
    return tuple(target for allowed, target in pairs if allowed and 0 <= target < BOARD_SIZE)


def legal_moves(state: State, board_width: int = 8) -> tuple[Move, ...]:
    validate_board_width(board_width)
    state = normalize_state(state, board_width)
    if is_terminal(state):
        return ()

    moves: list[Move] = []
    all_pawns = occupied(state)
    enemies = opponent_pawns(state)
    direction = 8 if state.turn == WHITE else -8

    for from_square in iter_squares(pawns_for_turn(state)):
        if not square_is_on_board(from_square, board_width):
            continue
        one_step = _single_push(state, from_square, board_width)
        if one_step is not None:
            flags = FLAG_WINNING if _is_goal_rank(state.turn, one_step) else 0
            moves.append(Move(from_square, one_step, flags))

            two_step = from_square + direction * 2
            if _is_start_rank(state.turn, from_square) and not (all_pawns & bit(two_step)):
                moves.append(Move(from_square, two_step, FLAG_DOUBLE))

        for target in _capture_targets(state, from_square, board_width):
            target_bit = bit(target)
            if enemies & target_bit:
                flags = FLAG_CAPTURE
                if _is_goal_rank(state.turn, target):
                    flags |= FLAG_WINNING
                moves.append(Move(from_square, target, flags))
            elif target == state.ep_square:
                moves.append(Move(from_square, target, FLAG_CAPTURE | FLAG_EN_PASSANT))

    return tuple(sorted(moves))


def find_legal_move(state: State, coord: str, board_width: int = 8) -> Move:
    if len(coord) != 4:
        raise ValueError(f"coordinate move must have length 4: {coord!r}")
    from_square = algebraic_to_square(coord[:2])
    to_square = algebraic_to_square(coord[2:])
    for move in legal_moves(state, board_width):
        if move.from_square == from_square and move.to_square == to_square:
            return move
    raise ValueError(f"illegal move {coord!r} in state {state}")


def make_move(
    state: State,
    move: Move,
    *,
    validate: bool = True,
    board_width: int = 8,
) -> State:
    validate_board_width(board_width)
    state = normalize_state(state, board_width)
    if validate and move not in legal_moves(state, board_width):
        raise ValueError(f"illegal move {move_to_coord(move)} in state {state}")

    mover_bit = bit(move.from_square)
    target_bit = bit(move.to_square)
    white = state.white
    black = state.black
    next_ep = NO_EP

    if state.turn == WHITE:
        white = (white & ~mover_bit) | target_bit
        if move.flags & FLAG_EN_PASSANT:
            black &= ~bit(move.to_square - 8)
        else:
            black &= ~target_bit
        if move.flags & FLAG_DOUBLE:
            next_ep = move.from_square + 8
        next_turn = BLACK
    else:
        black = (black & ~mover_bit) | target_bit
        if move.flags & FLAG_EN_PASSANT:
            white &= ~bit(move.to_square + 8)
        else:
            white &= ~target_bit
        if move.flags & FLAG_DOUBLE:
            next_ep = move.from_square - 8
        next_turn = WHITE

    return normalize_state(State(white, black, next_turn, next_ep), board_width)


def play_coord_moves(
    state: State,
    coords: tuple[str, ...] | list[str],
    board_width: int = 8,
) -> State:
    current = state
    for coord in coords:
        current = make_move(
            current,
            find_legal_move(current, coord, board_width),
            board_width=board_width,
        )
    return current


def perft(state: State, depth: int, board_width: int = 8) -> int:
    validate_board_width(board_width)
    if depth < 0:
        raise ValueError(f"depth must be non-negative: {depth}")
    if depth == 0:
        return 1

    total = 0
    for move in legal_moves(state, board_width):
        total += perft(
            make_move(state, move, validate=False, board_width=board_width),
            depth - 1,
            board_width,
        )
    return total
