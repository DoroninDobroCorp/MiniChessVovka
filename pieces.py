# -*- coding: utf-8 -*-
import pygame
from config import SQUARE_SIZE, WHITE, BLACK, PIECE_BG_COLORS

# --- Piece Representation ---
EMPTY_SQUARE = '.'
PAWN = ['P', 'p']
KNIGHT = ['N', 'n']
BISHOP = ['B', 'b']
ROOK = ['R', 'r']
QUEEN = ['Q', 'q']
KING = ['K', 'k']

PIECES_ALL_CASES = ['P', 'N', 'B', 'R', 'K', 'p', 'n', 'b', 'r', 'k']
PROMOTION_PIECES_WHITE_STR = ['R', 'N', 'B']
PROMOTION_PIECES_BLACK_STR = ['r', 'n', 'b']

# Соответствие фигур и юникод-символов (для отрисовки текстом, если нужно)
PIECE_TO_SYMBOL = {
    'p': '♟', 'n': '♞', 'b': '♝', 'r': '♜', 'k': '♚',
    'P': '♙', 'N': '♘', 'B': '♗', 'R': '♖', 'K': '♔'
}

# Оценка фигур для ИИ (в сантипешках)
PIECE_VALUES = {
    'P': 100, 'N': 300, 'B': 300, 'R': 500, 'Q': 900, 'K': 10000,
    'p': -100, 'n': -300, 'b': -300, 'r': -500, 'q': -900, 'k': -10000,
    EMPTY_SQUARE: 0
}
# Оценка для фигур в руке (может быть чуть меньше)
HAND_PIECE_VALUES = {
    k.upper(): abs(v) * 0.9 for k, v in PIECE_VALUES.items() if k != EMPTY_SQUARE and k != 'K' and k != 'k' # Kings are never in hand
}

# --- Move Directions ---
KNIGHT_MOVES = [(1, 2), (1, -2), (-1, 2), (-1, -2),
                (2, 1), (2, -1), (-2, 1), (-2, -1)]
DIAGONAL_MOVES = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
STRAIGHT_MOVES = [(1, 0), (-1, 0), (0, 1), (0, -1)]
KING_MOVES = DIAGONAL_MOVES + STRAIGHT_MOVES


# --- Primitive Drawing Functions (OBSOLETE - Removed) ---
# def draw_pawn(surface, color, is_white):
#     """Рисует пешку (простой дизайн)."""
#     ...
#
# def draw_knight(surface, color, is_white):
#     """Рисует коня (более стилизованный)."""
#     ...
#
# def draw_bishop(surface, color, is_white):
#     """Рисует слона (более округлый)."""
#     ...
#
# def draw_rook(surface, color, is_white):
#     """Рисует ладью (классический вид)."""
#     ...
#
# def draw_king(surface, color, is_white):
#     """Рисует короля (простой дизайн с крестом)."""
#     ...