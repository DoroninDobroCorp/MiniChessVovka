# -*- coding: utf-8 -*-

# --- Game Constants ---
BOARD_SIZE = 6
SQUARE_SIZE = 90  # Увеличим размер клетки для лучшей видимости
TOTAL_WIDTH = BOARD_SIZE * SQUARE_SIZE  # Общая ширина доски
SIDE_PANEL_WIDTH = 320  # Увеличим боковую панель
INFO_HEIGHT = 200  # Увеличим высоту информационной панели
WIDTH = TOTAL_WIDTH + SIDE_PANEL_WIDTH  # Общая ширина окна
HEIGHT = TOTAL_WIDTH + INFO_HEIGHT  # Общая высота окна включая информационную панель
FPS = 30

# --- Colors ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
LIGHT_SQUARE = (238, 238, 210)
DARK_SQUARE = (118, 150, 86)
INFO_BG_COLOR = (49, 46, 43)
INFO_TEXT_COLOR = WHITE
BUTTON_COLOR = (70, 70, 70)
BUTTON_HOVER_COLOR = (100, 100, 100)
BUTTON_TEXT_COLOR = WHITE

# --- UI Colors ---
BOARD_COLORS = {
    'light': (238, 238, 210),
    'dark': (118, 150, 86)
}
HIGHLIGHT_COLORS = {
    'selected': (100, 150, 255, 150), # Semi-transparent blue
    'legal_move': (0, 255, 0, 100), # Semi-transparent green (for dots/rings)
    'check': (255, 0, 0, 120), # Semi-transparent red
    'previous_move': (255, 255, 0, 100), # Semi-transparent yellow
    'move_origin': (200, 200, 0, 80), # Fainter yellow for origin
    'undo': (200, 100, 0), # Orange-ish for undo button
    'toggle_ai': (80, 80, 80), # Dark gray for AI toggle
    'toggle_ai_active': (50, 150, 50), # Greenish for active AI toggle
    'trainer': (0, 150, 150), # Teal color for trainer button
    'hint': (255, 150, 210, 200),        # Розовый для подсказки
    'hint_hover': (220, 150, 120),       # Цвет при наведении на кнопку подсказки
    'hint_active': (255, 190, 160),      # Цвет при нажатии на кнопку подсказки
    'button': (80, 140, 200),            # Цвет для кнопок
    'button_hover': (100, 160, 220),     # Цвет при наведении на кнопку
    'button_active': (120, 180, 240),    # Цвет при нажатии на кнопку
    'button_text': (255, 255, 255),      # Цвет текста кнопок
    'undo_hover': (170, 140, 240),       # Цвет при наведении на кнопку отмены
    'undo_active': (190, 160, 255),      # Цвет при нажатии на кнопку отмены
    'toggle_ai_hover': (140, 220, 170)  # Цвет при наведении на кнопку переключения ИИ
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