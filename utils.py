# -*- coding: utf-8 -*-
from config import BOARD_SIZE
from pieces import EMPTY_SQUARE

# --- Helper Functions ---
def get_piece_color(piece):
    if piece == EMPTY_SQUARE: return None
    return 'w' if piece.isupper() else 'b'

def is_on_board(r, f):
    return 0 <= r < BOARD_SIZE and 0 <= f < BOARD_SIZE

def coords_to_algebraic(r, f):
    if not is_on_board(r,f): return "??"
    rank = BOARD_SIZE - 1 - r
    file = f
    return chr(ord('a') + file) + str(rank + 1)

def algebraic_to_coords(alg):
    if not isinstance(alg, str) or len(alg) != 2: return None
    file_char, rank_char = alg[0], alg[1]
    # Adjust check for file based on BOARD_SIZE
    max_file_char = chr(ord('a') + BOARD_SIZE - 1)
    max_rank_char = str(BOARD_SIZE)
    if not (('a' <= file_char <= max_file_char) and ('1' <= rank_char <= max_rank_char)): return None

    file = ord(file_char) - ord('a')
    rank = int(rank_char) - 1
    internal_rank = BOARD_SIZE - 1 - rank
    if not is_on_board(internal_rank, file): return None # Should be redundant but safe
    return internal_rank, file

def piece_to_lower(piece_type): return piece_type.lower()
def piece_to_upper(piece_type): return piece_type.upper()
def get_opposite_color(color): return 'b' if color == 'w' else 'w'

def format_move_for_print(move):
    """Форматирует ход для вывода в консоль или лог."""
    if move is None: return "None"
    if move[0] == 'drop':
        _, piece, (r, f) = move
        return f"{piece.upper()}@{coords_to_algebraic(r, f)}"
    else:
        (r1, f1), (r2, f2), promotion = move
        s = f"{coords_to_algebraic(r1, f1)}{coords_to_algebraic(r2, f2)}"
        if promotion: s += f"={promotion.upper()}" # Показываем превращение
        return s

def is_same_move(move1, move2):
    """Проверяет, совпадают ли два хода (игнорируя дополнительные детали)"""
    if not move1 or not move2: return False
    if move1[0] == 'drop' and move2[0] == 'drop':
        return move1[1] == move2[1] and move1[2] == move2[2]
    elif move1[0] != 'drop' and move2[0] != 'drop':
        # Check if both are tuple-like (start, end, promotion)
        if isinstance(move1[0], tuple) and isinstance(move2[0], tuple) and \
           isinstance(move1[1], tuple) and isinstance(move2[1], tuple):
             return move1[0] == move2[0] and move1[1] == move2[1]
    return False