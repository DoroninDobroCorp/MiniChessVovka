# -*- coding: utf-8 -*-
import pygame
import sys
import os # Added for path joining
from config import * # Import all constants and colors
from pieces import (PIECE_BG_COLORS, PIECES_ALL_CASES, EMPTY_SQUARE,
                    PROMOTION_PIECES_WHITE_STR, PROMOTION_PIECES_BLACK_STR, PIECE_TO_SYMBOL)
from utils import get_piece_color, piece_to_lower, piece_to_upper, coords_to_algebraic, get_opposite_color
# Need GameState for type hints and accessing state, but avoid circular import if possible
# If methods here need complex state logic, it might belong in GameState or main.py
# from gamestate import GameState # Potential circular import issue


# Global dictionary for piece images
PIECE_IMAGES = {}

# Initialize Pygame here for font loading
pygame.init()
FONT_INFO = pygame.font.SysFont('consolas', 18)
FONT_HAND = pygame.font.SysFont('arial', 22)
FONT_BUTTON = pygame.font.SysFont('arial', 16)
FONT_PROMOTION = pygame.font.SysFont('arial', 20, bold=True)
FONT_PIECE = pygame.font.SysFont('arial', 46, bold=True) # Увеличенный шрифт для фигур

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

def load_images(image_dir=".", target_piece_size=int(SQUARE_SIZE * 0.9)):
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
                # --- DEBUG BISHOP --- 
                if black_piece_char == 'b':
                    print(f"    [DEBUG] Bishop 'b' added to PIECE_IMAGES: {isinstance(PIECE_IMAGES.get('b'), pygame.Surface)}")
                # --- END DEBUG ---

                # Create and store white piece image by converting colors
                converted_white_image = invert_surface_colors(resized_black_image) # Use the new function name
                PIECE_IMAGES[white_piece_char] = converted_white_image
                print(f"    -> Converted and stored as '{white_piece_char}'")
                # --- DEBUG BISHOP --- 
                if white_piece_char == 'B':
                    print(f"    [DEBUG] Bishop 'B' added to PIECE_IMAGES: {isinstance(PIECE_IMAGES.get('B'), pygame.Surface)}")
                # --- END DEBUG ---
                found_files += 1

            except Exception as e:
                print(f"!! Error processing image {filepath}: {e}")
                # --- DEBUG BISHOP --- 
                if black_piece_char == 'b': # Also print error if bishop fails
                    print(f"    [DEBUG] Error specifically during bishop processing.")
                # --- END DEBUG ---
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
    """Draws the checkerboard pattern."""
    for r in range(BOARD_SIZE):
        for f in range(BOARD_SIZE):
            color = BOARD_COLORS['light'] if (r + f) % 2 == 0 else BOARD_COLORS['dark']
            x, y = get_screen_coords((r, f), board_flipped)
            pygame.draw.rect(screen, color, pygame.Rect(x, y, SQUARE_SIZE, SQUARE_SIZE))
            # Draw coordinates
            rank_label = str(BOARD_SIZE - r) if not board_flipped else str(r + 1)
            file_label = chr(ord('a') + f) if not board_flipped else chr(ord('a') + BOARD_SIZE - 1 - f)
            label_color = BOARD_COLORS['dark'] if (r+f)%2==0 else BOARD_COLORS['light']
            coord_text = FONT_INFO.render(rank_label, True, label_color)
            screen.blit(coord_text, (x + 2, y + 2))
            coord_text = FONT_INFO.render(file_label, True, label_color)
            screen.blit(coord_text, (x + SQUARE_SIZE - 12, y + SQUARE_SIZE - 18))

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
                else: continue # Only show drops for the selected piece
            elif gamestate.selected_square and move[0] == gamestate.selected_square:
                 target_r, target_f = move[1]
                 # Check if the target square has an opponent piece
                 if gamestate.board[target_r][target_f] != EMPTY_SQUARE:
                     is_capture = True
            else: continue # Only show moves for the selected piece

            target_x, target_y = get_screen_coords((target_r, target_f), board_flipped)

            center_x = target_x + SQUARE_SIZE // 2
            center_y = target_y + SQUARE_SIZE // 2

            if is_capture or is_drop: # Draw circle for captures/drops
                 radius = SQUARE_SIZE // 2 - 4 # Slightly smaller radius
                 pygame.draw.circle(screen, HIGHLIGHT_COLORS['legal_move'], (center_x, center_y), radius, 4) # Draw hollow circle
            else: # Draw dot for non-captures
                radius = SQUARE_SIZE // 8
                pygame.draw.circle(screen, HIGHLIGHT_COLORS['legal_move'], (center_x, center_y), radius)

    # 4. Check Highlight
    player_to_check = gamestate.current_turn if not board_flipped else get_opposite_color(gamestate.current_turn)

    if gamestate.is_in_check(player_to_check):
        king_char = 'K' if player_to_check == 'w' else 'k'
        king_pos = gamestate.king_pos.get(player_to_check)
        if king_pos:
            highlight_square(screen, king_pos, HIGHLIGHT_COLORS['check'], board_flipped)


# --- Side Panel and Info Panel ---

def draw_side_panel(screen, gamestate):
    """Draws the side panel with captured pieces, controls, status.
       Returns a dict containing button rects and hand piece rects.
    """
    panel_rect = pygame.Rect(TOTAL_WIDTH, 0, SIDE_PANEL_WIDTH, HEIGHT)
    pygame.draw.rect(screen, INFO_BG_COLOR, panel_rect)

    # buttons = {} # To return button rects for click detection
    # Initialize dict to hold all UI element rects
    ui_elements = {
        'buttons': {},
        'hand_pieces': {'w': {}, 'b': {}} # {'w': {'P': [Rect, Rect], 'N': [Rect]}, ...}
    }
    y_offset = 10

    # Title
    title_font = pygame.font.SysFont('arial', 20, bold=True)
    title = title_font.render("Мини Крейзи Хаус", True, WHITE)
    screen.blit(title, (TOTAL_WIDTH + (SIDE_PANEL_WIDTH - title.get_width()) // 2, y_offset))
    y_offset += title.get_height() + 15

    # Current Turn Indicator
    player_color_str = "Белые" if gamestate.current_turn == 'w' else "Черные"
    turn_text = FONT_INFO.render(f"Ход: {player_color_str}", True, WHITE)
    turn_rect = pygame.Rect(TOTAL_WIDTH + 10, y_offset, SIDE_PANEL_WIDTH - 20, 30)
    turn_bg_col = (60, 60, 60)
    pygame.draw.rect(screen, turn_bg_col, turn_rect, border_radius=3)
    pygame.draw.rect(screen, WHITE, turn_rect, 1) # Outline
    screen.blit(turn_text, turn_text.get_rect(center=turn_rect.center))
    y_offset += turn_rect.height + 10

    # Captured Pieces / Hand
    hand_section_y_start = y_offset
    hand_title_font = FONT_BUTTON
    piece_size_hand = 30
    max_width_hand = SIDE_PANEL_WIDTH - 30
    hand_padding_x = 5
    hand_padding_y = 5

    for color in ['w', 'b']:
        hand_title_text = "Рука Белых:" if color == 'w' else "Рука Черных:"
        hand_title = hand_title_font.render(hand_title_text, True, WHITE)
        screen.blit(hand_title, (TOTAL_WIDTH + 10, y_offset))
        y_offset += hand_title.get_height() + 5
        current_x = TOTAL_WIDTH + 15
        row_start_y = y_offset # Remember Y for the start of this hand's row(s)

        hand_sorted = sorted(gamestate.hands[color].items())
        if color not in ui_elements['hand_pieces']: ui_elements['hand_pieces'][color] = {}

        piece_draw_count_this_type = {} # Track how many of THIS type drawn for rect list indexing

        for piece_type, total_count in hand_sorted:
            if total_count <= 0: continue

            piece_char = piece_to_upper(piece_type) if color == 'w' else piece_to_lower(piece_type)
            piece_img = PIECE_IMAGES.get(piece_char)
            scaled_img = pygame.transform.smoothscale(piece_img, (piece_size_hand, piece_size_hand))

            if piece_type not in ui_elements['hand_pieces'][color]:
                ui_elements['hand_pieces'][color][piece_type] = []
            if piece_type not in piece_draw_count_this_type:
                 piece_draw_count_this_type[piece_type] = 0

            # Draw each piece individually up to its count
            for i in range(total_count):
                # Check if adding this piece exceeds width, wrap if necessary
                if current_x + piece_size_hand > TOTAL_WIDTH + SIDE_PANEL_WIDTH - 10: # Adjusted wrap check
                    y_offset += piece_size_hand + hand_padding_y
                    current_x = TOTAL_WIDTH + 15 # Reset x

                # Calculate exact rect for this piece instance
                piece_rect = pygame.Rect(current_x, y_offset, piece_size_hand, piece_size_hand)
                ui_elements['hand_pieces'][color][piece_type].append(piece_rect)

                # Draw background if selected (check current turn and selected piece type)
                # We only highlight the *type* of piece, not individual instances
                if gamestate.current_turn == color and gamestate.selected_drop_piece == piece_type:
                     sel_rect = piece_rect.inflate(4, 4)
                     pygame.draw.rect(screen, HIGHLIGHT_COLORS['selected'], sel_rect, border_radius=3)

                # Draw piece image
                screen.blit(scaled_img, piece_rect.topleft)

                # Draw count only on the first piece of its type in the row (optional)
                # Or maybe draw count text separately? Let's skip count text on image for now.

                current_x += piece_size_hand + hand_padding_x # Move x for next piece

            # After drawing all pieces of one type, move to next type
            # (No y_offset change here, handled by wrapping logic)

        # After drawing all pieces for this color, advance y_offset
        # Find the max y extent of the drawn pieces for this color
        max_y_this_hand = row_start_y
        for piece_type, rect_list in ui_elements['hand_pieces'][color].items():
             for rect in rect_list:
                  max_y_this_hand = max(max_y_this_hand, rect.bottom)

        if max_y_this_hand > row_start_y:
             y_offset = max_y_this_hand + 15 # Add padding after the last row of pieces
        else: # No pieces drawn for this hand
             y_offset += 15 # Add minimal padding


    # --- Controls Section ---
    controls_y_start = y_offset
    button_height = 35
    button_width = (SIDE_PANEL_WIDTH - 30) // 2
    button_padding = 10
    button_x1 = TOTAL_WIDTH + 10
    button_x2 = button_x1 + button_width + button_padding

    # -- Undo Button --
    undo_rect = pygame.Rect(button_x1, y_offset, button_width, button_height)
    pygame.draw.rect(screen, HIGHLIGHT_COLORS['undo'], undo_rect, border_radius=5)
    pygame.draw.rect(screen, WHITE, undo_rect, 1)
    undo_text = FONT_BUTTON.render("Отменить ход", True, WHITE)
    screen.blit(undo_text, undo_text.get_rect(center=undo_rect.center))
    ui_elements['buttons']['undo_button'] = undo_rect
    # y_offset += button_height + button_padding # Offset handled below row by row

    # -- New Game Button (only if game over) --
    if gamestate.checkmate or gamestate.stalemate:
        new_game_rect = pygame.Rect(button_x2, y_offset, button_width, button_height)
        pygame.draw.rect(screen, (0, 150, 50), new_game_rect, border_radius=5) # Greenish color
        pygame.draw.rect(screen, WHITE, new_game_rect, 1)
        new_game_text = FONT_BUTTON.render("Новая игра", True, WHITE)
        screen.blit(new_game_text, new_game_text.get_rect(center=new_game_rect.center))
        ui_elements['buttons']['new_game_button'] = new_game_rect
        # We can place it next to Undo, so y_offset doesn't change yet

    # -- AI Toggles -- (Moving Undo to its own row)
    y_offset += button_height + button_padding # Move down for next row of buttons
    toggle_w_rect = pygame.Rect(button_x1, y_offset, button_width, button_height)
    toggle_b_rect = pygame.Rect(button_x2, y_offset, button_width, button_height)

    ai_w_bg = HIGHLIGHT_COLORS['toggle_ai_active'] if gamestate.white_ai_enabled else HIGHLIGHT_COLORS['toggle_ai']
    pygame.draw.rect(screen, ai_w_bg, toggle_w_rect, border_radius=5)
    pygame.draw.rect(screen, WHITE, toggle_w_rect, 1)
    ai_w_text = FONT_BUTTON.render(f"ИИ Белые: {'Вкл' if gamestate.white_ai_enabled else 'Выкл'}", True, WHITE)
    screen.blit(ai_w_text, ai_w_text.get_rect(center=toggle_w_rect.center))
    ui_elements['buttons']['toggle_white_ai'] = toggle_w_rect

    ai_b_bg = HIGHLIGHT_COLORS['toggle_ai_active'] if gamestate.black_ai_enabled else HIGHLIGHT_COLORS['toggle_ai']
    pygame.draw.rect(screen, ai_b_bg, toggle_b_rect, border_radius=5)
    pygame.draw.rect(screen, WHITE, toggle_b_rect, 1)
    ai_b_text = FONT_BUTTON.render(f"ИИ Черные: {'Вкл' if gamestate.black_ai_enabled else 'Выкл'}", True, WHITE)
    screen.blit(ai_b_text, ai_b_text.get_rect(center=toggle_b_rect.center))
    ui_elements['buttons']['toggle_black_ai'] = toggle_b_rect
    y_offset += button_height + button_padding
    
    # -- Trainer Button --
    trainer_rect = pygame.Rect(button_x1, y_offset, button_width*2 + button_padding, button_height)
    pygame.draw.rect(screen, HIGHLIGHT_COLORS['trainer'], trainer_rect, border_radius=5)
    pygame.draw.rect(screen, WHITE, trainer_rect, 1)
    trainer_text = FONT_BUTTON.render("Тренажёр", True, WHITE)
    screen.blit(trainer_text, trainer_text.get_rect(center=trainer_rect.center))
    ui_elements['buttons']['trainer_button'] = trainer_rect
    y_offset += button_height + button_padding

    # --- Game Status ---
    status_text = ""
    status_color = WHITE
    if gamestate.checkmate:
        winner = "Черные" if gamestate.current_turn == 'w' else "Белые"
        status_text = f"Мат! {winner} победили!"
        status_color = (255, 50, 50) # Red
    elif gamestate.stalemate:
        status_text = "Пат! Ничья."
        status_color = (200, 200, 50) # Yellowish
    elif gamestate.needs_promotion_choice:
        player = "Белые" if gamestate.current_turn == 'w' else "Черные"
        status_text = f"{player}, выберите фигуру для превращения."
        status_color = (50, 200, 255) # Cyan

    if status_text:
        status_font = pygame.font.SysFont('arial', 18, bold=True)
        status_surf = status_font.render(status_text, True, status_color)
        status_rect = pygame.Rect(TOTAL_WIDTH + 10, y_offset, SIDE_PANEL_WIDTH - 20, 40)
        pygame.draw.rect(screen, (40, 40, 40), status_rect, border_radius=3)
        screen.blit(status_surf, status_surf.get_rect(center=status_rect.center))
        y_offset += status_rect.height + 10

    # return buttons # Return the dict of button rects
    return ui_elements # Return dict with button and hand piece rects


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

def draw_game_state(screen, gamestate, board_flipped=False):
    """Main drawing function called each frame."""
    # 1. Draw Board and Pieces
    draw_board(screen, board_flipped)
    draw_pieces(screen, gamestate.board, board_flipped)

    # 2. Draw Highlights (selected, legal moves, check, last move)
    draw_highlights(screen, gamestate, board_flipped)

    # 3. Draw Side Panel (captured pieces, controls, status)
    # This function now returns a dict with 'buttons' and 'hand_pieces'
    ui_elements = draw_side_panel(screen, gamestate)

    # 4. Draw Info Panel (if used)
    draw_info_panel(screen, gamestate)

    # 5. Draw Promotion Choice Overlay (if needed)
    # This returns promotion button rects, but they are handled in main loop
    # We might want to merge promotion rects into ui_elements too for consistency
    promotion_buttons = draw_promotion_choice(screen, gamestate)
    if promotion_buttons: # Add promotion buttons to the dict if they exist
        if 'promotion_buttons' not in ui_elements:
             ui_elements['promotion_buttons'] = {}
        ui_elements['promotion_buttons'] = promotion_buttons


    # Return ui_elements dict containing all clickable element rects
    return ui_elements