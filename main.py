# -*- coding: utf-8 -*-
# --- Imports ---
import pygame
import sys
import copy
import random
import time
import math
import threading
from collections import Counter # Keep if needed, maybe for eval? Not currently used.

# Import from project files
from config import * # Constants, Colors, Sizes
from pieces import * # Piece data
from utils import * # Helper functions
from gamestate import GameState # Core game logic class
from gui import * # All drawing functions and GUI helpers
import ai # <<< Меняем импорт, чтобы иметь доступ к ai.load/save
# from mate_trainer import MateTrainer # Тренажёр
# from ai import * # AI functions (needed for direct calls?) - find_best_move is in thread
from thread_utils import AIThread # AI thread class

# --- Global Variables / State ---
# show_hint is modified here and read in gui.py
# show_hint = False
# hint_move is calculated by hint thread and read here/in gui.py
# hint_move = None


# --- Main Loop ---
def main():
    """Основная функция игры"""
    # global show_hint, hint_move # Declare modification of globals

    # <<< 1. Загружаем КЭШ ХОДОВ из БД при старте >>>
    # print(f"Attributes in ai module: {dir(ai)}") # <<< Удаляем отладочный print
    ai.load_move_cache_from_db() # <<< Используем новую функцию

    print("Запуск main()")
    # Pygame init is already called in gui.py for fonts
    # pygame.init()

    # Инициализация экрана
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Мини Шахматы - Crazyhouse 6x6")
    print("Окно создано")

    # Загрузка изображений (Function is in gui.py)
    try:
        if not load_images(): 
            print("КРИТИЧЕСКАЯ ОШИБКА: Не удалось загрузить изображения фигур!")
            print("Убедитесь, что следующие файлы находятся в корневой папке проекта:")
            print("  - pawn.png, horse.png, bishop.png, rookie.png, king.png")
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
    gamestate.setup_initial_board() # Sets up board and saves initial state
    print("Игра инициализирована")

    clock = pygame.time.Clock()

    # Переменные для ИИ
    making_ai_move = False
    ai_thread = None

    # Для хинтов
    # hint_thread = None
    # hint_thread_active = False
    # last_hint_position_hash = None # Hash of position for which hint was calculated

    running = True
    print("Начинаем игровой цикл")

    # Check if AI should make the first move
    if gamestate.current_turn == 'b' and gamestate.black_ai_enabled:
        print("AI Black to make the first move.")
        making_ai_move = True
        ai_thread = AIThread(gamestate, gamestate.ai_depth)
        ai_thread.start()

    while running:
        current_time = time.time()
        mouse_pos = pygame.mouse.get_pos()

        # <<< Определяем, нужно ли переворачивать доску >>>
        board_flipped = (gamestate.current_turn == 'b' and not gamestate.black_ai_enabled)

        # We need ui_elements early for event processing
        # Draw everything first to get the rects, then process events for that frame
        screen.fill(INFO_BG_COLOR) # Fill background before drawing
        # <<< Передаем флаг board_flipped в функцию отрисовки >>>
        ui_elements = draw_game_state(screen, gamestate, board_flipped=board_flipped) # Draw and get all UI rects
        pygame.display.flip() # Display the drawn frame

        # --- Handle AI Move Completion ---
        if making_ai_move and ai_thread and ai_thread.done:
            print("AI thread finished calculation.")
            ai_best_move = ai_thread.best_move
            ai_thread = None
            making_ai_move = False # Stop blocking input

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
                    print("!!! AI move resulted in promotion choice needed - AI should have chosen!")
                    prom_char = 'R' if get_opposite_color(gamestate.current_turn) == 'w' else 'r'
                    gamestate.complete_promotion(prom_char)
                gamestate.save_state()
                print("AI move successful.")
                # <<< 2. Сохраняем КЭШ ХОДОВ в БД после успешного хода ИИ >>>
                ai.save_move_cache_to_db(ai.move_cache) # <<< Используем новую функцию и переменную
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

            # Process clicks only if AI is not currently calculating its move
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not making_ai_move:
                 mouse_pos = event.pos # Use event's position for click

                 # --- Check standard UI buttons --- 
                 clicked_button_info = None
                 # Use the buttons rects returned by draw_game_state via ui_elements
                 if 'buttons' in ui_elements:
                     for name, rect in ui_elements['buttons'].items():
                         if rect.collidepoint(mouse_pos):
                             clicked_button_info = name
                             break
                 if clicked_button_info: continue # Handle below event loop

                 # --- Check promotion choice buttons --- 
                 clicked_promotion_choice = None
                 if gamestate.needs_promotion_choice and 'promotion_buttons' in ui_elements:
                     # Use handle_promotion_choice which iterates through the dict
                     clicked_promotion_choice = handle_promotion_choice(mouse_pos, ui_elements['promotion_buttons'])
                     if clicked_promotion_choice: continue # Handle below

                 # --- Check click on board --- 
                 clicked_square = None
                 if mouse_pos[0] < TOTAL_WIDTH and mouse_pos[1] < TOTAL_WIDTH:
                     # Получаем "экранные" координаты клетки
                     screen_col = mouse_pos[0] // SQUARE_SIZE
                     screen_row = mouse_pos[1] // SQUARE_SIZE

                     # <<< Пересчитываем в логические координаты, если доска перевернута >>>
                     if board_flipped:
                         logical_row = BOARD_SIZE - 1 - screen_row
                         logical_col = BOARD_SIZE - 1 - screen_col
                     else:
                         logical_row = screen_row
                         logical_col = screen_col

                     clicked_square = (logical_row, logical_col)
                     # Don't continue yet, need to check hand piece click first or handle board click
                     # if gamestate.selected_drop_piece: continue # Drop target handled below
                     # else: continue # Board selection handled below

                 # --- Check click on hand piece --- 
                 clicked_hand_piece_type = None
                 # Pass the hand_pieces rects from ui_elements to the checking function
                 if 'hand_pieces' in ui_elements:
                      clicked_hand_piece_type = get_clicked_hand_piece(mouse_pos, gamestate, ui_elements['hand_pieces'])
                      if clicked_hand_piece_type:
                           continue # Handle hand piece click below

                 # If we reach here and clicked_square is set, it's a board click (not button/hand/promo)
                 if clicked_square: continue # Handle board click below


        # --- Process Clicks and Game Logic (Outside Event Loop) ---

        # Handle Button Clicks
        if clicked_button_info and not making_ai_move:
            print(f"Button clicked: {clicked_button_info}")
            if clicked_button_info == 'undo_button':
                # --- Новая логика: отменяем два полухода --- 
                print("Attempting to undo two half-moves (AI's then Player's)...")
                undone_ai_move = gamestate.undo_move() # Пытаемся отменить ход ИИ
                if undone_ai_move:
                    print("Successfully undid AI's move.")
                    undone_player_move = gamestate.undo_move() # Пытаемся отменить ход игрока
                    if undone_player_move:
                        print("Successfully undid Player's move. Your turn.")
                        # Убедимся, что ИИ не начнет ходить сразу
                        making_ai_move = False
                        if ai_thread: # Останавливаем поток ИИ, если он вдруг активен
                            # Попытка дождаться завершения потока (маловероятно, но для безопасности)
                            try: ai_thread.join(timeout=0.1) 
                            except: pass # Игнорируем ошибки при остановке
                            ai_thread = None
                    else:
                        print("Could not undo Player's move (already at the start?). It remains AI's turn.")
                        # В этой ситуации ИИ, вероятно, снова сделает ход.
                else:
                    print("Cannot undo any further.")
                # --- Конец новой логики ---
            elif clicked_button_info == 'new_game_button':
                print("Starting new game...")
                gamestate.setup_initial_board() # Reset the game state
                making_ai_move = False # Ensure AI isn't stuck thinking from previous game
                if ai_thread: ai_thread = None # Clear AI thread just in case
                # Check if AI should move first in the new game
                if gamestate.current_turn == 'b' and gamestate.black_ai_enabled:
                    print("AI Black to make the first move in new game.")
                    making_ai_move = True
                    ai_thread = AIThread(gamestate, gamestate.ai_depth)
                    ai_thread.start()
            elif clicked_button_info == 'toggle_white_ai':
                 gamestate.white_ai_enabled = not gamestate.white_ai_enabled
                 print(f"White AI: {gamestate.white_ai_enabled}")
                 if gamestate.current_turn == 'w' and gamestate.white_ai_enabled and not making_ai_move:
                      making_ai_move = True
                      ai_thread = AIThread(gamestate, gamestate.ai_depth)
                      ai_thread.start()
            elif clicked_button_info == 'toggle_black_ai':
                 gamestate.black_ai_enabled = not gamestate.black_ai_enabled
                 print(f"Black AI: {gamestate.black_ai_enabled}")
                 # If black's turn and AI is now enabled, trigger AI move
                 if gamestate.current_turn == 'b' and gamestate.black_ai_enabled and not making_ai_move:
                      making_ai_move = True
                      ai_thread = AIThread(gamestate, gamestate.ai_depth)
                      ai_thread.start()
            # elif clicked_button_info == 'trainer_button': # <<< Убрано - нет тренажёра >>>
            #     print("Запуск тренажёра...")
            #     # <<< Передаем screen и загруженные изображения >>>
            #     trainer = MateTrainer(screen, PIECE_IMAGES)
            #     trainer.run() # Запускаем тренажёр
            #     # После выхода из тренажёра, основной цикл продолжит работу
            #     print("Выход из тренажёра.")
            #     # <<< Перерисовываем основной экран после выхода из тренажера >>>
            #     # Это нужно, так как тренажер мог изменить содержимое экрана
            #     screen.fill(INFO_BG_COLOR)
            #     ui_elements = draw_game_state(screen, gamestate)
            #     pygame.display.flip()
            clicked_button_info = None

        # Handle Promotion Choice Click
        elif clicked_promotion_choice and not making_ai_move:
            print(f"Promotion choice made: {clicked_promotion_choice}")
            if gamestate.complete_promotion(clicked_promotion_choice):
                 gamestate.save_state()
                 if not (gamestate.checkmate or gamestate.stalemate):
                      is_next_player_ai = (gamestate.current_turn == 'w' and gamestate.white_ai_enabled) or \
                                          (gamestate.current_turn == 'b' and gamestate.black_ai_enabled)
                      if is_next_player_ai:
                           making_ai_move = True
                           ai_thread = AIThread(gamestate, gamestate.ai_depth)
                           ai_thread.start()
            else:
                 print("Error completing promotion.")
            clicked_promotion_choice = None

        # Handle Hand Piece Click
        elif clicked_hand_piece_type and not making_ai_move:
            # clicked_hand_piece_type is UPPERCASE 'N', 'P', etc.
            # Construct the full piece code with color, e.g., 'wN', 'bP'
            full_piece_code = gamestate.current_turn + clicked_hand_piece_type

            # Check if this specific piece code is already selected
            if gamestate.selected_drop_piece == full_piece_code:
                gamestate.selected_drop_piece = None # Deselect
                gamestate.highlighted_moves = []
                print(f"Deselected drop piece: {full_piece_code}") # Use full code
            else:
                gamestate.selected_drop_piece = full_piece_code # Store the full code ('wN')
                gamestate.selected_square = None # Deselect board square
                print(f"Selected drop piece: {full_piece_code}") # Use full code
                gamestate.highlighted_moves = []
                # drop_char = clicked_hand_piece_type if gamestate.current_turn == 'w' else piece_to_lower(clicked_hand_piece_type) # OLD logic
                # Use the full_piece_code to find legal moves
                for move in gamestate.get_all_legal_moves():
                    # Move format: ('drop', 'wN', (r, f))
                    if move[0] == 'drop' and move[1] == full_piece_code:
                        gamestate.highlighted_moves.append(move)
            clicked_hand_piece_type = None

        # Handle Board Click
        elif clicked_square and not making_ai_move:
            r, f = clicked_square
            # Case 1: Drop move
            if gamestate.selected_drop_piece:
                # selected_drop_piece now holds the full code ('wN', 'bP', etc.)
                # drop_char = gamestate.selected_drop_piece if gamestate.current_turn == 'w' else piece_to_lower(gamestate.selected_drop_piece) # OLD logic
                # Construct the move tuple using the stored full code
                drop_move = ('drop', gamestate.selected_drop_piece, clicked_square)
                is_legal_drop = False
                # Compare against highlighted moves (which should now match format)
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
                        if not (gamestate.checkmate or gamestate.stalemate):
                             is_next_player_ai = (gamestate.current_turn == 'w' and gamestate.white_ai_enabled) or \
                                                 (gamestate.current_turn == 'b' and gamestate.black_ai_enabled)
                             if is_next_player_ai:
                                  making_ai_move = True
                                  ai_thread = AIThread(gamestate, gamestate.ai_depth)
                                  ai_thread.start()
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
                             if not (gamestate.checkmate or gamestate.stalemate):
                                 is_next_player_ai = (gamestate.current_turn == 'w' and gamestate.white_ai_enabled) or \
                                                     (gamestate.current_turn == 'b' and gamestate.black_ai_enabled)
                                 if is_next_player_ai:
                                      making_ai_move = True
                                      ai_thread = AIThread(gamestate, gamestate.ai_depth)
                                      ai_thread.start()
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

        clock.tick(FPS) # Control frame rate

    # --- End of Game Loop ---
    print("Exiting game loop.")
    pygame.quit()
    sys.exit()


# Entry point
if __name__ == "__main__":
    main()