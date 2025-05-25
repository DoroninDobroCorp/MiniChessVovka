# -*- coding: utf-8 -*-
import copy
from config import BOARD_SIZE
from pieces import (EMPTY_SQUARE, PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING,
                    PROMOTION_PIECES_WHITE_STR, PROMOTION_PIECES_BLACK_STR,
                    KNIGHT_MOVES, DIAGONAL_MOVES, STRAIGHT_MOVES, KING_MOVES)
from utils import (get_piece_color, is_on_board, get_opposite_color,
                   piece_to_lower, piece_to_upper)


# --- Game State Class ---
class GameState:
    """Класс для представления состояния игры"""
    def __init__(self):
        """Инициализация новой игры"""
        self.board = [[EMPTY_SQUARE for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        self.current_turn = 'w'
        self.hands = {'w': {}, 'b': {}}
        self.king_pos = {'w': None, 'b': None}
        self.checkmate = False
        self.stalemate = False
        self.last_move = None
        self.move_log = []
        self.game_over_message = ""
        self.saved_states = []
        self.selected_square = None
        self.selected_drop_piece = None
        self.highlighted_moves = []
        self.needs_promotion_choice = False
        self.promotion_square = None
        self.last_move_for_promotion = None
        self.white_ai_enabled = False
        self.black_ai_enabled = True
        self.ai_depth = 4
        self.show_hint = False # Note: show_hint itself is global in main.py
        self._all_legal_moves_cache = None
        self._is_check_cache = None
        self._hash_cache = None # Добавляем кэш для хэша

    def save_state(self):
        """Сохраняет текущее состояние игры для возможности отмены хода"""
        state = {
            'board': copy.deepcopy(self.board),
            'hands': copy.deepcopy(self.hands),
            'current_turn': self.current_turn,
            'king_pos': copy.deepcopy(self.king_pos),
            'checkmate': self.checkmate,
            'stalemate': self.stalemate,
            'last_move': self.last_move,
            'game_over_message': self.game_over_message,
            'needs_promotion_choice': self.needs_promotion_choice,
            'promotion_square': self.promotion_square
            # 'last_move_for_promotion' might be needed if undo happens during promotion choice
        }
        self.saved_states.append(state)

    def undo_move(self):
        """Отменяет последний ход"""
        if len(self.saved_states) <= 1:
            print("Cannot undo further.")
            return False

        self.saved_states.pop() # Remove current state
        if not self.saved_states: # Should not happen if check above works
             print("Error: No previous state to restore.")
             self.setup_initial_board() # Reset to start as fallback
             self.save_state()
             return False

        prev_state = self.saved_states[-1]
        self.board = copy.deepcopy(prev_state['board'])
        self.hands = copy.deepcopy(prev_state['hands'])
        self.current_turn = prev_state['current_turn']
        self.king_pos = copy.deepcopy(prev_state['king_pos'])
        self.checkmate = prev_state['checkmate']
        self.stalemate = prev_state['stalemate']
        self.last_move = prev_state.get('last_move') # Use get for safety
        self.game_over_message = prev_state['game_over_message']
        self.needs_promotion_choice = prev_state['needs_promotion_choice']
        self.promotion_square = prev_state['promotion_square']
        # self.last_move_for_promotion = prev_state.get('last_move_for_promotion') # Restore if needed

        # Clear selections and highlights
        self.selected_square = None
        self.selected_drop_piece = None
        self.highlighted_moves = []
        self._all_legal_moves_cache = None # Clear cache

        print(f"Move undone. Current turn: {self.current_turn}")
        # Remove the undone move from the log if necessary
        if self.move_log:
            undone_move = self.move_log.pop()
            # print(f"Removed move from log: {format_move_for_print(undone_move)}") # Requires format_move... import

        # Ensure king positions are correct after undo
        self.find_kings() # Recalculate king positions just in case

        return True

    def reset_board(self):
        """Сбрасывает состояние игры к начальному, вызывая __init__."""
        print("[DEBUG GameState] Resetting board...")
        self.__init__()
        print("[DEBUG GameState] Board reset complete.")

    def copy(self):
        """Создает и возвращает глубокую копию текущего объекта GameState."""
        print(f"[DEBUG GameState.copy] Entered copy() for object with id: {id(self)}")
        # Сначала копируем критические данные, особенно hands
        print(f"[DEBUG GameState.copy ENTRY] self.hands = {self.hands}")
        try:
            hands_copy = copy.deepcopy(self.hands)
            print(f"[DEBUG GameState.copy] Result of deepcopy(self.hands): {hands_copy}")
            board_copy = copy.deepcopy(self.board)
            king_pos_copy = copy.deepcopy(self.king_pos)
        except Exception as e:
            print(f"[ERROR GameState.copy] Deepcopy failed: {e}")
            # В случае ошибки вернем пустой или базовый стейт, чтобы избежать креша
            # но это укажет на проблему
            hands_copy = {'w':{}, 'b':{}}
            board_copy = [[EMPTY_SQUARE for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
            king_pos_copy = {'w': None, 'b': None}

        # Теперь создаем новый объект
        new_state = GameState()

        # Присваиваем скопированные значения
        new_state.board = board_copy
        new_state.current_turn = self.current_turn
        new_state.hands = hands_copy # Используем УЖЕ скопированное значение
        new_state.king_pos = king_pos_copy

        # Копируем остальные атрибуты (как раньше)
        new_state.checkmate = self.checkmate
        new_state.stalemate = self.stalemate
        new_state.last_move = self.last_move
        new_state.game_over_message = self.game_over_message
        new_state.selected_square = self.selected_square
        new_state.selected_drop_piece = self.selected_drop_piece
        new_state.highlighted_moves = copy.deepcopy(self.highlighted_moves)
        new_state.needs_promotion_choice = self.needs_promotion_choice
        new_state.promotion_square = self.promotion_square
        new_state.last_move_for_promotion = self.last_move_for_promotion
        new_state.white_ai_enabled = self.white_ai_enabled
        new_state.black_ai_enabled = self.black_ai_enabled
        new_state.ai_depth = self.ai_depth
        new_state._all_legal_moves_cache = None

        print(f"[DEBUG GameState.copy EXIT] new_state.hands = {new_state.hands}")
        return new_state

    def find_kings(self):
        """Explicitly finds and updates king positions."""
        self.king_pos = {'w': None, 'b': None}
        for r in range(BOARD_SIZE):
            for f in range(BOARD_SIZE):
                piece = self.board[r][f]
                if piece == KING[0]:
                    self.king_pos['w'] = (r, f)
                elif piece == KING[1]:
                    self.king_pos['b'] = (r, f)

    def setup_initial_board(self):
        """Устанавливает начальную позицию на доске"""
        self.board = [
            ['.', '.', 'b', 'n', 'r', 'k'], # Black pieces (rank 0)
            ['.', '.', '.', '.', '.', 'p'], # Black pawn
            ['.', '.', '.', '.', '.', '.'], # Empty ranks
            ['.', '.', '.', '.', '.', '.'],
            ['P', '.', '.', '.', '.', '.'], # White pawn (rank 4)
            ['K', 'R', 'N', 'B', '.', '.']  # White pieces (rank 5)
        ]
        self.king_pos = {'w': (5, 0), 'b': (0, 5)}
        self.current_turn = 'w'
        self.hands = {'w': {}, 'b': {}}
        # Initialize hands structure with uppercase keys
        for p_upper in "PNBR": # Removed Q as queens are not usually captured/dropped in mini-chess? Keep if needed.
             self.hands['w'][p_upper] = 0
             self.hands['b'][p_upper] = 0

        self.checkmate = False
        self.stalemate = False
        self.last_move = None
        self.move_log = []
        self.game_over_message = ""
        self.saved_states = [] # Clear history for new game
        self.selected_square = None
        self.selected_drop_piece = None
        self.highlighted_moves = []
        self.needs_promotion_choice = False
        self.promotion_square = None
        self.last_move_for_promotion = None
        self._all_legal_moves_cache = None
        self.save_state() # Save the initial state


    def make_move(self, move, is_check_game_over=True):
        """Выполняет ход, меняет текущего игрока и проверяет окончание игры."""
        self._all_legal_moves_cache = None # Invalidate cache

        if self.needs_promotion_choice:
            print("Error: Cannot make move, must choose promotion first.")
            return False

        # --- Handle Drop Move ---
        if move[0] == 'drop':
            _, piece_code, (r, f) = move # piece_code is 'wN', 'bP', etc.
            # Correctly determine color from first char, type from second
            color = piece_code[0]
            piece_type_upper = piece_code[1] # Already uppercase 'N', 'P', etc.

            # Validations
            if self.board[r][f] != EMPTY_SQUARE:
                print(f"Error (drop): Target square {r},{f} not empty.")
                return False
            # Use the correctly determined color here
            if color != self.current_turn:
                 print(f"Error (drop): Trying to drop {color} piece ('{piece_code}') on {self.current_turn}'s turn.")
                 return False
            # Check hand using the uppercase piece type
            if self.hands[color].get(piece_type_upper, 0) <= 0:
                 print(f"Error (drop): No {piece_type_upper} in {color}'s hand. Hand: {self.hands[color]}")
                 return False
            # Special check for pawn drop on forbidden rank
            if piece_type_upper == 'P':
                 promotion_rank = 0 if color == 'w' else BOARD_SIZE - 1
                 if r == promotion_rank:
                     print(f"Error (drop): Cannot drop pawn {piece_code} on promotion rank {r}.")
                     return False

            # Execute drop
            correct_piece_char = piece_code[1].upper() if color == 'w' else piece_code[1].lower()
            self.board[r][f] = correct_piece_char 
            self.hands[color][piece_type_upper] -= 1 # Decrement using 'N', 'P', etc.
            # Removed King check here, kings are not in hand

            self.last_move = move
            self.move_log.append(move)
            self.current_turn = get_opposite_color(self.current_turn)
            self.selected_square = None # Clear selections
            self.selected_drop_piece = None
            self.highlighted_moves = []

            if is_check_game_over:
                 self.check_game_over() # Check after opponent's turn starts
            return True

        # --- Handle Regular Move ---
        if len(move) != 3 or not isinstance(move[0], tuple) or not isinstance(move[1], tuple):
             print(f"Error: Invalid move format for regular move: {move}")
             return False

        (r1, f1), (r2, f2), promotion_choice = move
        piece = self.board[r1][f1]

        # Validations
        if piece == EMPTY_SQUARE:
            print(f"Error (move): Start square {r1},{f1} is empty.")
            return False
        moving_color = get_piece_color(piece)
        if moving_color != self.current_turn:
             print(f"Error (move): Trying to move {moving_color} piece on {self.current_turn}'s turn.")
             return False

        target_piece = self.board[r2][f2]
        is_capture = target_piece != EMPTY_SQUARE

        # Execute move (part 1: remove piece from start)
        self.board[r1][f1] = EMPTY_SQUARE

        # Handle capture
        if is_capture:
            captured_type = target_piece.upper()
            if captured_type == 'K':
                 print("Error: King capture detected - should not happen in legal moves.")
                 # This indicates a potential issue in move generation or checking
                 # Revert board state? For now, just log it.
            else:
                 # Ensure hand structure exists
                 if moving_color not in self.hands: self.hands[moving_color] = {}
                 for p_upper in "PNBRQ": # Ensure all keys exist
                      if p_upper not in self.hands[moving_color]: self.hands[moving_color][p_upper] = 0

                 self.hands[moving_color][captured_type] = self.hands[moving_color].get(captured_type, 0) + 1
                 # print(f"Captured {target_piece}. {moving_color}'s hand: {self.hands[moving_color]}")

        # Update King position if King moved
        if piece.upper() == 'K':
            self.king_pos[moving_color] = (r2, f2)

        # Place piece on target square / Handle promotion
        is_pawn_move = piece.upper() == 'P'
        promotion_rank = 0 if moving_color == 'w' else BOARD_SIZE - 1

        if is_pawn_move and r2 == promotion_rank:
            if promotion_choice:
                # Promotion choice is provided (likely by AI or already chosen)
                valid_promotions = PROMOTION_PIECES_WHITE_STR if moving_color == 'w' else PROMOTION_PIECES_BLACK_STR
                if promotion_choice not in valid_promotions:
                     print(f"Error: Invalid promotion choice '{promotion_choice}' for {moving_color}.")
                     # Revert move? Put piece back? For now, just error out.
                     self.board[r1][f1] = piece # Put piece back
                     # Need to undo capture as well if it happened
                     if is_capture and captured_type != 'K':
                          self.hands[moving_color][captured_type] -= 1
                     return False
                self.board[r2][f2] = promotion_choice
                self.needs_promotion_choice = False # Promotion was handled
                self.promotion_square = None
                self.last_move_for_promotion = None
            else:
                # Pawn reached promotion rank, but no choice provided yet (human player)
                self.board[r2][f2] = piece # Temporarily place pawn
                self.needs_promotion_choice = True
                self.promotion_square = (r2, f2)
                # Store the move *before* promotion choice is made
                self.last_move_for_promotion = ((r1, f1), (r2, f2), None)
                self.last_move = self.last_move_for_promotion # Set last move for highlighting etc.
                self.move_log.append(self.last_move_for_promotion) # Log the base move
                # Do NOT switch turn yet or check game over
                print(f"Pawn reached promotion rank at {r2},{f2}. Waiting for choice.")
                return True # Indicate move was partially successful, needs completion
        else:
            # Regular move or non-promoting pawn move
            self.board[r2][f2] = piece
            self.needs_promotion_choice = False # Not a promotion situation

        # Finalize move
        self.last_move = move # Store the completed move
        self.move_log.append(move)
        self.current_turn = get_opposite_color(self.current_turn)
        self.selected_square = None # Clear selections
        self.selected_drop_piece = None
        self.highlighted_moves = []

        if is_check_game_over:
            self.check_game_over() # Check after opponent's turn starts

        return True


    def complete_promotion(self, chosen_piece_char):
        """Завершает ход с превращением после выбора игрока/ИИ."""
        if not self.needs_promotion_choice or not self.promotion_square:
            print("Error: Not in promotion choice state.")
            return False

        r, f = self.promotion_square
        # Determine original player color based on whose turn it *was*
        original_player_color = get_opposite_color(self.current_turn) # Turn hasn't switched yet

        valid_promotions = PROMOTION_PIECES_WHITE_STR if original_player_color == 'w' else PROMOTION_PIECES_BLACK_STR
        if chosen_piece_char not in valid_promotions:
             print(f"Error: Invalid promotion choice '{chosen_piece_char}' for {original_player_color}.")
             return False

        # Update board
        self.board[r][f] = chosen_piece_char

        # Update the last move in the log
        if self.move_log and self.last_move_for_promotion:
            # Find the base move in the log (should be the last one)
            if self.move_log[-1] == self.last_move_for_promotion:
                 self.move_log.pop()
                 (r1,f1),(r2,f2),_ = self.last_move_for_promotion
                 completed_move = ((r1,f1),(r2,f2), chosen_piece_char)
                 self.move_log.append(completed_move)
                 self.last_move = completed_move # Update the actual last move
            else:
                 print("Warning: Could not find base promotion move in log to update.")
                 # Log might be inconsistent, proceed with caution
                 (r1,f1),(r2,f2),_ = self.last_move_for_promotion # Assuming this is correct
                 completed_move = ((r1,f1),(r2,f2), chosen_piece_char)
                 self.last_move = completed_move

        else:
             print("Warning: Move log or last_move_for_promotion missing during promotion completion.")
             # Attempt to salvage based on promotion_square
             # This part is less reliable if state is inconsistent
             if self.last_move and self.last_move[0] != 'drop':
                 (r1,f1),(r2,f2),_ = self.last_move
                 if (r2, f2) == (r, f): # Check if last move ended here
                     completed_move = ((r1,f1),(r2,f2), chosen_piece_char)
                     self.last_move = completed_move
                 else: print("Error: Cannot reliably update last move for promotion.")
             else: print("Error: Cannot reliably update last move for promotion.")


        # Reset promotion state and switch turn
        self.needs_promotion_choice = False
        self.promotion_square = None
        self.last_move_for_promotion = None
        # Turn already switched when make_move returned True for promotion pending
        # self.current_turn = get_opposite_color(self.current_turn) # DO NOT switch turn again

        self.selected_square = None # Clear selections
        self.selected_drop_piece = None
        self.highlighted_moves = []
        self._all_legal_moves_cache = None # Invalidate cache

        print(f"Promotion to {chosen_piece_char} completed. Turn: {self.current_turn}")

        # Check game over after promotion is complete and turn switches
        self.check_game_over()

        return True


    # --- Move Generation Methods ---

    def get_pawn_moves(self, r, f, color):
        moves = []
        direction = -1 if color == 'w' else 1
        promotion_rank = 0 if color == 'w' else BOARD_SIZE - 1
        prom_pieces = PROMOTION_PIECES_WHITE_STR if color == 'w' else PROMOTION_PIECES_BLACK_STR

        # Forward move
        nr, nf = r + direction, f
        if is_on_board(nr, nf) and self.board[nr][nf] == EMPTY_SQUARE:
            if nr == promotion_rank:
                # Generate promotion moves immediately
                for prom_piece in prom_pieces:
                    moves.append(((r, f), (nr, nf), prom_piece))
            else:
                moves.append(((r, f), (nr, nf), None))

        # Captures
        for df in [-1, 1]:
            nr, nf = r + direction, f + df
            if is_on_board(nr, nf):
                target_piece = self.board[nr][nf]
                if target_piece != EMPTY_SQUARE and get_piece_color(target_piece) != color:
                    if nr == promotion_rank:
                        for prom_piece in prom_pieces:
                            moves.append(((r, f), (nr, nf), prom_piece))
                    else:
                        moves.append(((r, f), (nr, nf), None))
        return moves

    def get_knight_moves(self, r, f, color):
        moves = []
        for dr, df in KNIGHT_MOVES:
            nr, nf = r + dr, f + df
            if is_on_board(nr, nf):
                target_piece = self.board[nr][nf]
                if target_piece == EMPTY_SQUARE or get_piece_color(target_piece) != color:
                    moves.append(((r, f), (nr, nf), None))
        return moves

    def get_sliding_moves(self, r, f, color, directions):
        moves = []
        for dr, df in directions:
            nr, nf = r + dr, f + df
            while is_on_board(nr, nf):
                target_piece = self.board[nr][nf]
                if target_piece == EMPTY_SQUARE:
                    moves.append(((r, f), (nr, nf), None))
                elif get_piece_color(target_piece) != color:
                    moves.append(((r, f), (nr, nf), None)) # Capture
                    break
                else: # Friendly piece
                    break
                nr, nf = nr + dr, nf + df
        return moves

    def get_bishop_moves(self, r, f, color):
        return self.get_sliding_moves(r, f, color, DIAGONAL_MOVES)

    def get_rook_moves(self, r, f, color):
         return self.get_sliding_moves(r, f, color, STRAIGHT_MOVES)

    def get_queen_moves(self, r, f, color): # Queens can only appear via drops currently
        return self.get_sliding_moves(r, f, color, DIAGONAL_MOVES + STRAIGHT_MOVES)

    def get_king_moves(self, r, f, color):
        moves = []
        # King cannot move into check - this check is done in get_all_legal_moves
        for dr, df in KING_MOVES:
            nr, nf = r + dr, f + df
            if is_on_board(nr, nf):
                target_piece = self.board[nr][nf]
                if target_piece == EMPTY_SQUARE or get_piece_color(target_piece) != color:
                     moves.append(((r, f), (nr, nf), None))
        # Castling is not part of mini crazyhouse
        return moves

    def generate_all_pseudo_legal_moves(self, color):
        """Generates all possible moves for 'color' without checking for check.
           Uses the current object's state (self.board, self.hands).
        """
        moves = []
        drop_moves_generated = [] # Отладка
        # print(f"[DEBUG Pseudo] Generating pseudo-legal for {color} on board:")
        # for r_idx, row in enumerate(self.board):
        #     print(f"      {r_idx}: {row}")
            
        # Moves from pieces on board
        print(f"[DEBUG Board Check] Checking board for {color} moves...") # Отладка
        for r in range(BOARD_SIZE):
            for f in range(BOARD_SIZE):
                piece = self.board[r][f] # Используем self.board
                piece_color = get_piece_color(piece) # Может вернуть None для EMPTY_SQUARE
                # Отладка проверки фигуры на доске
                # if r == 5 and f == 4: # Пример для вывода конкретной клетки (где стоит wK в одном из логов)
                #    print(f"  Checking ({r},{f}): Piece='{piece}' ({type(piece)}), PieceColor='{piece_color}', ExpectedColor='{color}', EMPTY_SQUARE='{EMPTY_SQUARE}' ({type(EMPTY_SQUARE)})")
                if piece != EMPTY_SQUARE and piece_color == color:
                    # print(f"  Found own piece '{piece}' at ({r},{f})") # Отладка
                    piece_type = piece.upper()
                    move_func = None
                    if piece_type == PAWN[0]: move_func = self.get_pawn_moves
                    elif piece_type == KNIGHT[0]: move_func = self.get_knight_moves
                    elif piece_type == BISHOP[0]: move_func = self.get_bishop_moves
                    elif piece_type == ROOK[0]: move_func = self.get_rook_moves
                    elif piece_type == QUEEN[0]: move_func = self.get_queen_moves
                    elif piece_type == KING[0]: move_func = self.get_king_moves

                    if move_func:
                        # Передаем r, f, color - методы будут использовать self.board
                        # print(f"    Calling {move_func.__name__} for ({r},{f})") # Отладка
                        piece_moves = move_func(r, f, color)
                        # print(f"    {move_func.__name__} returned: {piece_moves}") # Отладка
                        moves.extend(piece_moves)

        # Drop moves from hand
        # print(f"[DEBUG Drop] Getting drops for {color}. Hand: {self.hands.get(color)}")
        player_hand = self.hands.get(color, {}) # Используем self.hands
        print(f"[DEBUG Drop Check] Checking drops for {color}. Hand: {player_hand}") # Отладка
        if player_hand:
            for piece_type_upper, count in player_hand.items():
                if count > 0:
                    piece_code = color + piece_type_upper # Construct 'wN', 'bP', etc.
                    # Special check for pawn drop legality (no drop on promotion rank)
                    promotion_rank = 0 if color == 'w' else BOARD_SIZE - 1
                    is_pawn = piece_type_upper == 'P'

                    for r in range(BOARD_SIZE):
                        # Cannot drop pawn on promotion rank
                        if is_pawn and r == promotion_rank:
                            continue
                        for f in range(BOARD_SIZE):
                            target_cell = self.board[r][f]
                            print(f"  Checking drop at ({r},{f}): Cell='{target_cell}' ({type(target_cell)}), EMPTY_SQUARE='{EMPTY_SQUARE}' ({type(EMPTY_SQUARE)}), Comparison Result: {target_cell == EMPTY_SQUARE}")
                            if target_cell == EMPTY_SQUARE:
                                drop_move = ('drop', piece_code, (r, f)) # Use constructed piece_code
                                moves.append(drop_move)
                                drop_moves_generated.append(drop_move) # Отладка
                    # print(f"[DEBUG Drop] Finished checking drops for {piece_char}") # Отладка

        # print(f"[DEBUG Pseudo] Total pseudo-legal moves: {len(moves)}")
        print(f"[DEBUG Pseudo Gen] For {color}, Generated {len(drop_moves_generated)} drop moves: {drop_moves_generated}") # Отладка
        print(f"[DEBUG Pseudo Gen] For {color}, Total generated pseudo-legal moves: {len(moves)}") # Отладка
        return moves

    def get_all_legal_moves(self):
        """Generates all LEGAL moves for the CURRENT player. Caches result."""
        if self._all_legal_moves_cache is not None:
            return self._all_legal_moves_cache

        if self.needs_promotion_choice:
            self._all_legal_moves_cache = []
            return []

        legal_moves = []
        current_color = self.current_turn
        # Вызываем generate_all_pseudo_legal_moves для ТЕКУЩЕГО объекта (self)
        # Он использует self.board и self.hands
        pseudo_legal_moves = self.generate_all_pseudo_legal_moves(current_color)
        # print(f"[DEBUG Legality] Pseudo-legal for {current_color}: {pseudo_legal_moves}")
        print(f"[DEBUG Legality Check] For {current_color}, received {len(pseudo_legal_moves)} pseudo-legal moves to check.") # Отладка

        # Для проверки легальности нам все еще нужно симулировать ходы
        # Сохраняем состояние ТЕКУЩЕГО объекта (не нужно, симулируем на копии)
        # original_board = copy.deepcopy(self.board)
        # original_hands = copy.deepcopy(self.hands)
        # original_king_pos = copy.deepcopy(self.king_pos)

        for move in pseudo_legal_moves:
            # Создаем копию ТЕКУЩЕГО объекта для симуляции
            temp_game_state = self.copy()

            # --- Новая симуляция с использованием копии GameState ---
            # Пытаемся сделать ход на КОПИИ
            move_made = temp_game_state.make_move(move, is_check_game_over=False) # Не проверяем game over внутри симуляции
            if move_made:
                 # После хода проверяем, не оказался ли король ТЕКУЩЕГО игрока под шахом на доске копии
                 is_check_after = temp_game_state.is_in_check(current_color)
                 if not is_check_after:
                      legal_moves.append(move) # Ход легален
                 # else: # Отладка - почему ход нелегален
                 #    print(f"[DEBUG Legality Check] Move {move} for {current_color} is ILLEGAL (king in check after)")
            # else: # Отладка - почему ход не сделался
            #    print(f"[DEBUG Legality Check] Move {move} for {current_color} FAILED simulation (make_move returned False)")
            # --- Конец новой симуляции ---

        self._all_legal_moves_cache = legal_moves
        # print(f"[DEBUG Legality] Legal moves for {current_color}: {legal_moves}")
        print(f"[DEBUG Legality Check] For {current_color}, Found {len(legal_moves)} legal moves after filtering.") # Отладка
        return legal_moves

    def is_in_check(self, color):
        """Проверяет, находится ли король цвета color под шахом."""
        king_pos = self.king_pos.get(color)
        if not king_pos:
             self.find_kings()
             king_pos = self.king_pos.get(color)
             if not king_pos:
                  print(f"Предупреждение (is_in_check): Король цвета {color} не найден на доске!")
                  return False
        # Вызываем ПЕРЕИМЕНОВАННЫЙ метод
        return self._internal_is_square_attacked(king_pos[0], king_pos[1], get_opposite_color(color))

    def check_game_over(self):
        """Checks and sets checkmate/stalemate flags."""
        if self.needs_promotion_choice: return False # Game not over yet

        # Check for the player WHOSE TURN IT IS NOW
        current_player_color = self.current_turn
        legal_moves = self.get_all_legal_moves() # Get legal moves for the current player

        if not legal_moves:
            # Check if the current player is in check
            if self.is_in_check(current_player_color):
                self.checkmate = True
                winner = "Black" if current_player_color == 'w' else "White"
                self.game_over_message = f"Checkmate! {winner} wins."
                print(self.game_over_message)
            else:
                self.stalemate = True
                self.game_over_message = "Stalemate! Draw."
                print(self.game_over_message)
            return True # Game is over

        # Game is not over
        self.checkmate = False
        self.stalemate = False
        self.game_over_message = ""
        return False

    # --- Legality and Check Checking ---

    # ВОССТАНАВЛИВАЕМ МЕТОД
    def _internal_is_square_attacked(self, r, f, attacker_color):
        """Проверяет, атаковано ли поле (r, f) фигурами цвета attacker_color.
           Использует self.board.
        """
        opponent_color = get_opposite_color(attacker_color)

        # Check Pawns
        pawn_piece = PAWN[0] if attacker_color == 'w' else PAWN[1]
        pawn_dir = -1 if attacker_color == 'w' else 1 # Direction pawns *move*
        # Pawns attack diagonally forward relative to their movement direction
        for df_attack in [-1, 1]:
            pr, pf = r - pawn_dir, f + df_attack # Check squares where attacker pawn could be
            if is_on_board(pr, pf) and self.board[pr][pf] == pawn_piece:
                 # print(f"Debug: Square {r},{f} attacked by {pawn_piece} at {pr},{pf}")
                 return True

        # Check Knights
        knight_piece = KNIGHT[0] if attacker_color == 'w' else KNIGHT[1]
        for dr, df in KNIGHT_MOVES:
            nr, nf = r + dr, f + df
            if is_on_board(nr, nf) and self.board[nr][nf] == knight_piece:
                 # print(f"Debug: Square {r},{f} attacked by {knight_piece} at {nr},{nf}")
                 return True

        # Check Sliding Pieces (Bishops, Rooks, Queens)
        bishop_piece = BISHOP[0] if attacker_color == 'w' else BISHOP[1]
        rook_piece = ROOK[0] if attacker_color == 'w' else ROOK[1]
        queen_piece = QUEEN[0] if attacker_color == 'w' else QUEEN[1] # Queens can be dropped

        # Diagonal Attacks (Bishop, Queen)
        for dr, df in DIAGONAL_MOVES:
            cr, cf = r + dr, f + df
            while is_on_board(cr, cf):
                piece = self.board[cr][cf]
                if piece != EMPTY_SQUARE:
                    if piece == bishop_piece or piece == queen_piece:
                         # print(f"Debug: Square {r},{f} attacked by {piece} at {cr},{cf}")
                         return True
                    break # Path blocked
                cr, cf = cr + dr, cf + df

        # Straight Attacks (Rook, Queen)
        for dr, df in STRAIGHT_MOVES:
            cr, cf = r + dr, f + df
            while is_on_board(cr, cf):
                piece = self.board[cr][cf]
                if piece != EMPTY_SQUARE:
                    if piece == rook_piece or piece == queen_piece:
                         # print(f"Debug: Square {r},{f} attacked by {piece} at {cr},{cf}")
                         return True
                    break # Path blocked
                cr, cf = cr + dr, cf + df

        # Check King
        king_piece = KING[0] if attacker_color == 'w' else KING[1]
        for dr, df in KING_MOVES:
            kr, kf = r + dr, f + df
            if is_on_board(kr, kf) and self.board[kr][kf] == king_piece:
                 # print(f"Debug: Square {r},{f} attacked by {king_piece} at {kr},{kf}")
                 return True

        return False