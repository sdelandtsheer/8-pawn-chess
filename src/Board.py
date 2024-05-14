# class Board for 8Pawns game
import numpy as np

class Board:
    def __init__(self):
        self.board = [
            [0] * 8,
            [-1] * 8, # Black pawns
            [0] * 8,
            [0] * 8,
            [0] * 8,
            [0] * 8,
            [1] * 8, # White pawns
            [0] * 8,
        ]
        self.current_player = 1 # White starts

    def __str__(self):
        board_str = ""
        for row in self.board:
            row_str = ""
            for pawn in row:
                if pawn in [-1, -2]:  # Check if pawn is either -1 or -2
                    row_str += f"{pawn} "
                else:
                    row_str += f"{pawn}  "  # Use two spaces for other numbers
            board_str += row_str.strip() + "\n"  # Strip trailing spaces before adding newline
        return board_str

    def get_moves_list(self, player):
        moves = []
        direction = player
        start_row = 6 if player == 1 else 1
        self.normalize_pawns(player)

        for row in range(8):
            for col in range(8):
                print(f'{row, col}')
                if self.board[row][col] == player: # if player's pawn
                    if self.board[row - direction][col] == 0: # if next square is free
                        moves.append((row, col, row - direction, col, False)) # one square forward
                    if self.board[row - direction][col] == 0 and self.board[row - (direction * 2)][col] == 0 and row == start_row:
                        moves.append((row, col, row - direction * 2, col, False))  # two squares forward
                    if col > 0:
                        if self.board[row - direction][col - 1] == -player or self.board[row - direction][col - 1] == -(player * 2):
                            moves.append((row, col, row - direction, col - 1, False))  # capture left
                        if self.board[row][col - 1] == -(player * 2):
                            moves.append((row, col, row - direction, col - 1, True))  # capture en-passant left
                    if col < 7:
                        if self.board[row - direction][col + 1] == -player or self.board[row - direction][col + 1] == -(player * 2):
                            moves.append((row, col, row - direction, col + 1, False))  # capture right
                        if self.board[row][col + 1] == -(player * 2):
                            moves.append((row, col, row - direction, col + 1, True))  # capture en-passant right
        return moves

    def normalize_pawns(self, player): # reset en-passant at the beginning of each move
        self.board = [[player if x == (player * 2) else x for x in row] for row in self.board]

    def push_move(self, move):
        from_row, from_col, to_row, to_col, is_ep = move
        this_pawn = self.board[from_row][from_col]
        self.board[from_row][from_col] = 0
        self.board[to_row][to_col] = this_pawn if abs(from_row - to_row) == 1 else this_pawn * 2
        if is_ep:
            self.board[from_row][to_col] = 0

    def is_winning(self, player):
        last_row = 6 if player == 1 else 1 # no need for very last row, if a pawn reaches 2nd or 7th row promotion is inevitable
        for col in range(8):
            if self.board[last_row][col] == player:
                return True
        if not self.get_moves_list(-player):
            return True
        return False

    def _evaluate_single(self, player):
        if self.is_winning(player):
            return np.inf
        elif self.is_winning(-player):
            return -np.inf

        theta1 = 1
        theta2 = 1
        start_row = 6 if player == 1 else 1

        # 1: reward for pawn existing, and advancing
        score_base = 0
        for row in range(8):
            for col in range(8):
                if self.board[row][col] in [player, player * 2]:
                    score_base += abs(row - start_row)

        # 2: reward for mobility
        score_mobility = len(self.get_moves_list(player))

        # add more functions here...

        # summing up
        score_single = score_base * theta1 + score_mobility * theta2

        return score_single

    def evaluate(self, player):
        pos = self._evaluate_single(player)
        neg = self._evaluate_single(-player)

        score = pos - neg

        return score

