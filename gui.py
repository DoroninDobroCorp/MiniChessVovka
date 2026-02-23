# -*- coding: utf-8 -*-
import pygame
import sys
import os
import math
from config import *
from pieces import (PIECE_BG_COLORS, PIECES_ALL_CASES, EMPTY_SQUARE,
                    PROMOTION_PIECES_WHITE_STR, PROMOTION_PIECES_BLACK_STR, PIECE_TO_SYMBOL)
from utils import get_piece_color, piece_to_lower, piece_to_upper, coords_to_algebraic, get_opposite_color


# Global dictionary for piece images
PIECE_IMAGES = {}

# Initialize Pygame here for font loading
pygame.init()
FONT_COORD = pygame.font.SysFont('consolas', 13, bold=True)
FONT_INFO = pygame.font.SysFont('segoeui', 17)
FONT_HAND = pygame.font.SysFont('segoeui', 20)
FONT_BUTTON = pygame.font.SysFont('segoeui', 15, bold=True)
FONT_PROMOTION = pygame.font.SysFont('segoeui', 20, bold=True)
FONT_PIECE = pygame.font.SysFont('segoeui', 48, bold=True)
FONT_TITLE = pygame.font.SysFont('segoeui', 22, bold=True)
FONT_STATUS = pygame.font.SysFont('segoeui', 16, bold=True)

# --- Image Loading and Helper Functions ---

def get_screen_coords(logical_coords, board_flipped):
    """Преобразует логические координаты (row, col) в экранные пиксельные координаты (x, y) левого верхнего угла клетки, учитывая переворот доски."""
    r, f = logical_coords
    if board_flipped:
        screen_row = BOARD_SIZE - 1 - r
        screen_col = BOARD_SIZE - 1 - f
    else:
        screen_row = r
        screen_col = f
    return screen_col * SQUARE_SIZE, screen_row * SQUARE_SIZE

def resize_image(surface, target_size):
    """Resizes a Pygame surface while maintaining aspect ratio and centering."""
    original_size = surface.get_size()
    if original_size[0] == 0 or original_size[1] == 0:
        # Avoid division by zero if surface is empty
        return pygame.Surface((target_size, target_size), pygame.SRCALPHA)

    aspect_ratio = original_size[0] / original_size[1]

    if aspect_ratio > 1:
        # Wider than tall
        new_width = target_size
        new_height = int(target_size / aspect_ratio)
    else:
        # Taller than wide or square
        new_height = target_size
        new_width = int(target_size * aspect_ratio)

    # Ensure dimensions are at least 1
    new_width = max(1, new_width)
    new_height = max(1, new_height)

    try:
        scaled_surface = pygame.transform.smoothscale(surface, (new_width, new_height))
    except ValueError:
        # Fallback if smoothscale fails (e.g., surface too small)
        scaled_surface = pygame.transform.scale(surface, (new_width, new_height))

    # Center the scaled image onto a target-sized transparent surface
    result_surface = pygame.Surface((target_size, target_size), pygame.SRCALPHA)
    x_offset = (target_size - new_width) // 2
    y_offset = (target_size - new_height) // 2
    result_surface.blit(scaled_surface, (x_offset, y_offset))
    return result_surface

def invert_surface_colors(surface):
    """Creates a new surface, mapping dark pixels to light gray, preserving alpha."""
    # Ensure the input surface has per-pixel alpha for transparency handling
    src_surface = surface.convert_alpha()
    width, height = src_surface.get_size()
    inverted_surface = pygame.Surface((width, height), pygame.SRCALPHA)

    TARGET_GRAY = (200, 200, 200) # Target color for the main body of white pieces
    EDGE_GRAY = (150, 150, 150)   # Target color for anti-aliased edges
    DARK_THRESHOLD = 150          # Pixels darker than this (sum of RGB) are considered part of the piece
    ALPHA_THRESHOLD = 128         # Pixels less transparent than this are considered

    try:
        src_surface.lock()
        inverted_surface.lock()
        for x in range(width):
            for y in range(height):
                r, g, b, a = src_surface.get_at((x, y))

                if a >= ALPHA_THRESHOLD: # Consider only sufficiently opaque pixels
                    brightness = r + g + b
                    if brightness < DARK_THRESHOLD:
                        # Dark pixel -> map to target light gray
                        inverted_surface.set_at((x, y), (*TARGET_GRAY, a))
                    else:
                        # Lighter pixel (likely anti-aliasing) -> map to edge gray
                        # Or you could try other mappings, e.g., scaling the original gray
                        inverted_surface.set_at((x, y), (*EDGE_GRAY, a))
                # else: pixel is mostly transparent, leave it transparent in inverted_surface

    finally:
        src_surface.unlock()
        inverted_surface.unlock()
    return inverted_surface

def load_images(image_dir="assets/sprites", target_piece_size=int(SQUARE_SIZE * 0.9)):
    """Loads piece images from a directory, resizes, creates white versions by inverting.
       Uses specific filenames provided by user.
    """
    print(f"Loading piece images from '{image_dir}'...")
    PIECE_IMAGES.clear()
    found_files = 0

    # Map internal piece type to user filenames and characters
    piece_file_map = {
        'pawn':   ('pawn.png', 'p', 'P'),
        'knight': ('horse.png', 'n', 'N'),
        'bishop': ('bishop.png', 'b', 'B'),
        'rook':   ('rookie.png', 'r', 'R'),
        # 'queen':  ('queen.png', 'q', 'Q'), # <<< УБРАНО, так как queen.png отсутствует
        'king':   ('king.png', 'k', 'K')
    }

    for piece_type, (filename, black_piece_char, white_piece_char) in piece_file_map.items():
        filepath = os.path.join(image_dir, filename)

        if os.path.exists(filepath):
            original_image = None # Initialize
            try:
                print(f"  Loading: {filepath}")
                if filename.lower().endswith('.png'):
                    original_image = pygame.image.load(filepath).convert_alpha()
                elif filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg'):
                    # original_image = pygame.image.load(filepath).convert()
                    original_image = pygame.image.load(filepath).convert_alpha() # Use convert_alpha() for JPG too
                else:
                    print(f"!! Warning: Unsupported image format for {filename}. Skipping.")
                    continue

                if original_image is None:
                     print(f"!! Error: Failed to load image {filepath} (returned None).")
                     continue

                # Resize black piece image
                resized_black_image = resize_image(original_image, SQUARE_SIZE)
                PIECE_IMAGES[black_piece_char] = resized_black_image
                print(f"    -> Stored as '{black_piece_char}'")

                # Create and store white piece image by converting colors
                converted_white_image = invert_surface_colors(resized_black_image)
                PIECE_IMAGES[white_piece_char] = converted_white_image
                print(f"    -> Converted and stored as '{white_piece_char}'")
                found_files += 1

            except Exception as e:
                print(f"!! Error processing image {filepath}: {e}")
        else:
            print(f"!! Warning: Image file not found: {filepath}")

    if found_files > 0:
        print(f"Successfully loaded and processed {found_files * 2} piece images.")
        return True
    else:
        print("!! Error: No piece image files found or processed. Ensure they are in the correct directory and format.")
        return False

# --- Primitive Drawing Functions (OBSOLETE - Keep for reference?) ---
# Remove imports from pieces.py for draw_ functions
# from pieces import draw_pawn, draw_knight, draw_bishop, draw_rook, draw_king

# --- Drawing Functions ---

def draw_board(screen, board_flipped):
    """Draws the checkerboard pattern with subtle coordinate labels."""
    for r in range(BOARD_SIZE):
        for f in range(BOARD_SIZE):
            is_light = (r + f) % 2 == 0
            color = BOARD_COLORS['light'] if is_light else BOARD_COLORS['dark']
            x, y = get_screen_coords((r, f), board_flipped)
            pygame.draw.rect(screen, color, pygame.Rect(x, y, SQUARE_SIZE, SQUARE_SIZE))

    # Draw coordinates on edges only
    for i in range(BOARD_SIZE):
        # Rank labels (left edge)
        r = i
        f = 0
        x, y = get_screen_coords((r, f), board_flipped)
        rank_label = str(BOARD_SIZE - r) if not board_flipped else str(r + 1)
        is_light = (r + f) % 2 == 0
        label_color = BOARD_COLORS['dark'] if is_light else BOARD_COLORS['light']
        coord_text = FONT_COORD.render(rank_label, True, label_color)
        screen.blit(coord_text, (x + 3, y + 3))

        # File labels (bottom edge)
        r = BOARD_SIZE - 1
        f = i
        x, y = get_screen_coords((r, f), board_flipped)
        file_label = chr(ord('a') + f) if not board_flipped else chr(ord('a') + BOARD_SIZE - 1 - f)
        is_light = (r + f) % 2 == 0
        label_color = BOARD_COLORS['dark'] if is_light else BOARD_COLORS['light']
        coord_text = FONT_COORD.render(file_label, True, label_color)
        screen.blit(coord_text, (x + SQUARE_SIZE - 12, y + SQUARE_SIZE - 16))

def draw_pieces(screen, board, board_flipped):
    """Draws pieces onto the board surface."""
    for r in range(BOARD_SIZE):
        for f in range(BOARD_SIZE):
            piece = board[r][f]
            if piece != EMPTY_SQUARE:
                x, y = get_screen_coords((r, f), board_flipped)
                img = PIECE_IMAGES.get(piece)
                if img:
                    screen.blit(img, (x, y))
                else:
                    # Fallback text rendering
                    piece_color = WHITE if get_piece_color(piece) == 'w' else BLACK
                    text_surf = FONT_PIECE.render(PIECE_TO_SYMBOL.get(piece, piece), True, piece_color)
                    text_rect = text_surf.get_rect(center=(x + SQUARE_SIZE // 2, y + SQUARE_SIZE // 2))
                    screen.blit(text_surf, text_rect)

def highlight_square(screen, square, color, board_flipped):
    """Draws a highlight effect on a given square."""
    x, y = get_screen_coords(square, board_flipped)
    highlight_surface = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
    highlight_surface.fill(color)
    screen.blit(highlight_surface, (x, y))

def draw_highlights(screen, gamestate, board_flipped):
    """Draws highlights for selected square, last move, check, legal moves."""
    # 1. Previous Move Highlight
    if gamestate.last_move:
        if gamestate.last_move[0] == 'drop':
            r, f = gamestate.last_move[2]
            highlight_square(screen, (r,f), HIGHLIGHT_COLORS['previous_move'], board_flipped)
        else:
            r1, f1 = gamestate.last_move[0]
            r2, f2 = gamestate.last_move[1]
            highlight_square(screen, (r1,f1), HIGHLIGHT_COLORS['move_origin'], board_flipped)
            highlight_square(screen, (r2,f2), HIGHLIGHT_COLORS['previous_move'], board_flipped)

    # 2. Selected Square Highlight
    if gamestate.selected_square:
        highlight_square(screen, gamestate.selected_square, HIGHLIGHT_COLORS['selected'], board_flipped)

    # 3. Legal Move Dots/Circles
    if gamestate.highlighted_moves:
        for move in gamestate.highlighted_moves:
            target_r, target_f = -1, -1
            is_capture = False
            is_drop = False

            if move[0] == 'drop':
                if gamestate.selected_drop_piece and move[1].upper() == gamestate.selected_drop_piece:
                     target_r, target_f = move[2]
                     is_drop = True
                else: continue
            elif gamestate.selected_square and move[0] == gamestate.selected_square:
                 target_r, target_f = move[1]
                 if gamestate.board[target_r][target_f] != EMPTY_SQUARE:
                     is_capture = True
            else: continue

            target_x, target_y = get_screen_coords((target_r, target_f), board_flipped)
            center_x = target_x + SQUARE_SIZE // 2
            center_y = target_y + SQUARE_SIZE // 2

            if is_capture or is_drop:
                 radius = SQUARE_SIZE // 2 - 3
                 s = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
                 pygame.draw.circle(s, (0, 0, 0, 40), (SQUARE_SIZE//2, SQUARE_SIZE//2), radius, 5)
                 screen.blit(s, (target_x, target_y))
            else:
                radius = SQUARE_SIZE // 6
                s = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
                pygame.draw.circle(s, HIGHLIGHT_COLORS['legal_move'], (SQUARE_SIZE//2, SQUARE_SIZE//2), radius)
                screen.blit(s, (target_x, target_y))

    # 4. Check Highlight
    player_to_check = gamestate.current_turn if not board_flipped else get_opposite_color(gamestate.current_turn)

    if gamestate.is_in_check(player_to_check):
        king_pos = gamestate.king_pos.get(player_to_check)
        if king_pos:
            highlight_square(screen, king_pos, HIGHLIGHT_COLORS['check'], board_flipped)


def draw_hint(screen, hint_move, board_flipped):
    """Draws a hint arrow showing the best move."""
    if not hint_move:
        return

    if hint_move[0] == 'drop':
        # For drop moves, highlight the target square
        target_r, target_f = hint_move[2]
        tx, ty = get_screen_coords((target_r, target_f), board_flipped)
        s = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
        s.fill(HIGHLIGHT_COLORS['hint_to'])
        screen.blit(s, (tx, ty))
        return

    # Regular move: draw arrow from source to target
    from_sq = hint_move[0]
    to_sq = hint_move[1]

    fx, fy = get_screen_coords(from_sq, board_flipped)
    tx, ty = get_screen_coords(to_sq, board_flipped)

    # Highlight squares
    s = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
    s.fill(HIGHLIGHT_COLORS['hint_from'])
    screen.blit(s, (fx, fy))
    s2 = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
    s2.fill(HIGHLIGHT_COLORS['hint_to'])
    screen.blit(s2, (tx, ty))

    # Draw arrow
    start_cx = fx + SQUARE_SIZE // 2
    start_cy = fy + SQUARE_SIZE // 2
    end_cx = tx + SQUARE_SIZE // 2
    end_cy = ty + SQUARE_SIZE // 2

    dx = end_cx - start_cx
    dy = end_cy - start_cy
    dist = math.sqrt(dx*dx + dy*dy)
    if dist < 1:
        return

    # Shorten arrow to not overlap piece centers
    shorten = SQUARE_SIZE * 0.3
    ux, uy = dx / dist, dy / dist
    sx = start_cx + ux * shorten
    sy = start_cy + uy * shorten
    ex = end_cx - ux * shorten
    ey = end_cy - uy * shorten

    arrow_color = (80, 200, 255)
    line_width = 6

    # Draw line
    pygame.draw.line(screen, arrow_color, (int(sx), int(sy)), (int(ex), int(ey)), line_width)

    # Draw arrowhead
    head_len = 14
    angle = math.atan2(dy, dx)
    left_x = ex - head_len * math.cos(angle - 0.5)
    left_y = ey - head_len * math.sin(angle - 0.5)
    right_x = ex - head_len * math.cos(angle + 0.5)
    right_y = ey - head_len * math.sin(angle + 0.5)
    pygame.draw.polygon(screen, arrow_color, [
        (int(ex), int(ey)),
        (int(left_x), int(left_y)),
        (int(right_x), int(right_y))
    ])


# --- Side Panel and Info Panel ---

def _draw_button(screen, rect, text, bg_color, text_color=WHITE, border_color=None):
    """Helper to draw a styled button."""
    pygame.draw.rect(screen, bg_color, rect, border_radius=6)
    if border_color:
        pygame.draw.rect(screen, border_color, rect, 1, border_radius=6)
    text_surf = FONT_BUTTON.render(text, True, text_color)
    screen.blit(text_surf, text_surf.get_rect(center=rect.center))


def draw_side_panel(screen, gamestate, show_hint=False, hint_move=None, board_flipped=False):
    """Draws the side panel with captured pieces, controls, status."""
    panel_rect = pygame.Rect(TOTAL_WIDTH, 0, SIDE_PANEL_WIDTH, HEIGHT)
    pygame.draw.rect(screen, INFO_BG_COLOR, panel_rect)

    # Subtle left border
    pygame.draw.line(screen, (60, 58, 55), (TOTAL_WIDTH, 0), (TOTAL_WIDTH, HEIGHT), 2)

    ui_elements = {
        'buttons': {},
        'hand_pieces': {'w': {}, 'b': {}}
    }
    y = 14
    px = TOTAL_WIDTH + 14  # left padding
    pw = SIDE_PANEL_WIDTH - 28  # usable width

    # ─── Title ───
    title = FONT_TITLE.render("Mini Crazyhouse 6×6", True, (220, 220, 220))
    screen.blit(title, (TOTAL_WIDTH + (SIDE_PANEL_WIDTH - title.get_width()) // 2, y))
    y += title.get_height() + 12

    # ─── Turn indicator ───
    is_white = gamestate.current_turn == 'w'
    turn_str = "● Ход белых" if is_white else "● Ход чёрных"
    dot_color = (240, 240, 240) if is_white else (80, 80, 80)
    turn_rect = pygame.Rect(px, y, pw, 30)
    pygame.draw.rect(screen, (52, 50, 48), turn_rect, border_radius=5)
    turn_surf = FONT_INFO.render(turn_str, True, (200, 200, 200))
    screen.blit(turn_surf, turn_surf.get_rect(center=turn_rect.center))
    # Small color dot
    pygame.draw.circle(screen, dot_color, (px + 16, y + 15), 5)
    y += 38

    # ─── Hands (captured pieces) ───
    piece_size_hand = 32
    hand_pad = 4

    for color in ['w', 'b']:
        label = "Рука белых" if color == 'w' else "Рука чёрных"
        label_surf = FONT_STATUS.render(label, True, (160, 160, 160))
        screen.blit(label_surf, (px, y))
        y += label_surf.get_height() + 4

        current_x = px
        row_start_y = y
        if color not in ui_elements['hand_pieces']:
            ui_elements['hand_pieces'][color] = {}

        hand_sorted = sorted(gamestate.hands[color].items())
        has_pieces = False

        for piece_type, total_count in hand_sorted:
            if total_count <= 0:
                continue
            has_pieces = True
            piece_char = piece_to_upper(piece_type) if color == 'w' else piece_to_lower(piece_type)
            piece_img = PIECE_IMAGES.get(piece_char)
            if not piece_img:
                continue
            scaled_img = pygame.transform.smoothscale(piece_img, (piece_size_hand, piece_size_hand))

            if piece_type not in ui_elements['hand_pieces'][color]:
                ui_elements['hand_pieces'][color][piece_type] = []

            for _ in range(total_count):
                if current_x + piece_size_hand > TOTAL_WIDTH + SIDE_PANEL_WIDTH - 14:
                    y += piece_size_hand + hand_pad
                    current_x = px

                piece_rect = pygame.Rect(current_x, y, piece_size_hand, piece_size_hand)
                ui_elements['hand_pieces'][color][piece_type].append(piece_rect)

                if gamestate.current_turn == color and gamestate.selected_drop_piece == piece_type:
                    sel_rect = piece_rect.inflate(4, 4)
                    pygame.draw.rect(screen, HIGHLIGHT_COLORS['selected'], sel_rect, border_radius=3)

                screen.blit(scaled_img, piece_rect.topleft)
                current_x += piece_size_hand + hand_pad

        # Advance y after drawing hand pieces
        max_y = row_start_y
        for rects in ui_elements['hand_pieces'][color].values():
            for rect in rects:
                max_y = max(max_y, rect.bottom)
        y = (max_y + 10) if has_pieces else (y + 8)

    # ─── Separator ───
    pygame.draw.line(screen, (70, 68, 65), (px, y), (px + pw, y), 1)
    y += 10

    # ─── Buttons ───
    btn_h = 34
    btn_w = (pw - 8) // 2

    # Row 1: Undo + New Game
    undo_rect = pygame.Rect(px, y, btn_w, btn_h)
    _draw_button(screen, undo_rect, "⟲ Отменить", HIGHLIGHT_COLORS['undo'])
    ui_elements['buttons']['undo_button'] = undo_rect

    if gamestate.checkmate or gamestate.stalemate:
        ng_rect = pygame.Rect(px + btn_w + 8, y, btn_w, btn_h)
        _draw_button(screen, ng_rect, "Новая игра", (30, 130, 60))
        ui_elements['buttons']['new_game_button'] = ng_rect
    else:
        ng_rect = pygame.Rect(px + btn_w + 8, y, btn_w, btn_h)
        _draw_button(screen, ng_rect, "Новая игра", (60, 60, 58))
        ui_elements['buttons']['new_game_button'] = ng_rect
    y += btn_h + 8

    # Row 2: AI toggles
    ai_w_active = gamestate.white_ai_enabled
    ai_b_active = gamestate.black_ai_enabled
    tw_rect = pygame.Rect(px, y, btn_w, btn_h)
    tb_rect = pygame.Rect(px + btn_w + 8, y, btn_w, btn_h)
    _draw_button(screen, tw_rect,
                 f"ИИ Б: {'ВКЛ' if ai_w_active else 'выкл'}",
                 HIGHLIGHT_COLORS['toggle_ai_active'] if ai_w_active else HIGHLIGHT_COLORS['toggle_ai'])
    _draw_button(screen, tb_rect,
                 f"ИИ Ч: {'ВКЛ' if ai_b_active else 'выкл'}",
                 HIGHLIGHT_COLORS['toggle_ai_active'] if ai_b_active else HIGHLIGHT_COLORS['toggle_ai'])
    ui_elements['buttons']['toggle_white_ai'] = tw_rect
    ui_elements['buttons']['toggle_black_ai'] = tb_rect
    y += btn_h + 8

    # Row 3: Hint toggle (full width)
    hint_rect = pygame.Rect(px, y, pw, btn_h)
    hint_bg = HIGHLIGHT_COLORS['hint_active'] if show_hint else HIGHLIGHT_COLORS['hint']
    hint_label = "💡 Подсказка: ВКЛ" if show_hint else "💡 Подсказка: выкл"
    _draw_button(screen, hint_rect, hint_label, hint_bg)
    ui_elements['buttons']['toggle_hint'] = hint_rect
    y += btn_h + 6

    # Row 4: Flip board toggle (full width)
    flip_rect = pygame.Rect(px, y, pw, btn_h)
    flip_bg = (80, 120, 80) if board_flipped else (60, 60, 58)
    flip_label = "🔄 Доска: перевёрнута" if board_flipped else "🔄 Перевернуть доску"
    _draw_button(screen, flip_rect, flip_label, flip_bg)
    ui_elements['buttons']['toggle_flip'] = flip_rect
    y += btn_h + 6

    # Hint status text
    if show_hint and hint_move:
        from utils import format_move_for_print
        hint_text = f"Лучший ход: {format_move_for_print(hint_move)}"
        hint_surf = FONT_STATUS.render(hint_text, True, (130, 210, 255))
        screen.blit(hint_surf, (px + 4, y))
        y += hint_surf.get_height() + 4
    elif show_hint:
        thinking = FONT_STATUS.render("Считаю…", True, (160, 160, 160))
        screen.blit(thinking, (px + 4, y))
        y += thinking.get_height() + 4

    y += 4

    # ─── Game Status ───
    status_text = ""
    status_color = WHITE
    if gamestate.checkmate:
        winner = "Чёрные" if gamestate.current_turn == 'w' else "Белые"
        status_text = f"♚ Мат! {winner} победили!"
        status_color = (255, 80, 80)
    elif gamestate.stalemate:
        status_text = "½ Пат — ничья"
        status_color = (220, 200, 80)
    elif gamestate.needs_promotion_choice:
        player = "Белые" if gamestate.current_turn == 'w' else "Чёрные"
        status_text = f"↑ {player}: выберите фигуру"
        status_color = (80, 210, 255)

    if status_text:
        status_rect = pygame.Rect(px, y, pw, 36)
        pygame.draw.rect(screen, (50, 48, 46), status_rect, border_radius=5)
        status_surf = FONT_STATUS.render(status_text, True, status_color)
        screen.blit(status_surf, status_surf.get_rect(center=status_rect.center))
        y += status_rect.height + 8

    return ui_elements


def draw_info_panel(screen, gamestate):
    """Draws the bottom info panel (currently integrated into side panel)."""
    # This function is kept separate in case the layout changes later.
    # Currently, status info is shown in draw_side_panel.
    pass


def draw_promotion_choice(screen, gamestate):
    """Draws the promotion selection interface."""
    if not gamestate.needs_promotion_choice or not gamestate.promotion_square:
        return [] # Return empty list if no choice needed

    # Determine color of the player promoting
    promoting_color = get_opposite_color(gamestate.current_turn)
    promotion_pieces = PROMOTION_PIECES_WHITE_STR if promoting_color == 'w' else PROMOTION_PIECES_BLACK_STR
    # Queen is not allowed by rules, so available pieces are R, N, B

    # Overlay to dim the background
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))

    # Box dimensions and position (centered?)
    num_choices = len(promotion_pieces)
    box_width = SQUARE_SIZE * num_choices
    box_height = SQUARE_SIZE
    box_x = (WIDTH - box_width) // 2
    box_y = (HEIGHT - box_height) // 2

    # Draw the container box
    pygame.draw.rect(screen, (50, 50, 50), (box_x - 10, box_y - 10, box_width + 20, box_height + 20), border_radius=5)
    pygame.draw.rect(screen, WHITE, (box_x - 10, box_y - 10, box_width + 20, box_height + 20), 2, border_radius=5)

    promotion_buttons = {} # Store rects for click detection

    for i, piece_char_upper in enumerate(promotion_pieces):
        piece_char = piece_char_upper if promoting_color == 'w' else piece_to_lower(piece_char_upper)
        button_rect = pygame.Rect(box_x + i * SQUARE_SIZE, box_y, SQUARE_SIZE, SQUARE_SIZE)

        # Draw button background
        pygame.draw.rect(screen, BUTTON_COLOR, button_rect)
        pygame.draw.rect(screen, WHITE, button_rect, 1) # Outline

        # Draw piece image inside button
        img = PIECE_IMAGES.get(piece_char)
        if img:
            img_rect = img.get_rect(center=button_rect.center)
            screen.blit(img, img_rect)
        else: # Fallback text
            text_surf = FONT_PIECE.render(piece_char, True, WHITE)
            text_rect = text_surf.get_rect(center=button_rect.center)
            screen.blit(text_surf, text_rect)

        promotion_buttons[piece_char] = button_rect # Store rect with the actual piece char ('R' or 'r')

    return promotion_buttons


def get_clicked_hand_piece(pos, gamestate, hand_piece_rects):
    """Checks if a click occurred on a piece in the side panel hand.
       Uses the pre-calculated rects from draw_side_panel.
       Returns the UPPERCASE piece type if clicked, else None."""
    # This function now relies on hand_piece_rects passed from main loop

    if pos[0] < TOTAL_WIDTH: return None # Click was on board

    current_player_color = gamestate.current_turn
    if current_player_color not in hand_piece_rects: return None

    player_hand_rects = hand_piece_rects[current_player_color]

    for piece_type, rect_list in player_hand_rects.items():
        for rect in rect_list:
            if rect.collidepoint(pos):
                return piece_type.upper() # Return the UPPERCASE type (matching GameState hand keys)

    return None # No hand piece clicked


def handle_promotion_choice(mouse_pos, promotion_buttons):
     """Checks if a promotion button was clicked. Returns chosen piece char or None."""
     for piece_char, rect in promotion_buttons.items():
         if rect.collidepoint(mouse_pos):
             return piece_char
     return None


# --- Main GUI Drawing Function ---

def draw_game_state(screen, gamestate, board_flipped=False, show_hint=False, hint_move=None):
    """Main drawing function called each frame."""
    # 1. Draw Board and Pieces
    draw_board(screen, board_flipped)

    # 2. Draw Hint (before pieces so arrow goes under them)
    if show_hint and hint_move:
        draw_hint(screen, hint_move, board_flipped)

    draw_pieces(screen, gamestate.board, board_flipped)

    # 3. Draw Highlights (selected, legal moves, check, last move)
    draw_highlights(screen, gamestate, board_flipped)

    # 4. Draw Side Panel (captured pieces, controls, status)
    ui_elements = draw_side_panel(screen, gamestate, show_hint=show_hint, hint_move=hint_move, board_flipped=board_flipped)

    # 5. Draw Info Panel (if used)
    draw_info_panel(screen, gamestate)

    # 6. Draw Promotion Choice Overlay (if needed)
    promotion_buttons = draw_promotion_choice(screen, gamestate)
    if promotion_buttons:
        if 'promotion_buttons' not in ui_elements:
             ui_elements['promotion_buttons'] = {}
        ui_elements['promotion_buttons'] = promotion_buttons

    return ui_elements