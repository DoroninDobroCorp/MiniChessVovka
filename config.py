# -*- coding: utf-8 -*-

# --- Game Constants ---
BOARD_SIZE = 6
SQUARE_SIZE = 100  # Увеличенный размер клетки для красоты
TOTAL_WIDTH = BOARD_SIZE * SQUARE_SIZE  # Общая ширина доски
SIDE_PANEL_WIDTH = 300  # Боковая панель
INFO_HEIGHT = 0  # Не используется (всё в боковой панели)
WIDTH = TOTAL_WIDTH + SIDE_PANEL_WIDTH  # Общая ширина окна
HEIGHT = TOTAL_WIDTH  # Высота = доска
FPS = 30
AI_MOVE_DELAY = 1.5  # Задержка перед ходом ИИ (секунды) — чтобы видеть ходы

# --- Colors ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
LIGHT_SQUARE = (240, 217, 181)
DARK_SQUARE = (181, 136, 99)
INFO_BG_COLOR = (38, 36, 33)
INFO_TEXT_COLOR = WHITE
BUTTON_COLOR = (70, 70, 70)
BUTTON_HOVER_COLOR = (100, 100, 100)
BUTTON_TEXT_COLOR = WHITE

# --- UI Colors ---
BOARD_COLORS = {
    'light': (240, 217, 181),
    'dark': (181, 136, 99)
}
HIGHLIGHT_COLORS = {
    'selected': (100, 150, 255, 150),
    'legal_move': (0, 0, 0, 60),
    'check': (235, 50, 50, 160),
    'previous_move': (255, 255, 0, 80),
    'move_origin': (200, 200, 0, 60),
    'undo': (180, 80, 40),
    'toggle_ai': (70, 70, 80),
    'toggle_ai_active': (46, 139, 87),
    'trainer': (0, 150, 150),
    'hint': (130, 80, 220),
    'hint_active': (170, 120, 255),
    'hint_from': (80, 200, 255, 140),
    'hint_to': (80, 255, 140, 160),
    'hint_arrow': (80, 200, 255, 200),
    'button': (80, 140, 200),
    'button_hover': (100, 160, 220),
    'button_active': (120, 180, 240),
    'button_text': (255, 255, 255),
    'undo_hover': (170, 140, 240),
    'undo_active': (190, 160, 255),
    'toggle_ai_hover': (140, 220, 170)
}

# Прозрачный цвет для возможных ходов
POSSIBLE_MOVE_COLOR = (80, 150, 105, 170)  # Более темный зеленый для возможных ходов

# Позиционные бонусы/штрафы (для AI)
CENTER_SQUARES = [(2, 2), (2, 3), (3, 2), (3, 3)] # c4, d4, c3, d3
CENTER_BONUS = 25 # Увеличен бонус за контроль центра
DEVELOPMENT_PENALTY = -10 # Штраф для B/N на стартовых позициях после нескольких ходов? (сложно) - Not directly used in evaluate_position currently
PAWN_STRUCTURE_BONUS = 15 # Увеличен бонус за хорошие пешечные структуры
KING_SAFETY_BONUS = 30 # Увеличен бонус за безопасность короля
MOBILITY_BONUS = 8  # Бонус за мобильность (количество ходов)
ATTACK_BONUS = 15  # Бонус за атаку/угрозу - Not directly used in evaluate_position currently

# Фаза игры влияет на оценку позиции (для AI)
OPENING_PHASE = 12  # Начальное число фигур (не включая пешки) на доске
ENDGAME_PHASE = 4   # Переход в эндшпиль

# Цвета фона для фигур (используется в примитивах рисования в pieces.py)
PIECE_BG_COLORS = {
    'K': (220, 220, 255), 'R': (220, 255, 220),
    'B': (255, 255, 220), 'N': (220, 255, 255), 'P': (255, 220, 255),
    'k': (100, 100, 180), 'r': (100, 180, 100),
    'b': (180, 180, 100), 'n': (100, 180, 180), 'p': (180, 100, 180)
}