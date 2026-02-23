# -*- coding: utf-8 -*-
# --- Imports ---
import pygame
import sys
import copy
import random
import time
import math
import threading
from collections import Counter

# Import from project files
from config import *
from pieces import *
from utils import *
from gamestate import GameState
from gui import *
import ai
from thread_utils import AIThread, HintThread


# --- Main Loop ---
def main():
    """Основная функция игры"""

    # <<< 1. Загружаем КЭШ ХОДОВ из БД при старте >>>
    ai.load_move_cache_from_db()

    print("Запуск main()")

    # Инициализация экрана
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Mini Crazyhouse 6×6")
    print("Окно создано")

    # Загрузка изображений
    try:
        if not load_images():
            print("КРИТИЧЕСКАЯ ОШИБКА: Не удалось загрузить изображения фигур!")
            pygame.quit()
            sys.exit(1)
        print("Изображения загружены")
    except Exception as e:
        print(f"КРИТИЧЕСКАЯ ОШИБКА при загрузке изображений: {e}")
        import traceback
        traceback.print_exc()
        pygame.quit()
        sys.exit(1)

    # Инициализация игры
    gamestate = GameState()
    gamestate.setup_initial_board()
    print("Игра инициализирована")

    clock = pygame.time.Clock()

    # AI state
    making_ai_move = False
    ai_thread = None
    ai_move_ready_time = None  # When AI finished — delay before executing

    # Hint state
    show_hint = False
    hint_move = None
    hint_thread = None
    hint_position_hash = None  # Track which position the hint is for

    # Board orientation (manual toggle only, no auto-flip)
    board_flipped = False

    running = True
    print("Начинаем игровой цикл")

    # Check if AI should make the first move
    if gamestate.current_turn == 'b' and gamestate.black_ai_enabled:
        print("AI Black to make the first move.")
        making_ai_move = True
        ai_thread = AIThread(gamestate, gamestate.ai_depth)
        ai_thread.start()

    def start_hint_if_needed():
        """Start hint calculation for current position if hints are enabled."""
        nonlocal hint_thread, hint_move, hint_position_hash
        if not show_hint:
            return
        # Don't hint during AI turns or game-over
        is_current_ai = (gamestate.current_turn == 'w' and gamestate.white_ai_enabled) or \
                        (gamestate.current_turn == 'b' and gamestate.black_ai_enabled)
        if is_current_ai or gamestate.checkmate or gamestate.stalemate:
            hint_move = None
            return
        try:
            pos_hash = ai.get_position_hash(gamestate)
        except Exception:
            pos_hash = None
        if pos_hash == hint_position_hash and hint_move is not None:
            return  # Already have hint for this position
        hint_move = None
        hint_position_hash = pos_hash
        if hint_thread and hint_thread.is_alive():
            pass  # Let old thread finish, will be overwritten
        hint_thread = HintThread(gamestate, depth=gamestate.ai_depth)
        hint_thread.start()

    start_hint_if_needed()

    while running:
        current_time = time.time()

        # Draw everything
        screen.fill(INFO_BG_COLOR)
        ui_elements = draw_game_state(screen, gamestate, board_flipped=board_flipped,
                                       show_hint=show_hint, hint_move=hint_move)
        pygame.display.flip()

        # --- Check hint thread completion ---
        if hint_thread and hint_thread.done:
            hint_move = hint_thread.best_move
            hint_thread = None

        # --- Handle AI Move Completion (with delay) ---
        if making_ai_move and ai_thread and ai_thread.done:
            if ai_move_ready_time is None:
                ai_move_ready_time = current_time  # Mark when AI finished
            
            # Wait AI_MOVE_DELAY seconds before executing
            if current_time - ai_move_ready_time >= AI_MOVE_DELAY:
                print("AI thread finished calculation.")
                ai_best_move = ai_thread.best_move
                ai_thread = None
                making_ai_move = False
                ai_move_ready_time = None

                if ai_best_move:
                    print(f"AI making move: {format_move_for_print(ai_best_move)}")
                    move_success = gamestate.make_move(ai_best_move)
                else:
                    print("!!! AI returned None - selecting random legal move as fallback")
                    legal_moves = gamestate.get_all_legal_moves()
                    if legal_moves:
                        ai_best_move = random.choice(legal_moves)
                        print(f"AI fallback move: {format_move_for_print(ai_best_move)}")
                        move_success = gamestate.make_move(ai_best_move)
                    else:
                        print("!!! No legal moves available - game should be over")
                        move_success = False

                if move_success:
                    if gamestate.needs_promotion_choice:
                        prom_char = 'R' if get_opposite_color(gamestate.current_turn) == 'w' else 'r'
                        gamestate.complete_promotion(prom_char)
                    gamestate.save_state()
                    print("AI move successful.")
                    ai.save_move_cache_to_db(ai.move_cache)
                    # Recalculate hint for new position
                    hint_move = None
                    hint_position_hash = None
                    start_hint_if_needed()
                else:
                    print(f"!!! Error executing AI move: {format_move_for_print(ai_best_move)}")

        # --- Handle Pygame Events ---
        clicked_button_info = None
        clicked_square = None
        clicked_hand_piece_type = None
        clicked_promotion_choice = None

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                print("Quit event received.")
                if ai_thread and ai_thread.is_alive(): print("Waiting for AI thread...")

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not making_ai_move:
                 mouse_pos = event.pos

                 # --- Check standard UI buttons ---
                 clicked_button_info = None
                 if 'buttons' in ui_elements:
                     for name, rect in ui_elements['buttons'].items():
                         if rect.collidepoint(mouse_pos):
                             clicked_button_info = name
                             break
                 if clicked_button_info: continue

                 # --- Check promotion choice buttons ---
                 clicked_promotion_choice = None
                 if gamestate.needs_promotion_choice and 'promotion_buttons' in ui_elements:
                     clicked_promotion_choice = handle_promotion_choice(mouse_pos, ui_elements['promotion_buttons'])
                     if clicked_promotion_choice: continue

                 # --- Check click on board ---
                 clicked_square = None
                 if mouse_pos[0] < TOTAL_WIDTH and mouse_pos[1] < TOTAL_WIDTH:
                     screen_col = mouse_pos[0] // SQUARE_SIZE
                     screen_row = mouse_pos[1] // SQUARE_SIZE

                     if board_flipped:
                         logical_row = BOARD_SIZE - 1 - screen_row
                         logical_col = BOARD_SIZE - 1 - screen_col
                     else:
                         logical_row = screen_row
                         logical_col = screen_col

                     clicked_square = (logical_row, logical_col)

                 # --- Check click on hand piece ---
                 clicked_hand_piece_type = None
                 if 'hand_pieces' in ui_elements:
                      clicked_hand_piece_type = get_clicked_hand_piece(mouse_pos, gamestate, ui_elements['hand_pieces'])
                      if clicked_hand_piece_type:
                           continue

                 if clicked_square: continue


        # --- Process Clicks and Game Logic (Outside Event Loop) ---

        def after_player_move():
            """Common logic after a successful player move."""
            nonlocal making_ai_move, ai_thread, hint_move, hint_position_hash
            hint_move = None
            hint_position_hash = None
            if not (gamestate.checkmate or gamestate.stalemate):
                 is_next_player_ai = (gamestate.current_turn == 'w' and gamestate.white_ai_enabled) or \
                                     (gamestate.current_turn == 'b' and gamestate.black_ai_enabled)
                 if is_next_player_ai:
                      making_ai_move = True
                      ai_thread = AIThread(gamestate, gamestate.ai_depth)
                      ai_thread.start()
                 else:
                      start_hint_if_needed()

        # Handle Button Clicks
        if clicked_button_info and not making_ai_move:
            print(f"Button clicked: {clicked_button_info}")
            if clicked_button_info == 'undo_button':
                print("Attempting to undo two half-moves...")
                undone_ai_move = gamestate.undo_move()
                if undone_ai_move:
                    print("Successfully undid AI's move.")
                    undone_player_move = gamestate.undo_move()
                    if undone_player_move:
                        print("Successfully undid Player's move. Your turn.")
                        making_ai_move = False
                        if ai_thread:
                            try: ai_thread.join(timeout=0.1)
                            except: pass
                            ai_thread = None
                        hint_move = None
                        hint_position_hash = None
                        start_hint_if_needed()
                    else:
                        print("Could not undo Player's move.")
                else:
                    print("Cannot undo any further.")
            elif clicked_button_info == 'new_game_button':
                print("Starting new game...")
                gamestate.setup_initial_board()
                making_ai_move = False
                if ai_thread: ai_thread = None
                hint_move = None
                hint_position_hash = None
                if gamestate.current_turn == 'b' and gamestate.black_ai_enabled:
                    print("AI Black to make the first move in new game.")
                    making_ai_move = True
                    ai_thread = AIThread(gamestate, gamestate.ai_depth)
                    ai_thread.start()
                else:
                    start_hint_if_needed()
            elif clicked_button_info == 'toggle_white_ai':
                 gamestate.white_ai_enabled = not gamestate.white_ai_enabled
                 print(f"White AI: {gamestate.white_ai_enabled}")
                 if gamestate.current_turn == 'w' and gamestate.white_ai_enabled and not making_ai_move:
                      making_ai_move = True
                      ai_thread = AIThread(gamestate, gamestate.ai_depth)
                      ai_thread.start()
                 hint_move = None
                 hint_position_hash = None
                 start_hint_if_needed()
            elif clicked_button_info == 'toggle_black_ai':
                 gamestate.black_ai_enabled = not gamestate.black_ai_enabled
                 print(f"Black AI: {gamestate.black_ai_enabled}")
                 if gamestate.current_turn == 'b' and gamestate.black_ai_enabled and not making_ai_move:
                      making_ai_move = True
                      ai_thread = AIThread(gamestate, gamestate.ai_depth)
                      ai_thread.start()
                 hint_move = None
                 hint_position_hash = None
                 start_hint_if_needed()
            elif clicked_button_info == 'toggle_hint':
                 show_hint = not show_hint
                 print(f"Hints: {'ON' if show_hint else 'OFF'}")
                 if show_hint:
                     hint_move = None
                     hint_position_hash = None
                     start_hint_if_needed()
                 else:
                     hint_move = None
                     hint_position_hash = None
            elif clicked_button_info == 'toggle_flip':
                 board_flipped = not board_flipped
                 print(f"Board flipped: {board_flipped}")
            clicked_button_info = None

        # Handle Promotion Choice Click
        elif clicked_promotion_choice and not making_ai_move:
            print(f"Promotion choice made: {clicked_promotion_choice}")
            if gamestate.complete_promotion(clicked_promotion_choice):
                 gamestate.save_state()
                 after_player_move()
            else:
                 print("Error completing promotion.")
            clicked_promotion_choice = None

        # Handle Hand Piece Click
        elif clicked_hand_piece_type and not making_ai_move:
            full_piece_code = gamestate.current_turn + clicked_hand_piece_type

            if gamestate.selected_drop_piece == full_piece_code:
                gamestate.selected_drop_piece = None
                gamestate.highlighted_moves = []
                print(f"Deselected drop piece: {full_piece_code}")
            else:
                gamestate.selected_drop_piece = full_piece_code
                gamestate.selected_square = None
                print(f"Selected drop piece: {full_piece_code}")
                gamestate.highlighted_moves = []
                for move in gamestate.get_all_legal_moves():
                    if move[0] == 'drop' and move[1] == full_piece_code:
                        gamestate.highlighted_moves.append(move)
            clicked_hand_piece_type = None

        # Handle Board Click
        elif clicked_square and not making_ai_move:
            r, f = clicked_square
            # Case 1: Drop move
            if gamestate.selected_drop_piece:
                drop_move = ('drop', gamestate.selected_drop_piece, clicked_square)
                is_legal_drop = False
                for legal_move in gamestate.highlighted_moves:
                    if is_same_move(drop_move, legal_move):
                        is_legal_drop = True
                        break
                if is_legal_drop:
                    print(f"Attempting drop: {format_move_for_print(drop_move)}")
                    if gamestate.make_move(drop_move):
                        gamestate.save_state()
                        gamestate.selected_drop_piece = None
                        gamestate.highlighted_moves = []
                        print("Drop successful.")
                        after_player_move()
                    else:
                        print("Drop failed.")
                else:
                    print("Invalid drop location.")
            # Case 2: Move piece on board
            elif gamestate.selected_square:
                start_sq = gamestate.selected_square
                target_sq = clicked_square
                found_move = None
                for legal_move in gamestate.get_all_legal_moves():
                    if legal_move[0] != 'drop' and \
                       legal_move[0] == start_sq and \
                       legal_move[1] == target_sq:
                        found_move = legal_move
                        break
                if found_move:
                    print(f"Attempting move: {format_move_for_print(found_move)}")
                    if gamestate.make_move(found_move):
                        if not gamestate.needs_promotion_choice:
                             gamestate.save_state()
                             print("Move successful.")
                             after_player_move()
                        else:
                            print("Move requires promotion choice.")
                        gamestate.selected_square = None
                        gamestate.highlighted_moves = []
                    else:
                        print("Move failed.")
                        gamestate.selected_square = None
                        gamestate.highlighted_moves = []
                else:
                    piece_at_click = gamestate.board[r][f]
                    if piece_at_click != EMPTY_SQUARE and get_piece_color(piece_at_click) == gamestate.current_turn:
                         gamestate.selected_square = clicked_square
                         gamestate.selected_drop_piece = None
                         gamestate.highlighted_moves = []
                         for move in gamestate.get_all_legal_moves():
                              if move[0] != 'drop' and move[0] == clicked_square:
                                   gamestate.highlighted_moves.append(move)
                         print(f"Selected piece at {coords_to_algebraic(*clicked_square)}")
                    else:
                         gamestate.selected_square = None
                         gamestate.highlighted_moves = []
                         print("Deselected piece.")
            # Case 3: Select piece on board
            else:
                piece = gamestate.board[r][f]
                if piece != EMPTY_SQUARE and get_piece_color(piece) == gamestate.current_turn:
                    gamestate.selected_square = clicked_square
                    gamestate.selected_drop_piece = None
                    gamestate.highlighted_moves = []
                    for move in gamestate.get_all_legal_moves():
                        if move[0] != 'drop' and move[0] == clicked_square:
                            gamestate.highlighted_moves.append(move)
                    print(f"Selected piece at {coords_to_algebraic(*clicked_square)}")
                else:
                    pass
            clicked_square = None

        # --- Start AI move if it's AI's turn ---
        is_current_player_ai = (gamestate.current_turn == 'w' and gamestate.white_ai_enabled) or \
                               (gamestate.current_turn == 'b' and gamestate.black_ai_enabled)
        if is_current_player_ai and not making_ai_move and not gamestate.needs_promotion_choice \
           and not gamestate.checkmate and not gamestate.stalemate:
             print(f"AI's turn ({gamestate.current_turn}). Starting calculation.")
             making_ai_move = True
             ai_thread = AIThread(gamestate, gamestate.ai_depth)
             ai_thread.start()

        clock.tick(FPS)

    # --- End of Game Loop ---
    print("Exiting game loop.")
    pygame.quit()
    sys.exit()


# Entry point
if __name__ == "__main__":
    main()