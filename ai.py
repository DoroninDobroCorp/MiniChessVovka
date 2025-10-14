# --- Imports and Constants ---
import sqlite3
import time
import copy
import random
import math
import multiprocessing
import pickle # For deep copying complex objects like GameState
import hashlib
import traceback
from utils import format_move_for_print, algebraic_to_coords, get_piece_color, get_opposite_color, is_on_board
from config import BOARD_SIZE

# Set multiprocessing start method to 'fork' for macOS (faster and more reliable)
try:
    multiprocessing.set_start_method('fork', force=True)
except RuntimeError:
    pass  # Already set

 

# Piece values (example, adjust as needed)
# Increased difference between pieces
PIECE_VALUES = {'P': 100, 'N': 320, 'B': 330, 'R': 500, 'Q': 900, 'K': 20000}
HAND_PIECE_VALUES = {'P': 150, 'N': 400, 'B': 410, 'R': 650, 'Q': 1000} # Much more valuable in hand for drops!

# --- Game Phase Constants ---
OPENING_PHASE = 0
ENDGAME_PHASE = 1 # Simplified: endgame if few pieces left

# --- Piece Square Tables (Simplified Example - More bonus for center) ---
# Bonus for controlling center squares (e.g., c3, d3, c4, d4 in standard)
# Indices for a 6x6 board need adjustment. Let's assume center is roughly rows 2,3 and cols 2,3
# (0,0) top-left -> (5,5) bottom-right
CENTER_SQUARES = [(2, 2), (2, 3), (3, 2), (3, 3)]
CENTER_BONUS = 15 # Bonus points per piece in center
KING_SAFETY_BONUS = 8 # Small bonus for pieces near king
MOBILITY_BONUS = 3 # Bonus per legal move
PAWN_STRUCTURE_BONUS = 5 # Bonus for connected pawns (simple check)
ATTACK_KING_ZONE_BONUS = 20 # Bonus for attacking squares near enemy king
DROP_THREAT_BONUS = 25 # Extra bonus for having pieces in hand (drop threats)

# --- Transposition Table (Now a simple Move Cache) ---
# Stores: {(position_hash, depth): best_move_repr} - includes depth to avoid shallow cached moves
move_cache = {}

# --- Transposition Table for Alpha-Beta ---
# key: position hash; value: dict(depth=int, score=float, flag=str('EXACT'|'LOWERBOUND'|'UPPERBOUND'), best_move=move)
tt = {}

# --- Killer Moves and History Heuristic ---
killer_moves = {}  # {depth: [move1, move2]}
history_scores = {}  # {move_repr: score}

# --- Database Handling for Move Cache ---
DB_PATH = "move_cache.db" # Renamed DB file

# --- Configuration ---
CACHE_ENABLED = True
# How many worker processes to use for parallel search
# Use None to let multiprocessing decide (usually number of CPU cores)
NUM_WORKERS = None

# --- Constants ---
CHECKMATE_SCORE = 1000000 # Large score for checkmate
STALEMATE_SCORE = 0       # Score for stalemate
MAX_QUIESCENCE_DEPTH = 4  # Limit quiescence search depth (increased for better tactics)

def setup_db():
    """Creates the move_cache table if it doesn't exist."""
    try:
        conn = sqlite3.connect(DB_PATH) # No timeout needed for simple ops
        cursor = conn.cursor()
        # Simplified schema: hash -> best_move representation
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS move_cache (
                hash TEXT PRIMARY KEY,
                best_move_repr TEXT
            )
        ''')
        conn.commit()
        conn.close()
        print(f"Database {DB_PATH} checked/created successfully.")
    except Exception as e:
        print(f"Error setting up database: {e}")

def load_move_cache_from_db():
    """Loads the move cache from the SQLite database."""
    global move_cache
    setup_db() # Ensure DB and table exist
    loaded_count = 0
    # Note: Old cache format didn't include depth, so we skip loading it
    # to avoid using shallow cached moves
    move_cache = {} # Start fresh - old cache was without depth
    print(f"Starting with empty move cache (old format incompatible).")
    # try:
    #     conn = sqlite3.connect(DB_PATH)
    #     cursor = conn.cursor()
    #     cursor.execute("SELECT hash, best_move_repr FROM move_cache")
    #     rows = cursor.fetchall()
    #     move_cache = {row[0]: row[1] for row in rows}
    #     loaded_count = len(move_cache)
    #     conn.close()
    #     print(f"Loaded {loaded_count} entries from move cache database.")
    # except Exception as e:
    #     print(f"Error loading move cache from database: {e}")
    #     move_cache = {} # Start with empty cache on error

def save_move_cache_to_db(cache_to_save):
    """Saves the current move cache to the SQLite database."""
    # Disabled saving - new format uses (hash, depth) tuple keys which don't work well with DB
    print(f"Move cache saving disabled (new format with depth tracking).")
    # print(f"Attempting to save {len(cache_to_save)} cache entries...")
    # try:
    #     conn = sqlite3.connect(DB_PATH)
    #     cursor = conn.cursor()
    #     # Use INSERT OR REPLACE to update existing entries or insert new ones
    #     entries_to_save = list(cache_to_save.items())
    #     cursor.executemany("INSERT OR REPLACE INTO move_cache (hash, best_move_repr) VALUES (?, ?)", entries_to_save)
    #     conn.commit()
    #     conn.close()
    #     print(f"Successfully saved {len(entries_to_save)} entries to move cache database.")
    # except Exception as e:
    #     print(f"Error saving move cache to database: {e}")


# --- Game State Import ---
# Import the actual GameState class and necessary constants
try:
    from gamestate import GameState # Import GameState class
    from pieces import EMPTY_SQUARE, KING, PAWN, PROMOTION_PIECES_WHITE_STR, PROMOTION_PIECES_BLACK_STR, KNIGHT_MOVES # Import constants
except ImportError:
    print("Warning: gamestate.py or pieces.py not found. Using dummy GameState.")
    # Provide minimal fallbacks for constants
    EMPTY_SQUARE = '.'
    # Define a basic dummy class for structure
    class GameState:
        def __init__(self):
            self.board = [[EMPTY_SQUARE for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
            self.current_turn = 'w'
            self.white_hand = {}
            self.black_hand = {}
            self.white_king_pos = None
            self.black_king_pos = None
            self.checkmate = False
            self.stalemate = False
            self.move_log = []
            self.needs_promotion_choice = False
            self.promotion_square = None
            self.en_passant_target = None # For hashing
            self.castling_rights = '----' # For hashing

        def get_all_legal_moves(self): return []
        def make_move(self, move, is_check_game_over=True): return False
        def complete_promotion(self, piece): return False
        def is_in_check(self): return False
        def get_piece_locations(self, color): return []
        def get_piece(self, r, c): return None
        def is_move_legal(self, move): # Added stub for cache check
             return move in self.get_all_legal_moves()


    KING = 'k'
    PAWN = 'p'
    PROMOTION_PIECES_WHITE_STR = "QRN" # Example
    PROMOTION_PIECES_BLACK_STR = "qrn" # Example


# --- Helper Functions ---
# Using helpers imported from utils: get_piece_color, get_opposite_color

def get_position_hash(gamestate: GameState):
    """Generates a unique and STABLE hash for the current game state including hands and turn.

       Handles potential missing attributes gracefully.
       Uses SHA256 for stability across runs.
    """
    try:
        board_tuple = tuple(''.join(row) for row in gamestate.board)
        # Hands are explicitly sorted for consistency
        white_hand_tuple = tuple(sorted(gamestate.hands.get('w', {}).items()))
        black_hand_tuple = tuple(sorted(gamestate.hands.get('b', {}).items()))
        turn = gamestate.current_turn
        # Use getattr for attributes that might be missing in some states/copies
        # Ensure consistent defaults (e.g., None or specific string)
        en_passant = getattr(gamestate, 'en_passant_target', None)
        # Castling rights format needs to be consistent
        castling_w_k = getattr(gamestate, 'can_castle_white_kingside', False)
        castling_w_q = getattr(gamestate, 'can_castle_white_queenside', False)
        castling_b_k = getattr(gamestate, 'can_castle_black_kingside', False)
        castling_b_q = getattr(gamestate, 'can_castle_black_queenside', False)
        castling = (castling_w_k, castling_w_q, castling_b_k, castling_b_q)

        # Combine all relevant state information into a tuple
        state_tuple = (board_tuple, white_hand_tuple, black_hand_tuple, turn, en_passant, castling)

        # Convert tuple to a string representation for hashing
        # Using repr() is generally safe and stable for tuples of primitives/basic types
        state_string = repr(state_tuple)

        # Calculate SHA256 hash
        hasher = hashlib.sha256()
        hasher.update(state_string.encode('utf-8')) # Hash the UTF-8 encoded string
        stable_hash = hasher.hexdigest() # Get the hex representation of the hash

        return stable_hash
    except Exception as e:
        print(f"[ERROR] Failed to generate hash: {e}")
        traceback.print_exc() # <--- Теперь traceback определен
        # Return a default or error hash to avoid crashing, though moves won't cache
        return "error_hash"


# --- Evaluation Function ---
def evaluate_position(gamestate: GameState):
    """
    Evaluates the current board position based on material, piece positions,
    king safety, mobility, and pawn structure.
    Returns a score (positive for white advantage, negative for black).
    """
    if gamestate.checkmate:
        return -float('inf') if gamestate.current_turn == 'w' else float('inf')
    if gamestate.stalemate:
        # --- Stalemate Evaluation based on Material ---
        white_material = 0
        black_material = 0
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                piece = gamestate.board[r][c]
                if piece != EMPTY_SQUARE:
                    value = PIECE_VALUES.get(piece.upper(), 0)
                    if get_piece_color(piece) == 'w': white_material += value
                    else: black_material += value
        for piece, count in gamestate.hands.get('w', {}).items():
             white_material += HAND_PIECE_VALUES.get(piece.upper(), 0) * count
        for piece, count in gamestate.hands.get('b', {}).items():
             black_material += HAND_PIECE_VALUES.get(piece.upper(), 0) * count

        material_diff = white_material - black_material
        # If white has advantage and it's white's turn (stalemate for black), it's bad for white.
        if gamestate.current_turn == 'w' and material_diff > 100: return -10000 # White failed to win
        # If black has advantage and it's black's turn (stalemate for white), it's bad for black.
        elif gamestate.current_turn == 'b' and material_diff < -100: return 10000 # Black failed to win
        # Otherwise, treat stalemate as close to zero (drawish)
        else: return 0

    score = 0
    white_king_pos = gamestate.king_pos.get('w')
    black_king_pos = gamestate.king_pos.get('b')
    white_king_r, white_king_c = white_king_pos if white_king_pos else (-1,-1)
    black_king_r, black_king_c = black_king_pos if black_king_pos else (-1,-1)
    total_material = 0 # For phase detection

    # 1. Material Count & Basic Piece Positions
    white_pawns = []
    black_pawns = []
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            piece = gamestate.board[r][c]
            if piece != EMPTY_SQUARE:
                piece_type = piece.upper()
                piece_color = get_piece_color(piece)
                value = PIECE_VALUES.get(piece_type, 0)
                total_material += value

                if piece_color == 'w':
                    score += value
                    if (r, c) in CENTER_SQUARES: score += CENTER_BONUS
                    if piece_type == 'P': white_pawns.append((r, c))
                    # King safety bonus (simple: distance)
                    if white_king_r != -1 and piece_type != 'K':
                         dist = max(abs(r - white_king_r), abs(c - white_king_c))
                         if dist <= 2: score += KING_SAFETY_BONUS
                else:
                    score -= value
                    if (r, c) in CENTER_SQUARES: score -= CENTER_BONUS
                    if piece_type == 'P': black_pawns.append((r, c))
                     # King safety bonus
                    if black_king_r != -1 and piece_type != 'K':
                         dist = max(abs(r - black_king_r), abs(c - black_king_c))
                         if dist <= 2: score -= KING_SAFETY_BONUS

    # Add hand material value + drop threat bonus
    white_hand_count = sum(gamestate.hands.get('w', {}).values())
    black_hand_count = sum(gamestate.hands.get('b', {}).values())
    
    for piece, count in gamestate.hands.get('w', {}).items():
        score += HAND_PIECE_VALUES.get(piece.upper(), 0) * count
        total_material += PIECE_VALUES.get(piece.upper(), 0) * count # Use board value for phase
    for piece, count in gamestate.hands.get('b', {}).items():
        score -= HAND_PIECE_VALUES.get(piece.upper(), 0) * count
        total_material += PIECE_VALUES.get(piece.upper(), 0) * count
    
    # Bonus for having pieces in hand (drop flexibility)
    score += white_hand_count * DROP_THREAT_BONUS
    score -= black_hand_count * DROP_THREAT_BONUS

    # Determine game phase (simplified)
    # Less than ~2 Rooks worth of material left besides kings? Consider it endgame.
    phase = ENDGAME_PHASE if total_material < (2 * PIECE_VALUES['R'] + 2*PIECE_VALUES['K']) else OPENING_PHASE

    # 2. Mobility (simple count of legal moves) - potentially expensive
    # white_moves = len(gamestate.get_valid_moves_for_color('w')) # Assuming this function exists
    # black_moves = len(gamestate.get_valid_moves_for_color('b')) # Assuming this function exists
    # score += (white_moves - black_moves) * MOBILITY_BONUS

    # 3. Pawn Structure (very simple: connected pawns)
    for r, c in white_pawns:
        # Check adjacent files for friendly pawns
        if c > 0 and gamestate.board[r][c-1] == 'P': score += PAWN_STRUCTURE_BONUS
        if c < BOARD_SIZE-1 and gamestate.board[r][c+1] == 'P': score += PAWN_STRUCTURE_BONUS
        # Add bonus for passed pawns (no opponent pawns ahead in this or adjacent files) - simplified
        is_passed = True
        for scan_r in range(r - 1, -1, -1): # Check rows ahead
            if gamestate.board[scan_r][c] == 'p': is_passed = False; break
            if c > 0 and gamestate.board[scan_r][c-1] == 'p': is_passed = False; break
            if c < BOARD_SIZE-1 and gamestate.board[scan_r][c+1] == 'p': is_passed = False; break
        if is_passed: score += (BOARD_SIZE - 1 - r) * 10 # Bonus increases closer to promotion

    for r, c in black_pawns:
        if c > 0 and gamestate.board[r][c-1] == 'p': score -= PAWN_STRUCTURE_BONUS
        if c < BOARD_SIZE-1 and gamestate.board[r][c+1] == 'p': score -= PAWN_STRUCTURE_BONUS
        is_passed = True
        for scan_r in range(r + 1, BOARD_SIZE): # Check rows ahead
            if gamestate.board[scan_r][c] == 'P': is_passed = False; break
            if c > 0 and gamestate.board[scan_r][c-1] == 'P': is_passed = False; break
            if c < BOARD_SIZE-1 and gamestate.board[scan_r][c+1] == 'P': is_passed = False; break
        if is_passed: score -= r * 10 # Bonus increases closer to promotion

    # 4. King Safety (endgame vs opening)
    if phase == OPENING_PHASE:
        # Penalty for king being too exposed (e.g., in center) - Needs better logic
        if (white_king_r, white_king_c) in CENTER_SQUARES: score -= 20
        if (black_king_r, black_king_c) in CENTER_SQUARES: score += 20
    else: # Endgame
        # Bonus for king being active / closer to center
        if (white_king_r, white_king_c) in CENTER_SQUARES: score += 10
        if (black_king_r, black_king_c) in CENTER_SQUARES: score -= 10

    # 5. IMPROVED: Piece Development Bonus (opening phase)
    if phase == OPENING_PHASE:
        # White pieces still on back rank (undeveloped)
        white_undeveloped = 0
        for c in range(BOARD_SIZE):
            piece = gamestate.board[5][c]
            if piece in ['N', 'B', 'R'] and piece != EMPTY_SQUARE:
                white_undeveloped += 1
        score -= white_undeveloped * 15  # Penalty for undeveloped pieces
        
        # Black pieces still on back rank
        black_undeveloped = 0
        for c in range(BOARD_SIZE):
            piece = gamestate.board[0][c]
            if piece in ['n', 'b', 'r'] and piece != EMPTY_SQUARE:
                black_undeveloped += 1
        score += black_undeveloped * 15

    # 6. IMPROVED: King Attack Evaluation
    # Count attacks on squares around enemy king
    if white_king_r != -1 and black_king_r != -1:
        # Count white pieces attacking black king zone
        white_attackers_on_black_king = 0
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0: continue
                check_r, check_c = black_king_r + dr, black_king_c + dc
                if is_on_board(check_r, check_c):
                    # Check if any white piece attacks this square
                    for r in range(BOARD_SIZE):
                        for c in range(BOARD_SIZE):
                            piece = gamestate.board[r][c]
                            if piece != EMPTY_SQUARE and get_piece_color(piece) == 'w':
                                # Simplified check: knights, bishops, rooks, queens
                                piece_type = piece.upper()
                                if piece_type == 'N':
                                    if (check_r - r, check_c - c) in KNIGHT_MOVES:
                                        white_attackers_on_black_king += 1
                                elif piece_type in ['B', 'Q']:
                                    # Diagonal attacks
                                    if abs(check_r - r) == abs(check_c - c) and check_r != r:
                                        # Check line is clear (simplified)
                                        white_attackers_on_black_king += 0.5
                                elif piece_type in ['R', 'Q']:
                                    # Straight attacks
                                    if (check_r == r or check_c == c) and not (check_r == r and check_c == c):
                                        white_attackers_on_black_king += 0.5
        
        score += white_attackers_on_black_king * ATTACK_KING_ZONE_BONUS
        
        # Count black pieces attacking white king zone (mirror logic)
        black_attackers_on_white_king = 0
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0: continue
                check_r, check_c = white_king_r + dr, white_king_c + dc
                if is_on_board(check_r, check_c):
                    for r in range(BOARD_SIZE):
                        for c in range(BOARD_SIZE):
                            piece = gamestate.board[r][c]
                            if piece != EMPTY_SQUARE and get_piece_color(piece) == 'b':
                                piece_type = piece.upper()
                                if piece_type == 'N':
                                    if (check_r - r, check_c - c) in KNIGHT_MOVES:
                                        black_attackers_on_white_king += 1
                                elif piece_type in ['B', 'Q']:
                                    if abs(check_r - r) == abs(check_c - c) and check_r != r:
                                        black_attackers_on_white_king += 0.5
                                elif piece_type in ['R', 'Q']:
                                    if (check_r == r or check_c == c) and not (check_r == r and check_c == c):
                                        black_attackers_on_white_king += 0.5
        
        score -= black_attackers_on_white_king * ATTACK_KING_ZONE_BONUS

    # 7. Tempo bonus for side to move (slight advantage)
    score += 10 if gamestate.current_turn == 'w' else -10

    # Add a small random element to avoid identical choices? (Optional)
    # score += random.uniform(-0.1, 0.1)

    return score


# --- Quiescence Search ---
def get_noisy_moves(gamestate: GameState):
    """ Get captures, promotions, maybe checks? """
    moves = gamestate.get_all_legal_moves()
    noisy_moves = []
    for move in moves:
        try:
            # Drop moves are not inherently captures; skip them in quiescence
            if isinstance(move, tuple) and move and move[0] == 'drop':
                continue
            # Normal move: ((r1,f1),(r2,f2), promotion)
            (start_r, start_c), (end_r, end_c), promotion = move
            is_capture = gamestate.board[end_r][end_c] != EMPTY_SQUARE
            is_promotion = promotion is not None
            if is_capture or is_promotion:
                noisy_moves.append(move)
        except Exception:
            # If move format is unexpected, skip it
            continue
    return noisy_moves


def quiescence_search(gamestate: GameState, alpha, beta, depth):
    """ Search only captures and promotions until a quiet position is reached. """
    if gamestate.checkmate or gamestate.stalemate:
         return evaluate_position(gamestate)

    stand_pat_score = evaluate_position(gamestate)

    if depth == 0:
        return stand_pat_score

    # Delta Pruning (simple version): If current eval + big margin < alpha, prune
    # BIG_MARGIN = PIECE_VALUES['R'] # e.g., value of a rook
    # if stand_pat_score < alpha - BIG_MARGIN:
    #      return alpha

    if gamestate.current_turn == 'w': # Maximizing
        if stand_pat_score >= beta:
            return beta # Fail high
        alpha = max(alpha, stand_pat_score)

        noisy_moves = get_noisy_moves(gamestate)
        # Sort noisy moves? MVV-LVA might be good here too.
        noisy_moves.sort(key=lambda m: mvv_lva_score(gamestate, m), reverse=True)

        for move in noisy_moves:
            next_state = copy.deepcopy(gamestate)
            move_made = next_state.make_move(move, is_check_game_over=False)
            if not move_made: continue
            if next_state.needs_promotion_choice:
                 best_prom_piece = 'Q'
                 if 'Q' not in PROMOTION_PIECES_WHITE_STR and 'R' in PROMOTION_PIECES_WHITE_STR: best_prom_piece = 'R'
                 if not next_state.complete_promotion(best_prom_piece): continue

            score = quiescence_search(next_state, alpha, beta, depth - 1)
            alpha = max(alpha, score)
            if alpha >= beta:
                return beta # Fail high (cutoff)
        return alpha # Best score found for maximizing player

    else: # Minimizing
        if stand_pat_score <= alpha:
            return alpha # Fail low
        beta = min(beta, stand_pat_score)

        noisy_moves = get_noisy_moves(gamestate)
        noisy_moves.sort(key=lambda m: mvv_lva_score(gamestate, m), reverse=True)

        for move in noisy_moves:
            next_state = copy.deepcopy(gamestate)
            move_made = next_state.make_move(move, is_check_game_over=False)
            if not move_made: continue
            if next_state.needs_promotion_choice:
                 best_prom_piece = 'q'
                 if 'q' not in PROMOTION_PIECES_BLACK_STR and 'r' in PROMOTION_PIECES_BLACK_STR: best_prom_piece = 'r'
                 if not next_state.complete_promotion(best_prom_piece): continue

            score = quiescence_search(next_state, alpha, beta, depth - 1)
            beta = min(beta, score)
            if alpha >= beta:
                return alpha # Fail low (cutoff)
        return beta # Best score found for minimizing player


# --- MVV-LVA Heuristic (IMPROVED) ---
def mvv_lva_score(gamestate, move):
    """ 
    Assigns a score for move ordering based on:
    1. Checks (highest priority)
    2. Captures (MVV-LVA)
    3. Attacks on enemy king zone
    4. Center control
    5. Promotions
    6. History heuristic
    """
    score = 0
    
    # Handle normal board moves: ((r1,f1),(r2,f2), promotion)
    if isinstance(move, tuple) and move and move[0] != 'drop':
        (start_r, start_c), (end_r, end_c), promotion = move
        aggressor_piece = gamestate.board[start_r][start_c]
        victim_piece = gamestate.board[end_r][end_c]
        
        if aggressor_piece == EMPTY_SQUARE:
            return 0
        
        aggressor_value = PIECE_VALUES.get(aggressor_piece.upper(), 0)
        piece_color = get_piece_color(aggressor_piece)
        
        # 1. CAPTURES - MVV-LVA
        if victim_piece != EMPTY_SQUARE:
            victim_value = PIECE_VALUES.get(victim_piece.upper(), 0)
            # High score for capturing valuable piece with less valuable one
            score += (victim_value * 10) - aggressor_value
        
        # 2. PROMOTION
        if promotion:
            score += 900
        
        # 3. CHECKS (simulate move and check if opponent in check)
        # This is expensive, so we do a quick heuristic instead:
        # If moving piece attacks opponent king square
        enemy_color = get_opposite_color(piece_color)
        enemy_king_pos = gamestate.king_pos.get(enemy_color)
        if enemy_king_pos:
            ek_r, ek_c = enemy_king_pos
            # Check if destination is adjacent to enemy king (potential check)
            if max(abs(end_r - ek_r), abs(end_c - ek_c)) <= 2:
                score += 500  # Likely attacking king zone
        
        # 4. CENTER CONTROL
        if (end_r, end_c) in CENTER_SQUARES:
            score += 30
        
        # 5. PIECE DEVELOPMENT (move from back rank)
        if piece_color == 'w' and start_r == 5 and end_r < 5:
            score += 20  # White developing
        elif piece_color == 'b' and start_r == 0 and end_r > 0:
            score += 20  # Black developing
        
        # 6. HISTORY HEURISTIC
        move_repr = repr(move)
        history_bonus = history_scores.get(move_repr, 0)
        score += history_bonus
        
        return score
    
    # Drops: strategic placement
    if isinstance(move, tuple) and move and move[0] == 'drop':
        piece_code = move[1]  # e.g., 'wN'
        if isinstance(piece_code, str) and len(piece_code) == 2:
            drop_r, drop_c = move[2]
            piece_type = piece_code[1].upper()
            piece_color = piece_code[0]
            
            base_score = HAND_PIECE_VALUES.get(piece_type, 0) // 10
            
            # DROP IN CENTER
            if (drop_r, drop_c) in CENTER_SQUARES:
                base_score += 50
            
            # DROP NEAR ENEMY KING
            enemy_color = get_opposite_color(piece_color)
            enemy_king_pos = gamestate.king_pos.get(enemy_color)
            if enemy_king_pos:
                ek_r, ek_c = enemy_king_pos
                if max(abs(drop_r - ek_r), abs(drop_c - ek_c)) <= 2:
                    base_score += 100  # Drop attacking king!
            
            move_repr = repr(move)
            history_bonus = history_scores.get(move_repr, 0)
            return base_score + history_bonus
        return 0
    
    return 0 # Unknown format


# --- Minimax with Alpha-Beta (Simplified - No TT logic inside) ---
def minimax_alpha_beta(gamestate: GameState, depth, alpha, beta, maximizing_player):
    """
    Performs minimax search with alpha-beta pruning.
    Does NOT interact with the move cache directly.
    Returns: (score, best_move_found_at_this_node)
    """
    if depth == 0 or gamestate.checkmate or gamestate.stalemate:
        q_score = quiescence_search(gamestate, alpha, beta, MAX_QUIESCENCE_DEPTH)
        return q_score, None

    # Transposition Table probe
    pos_hash = get_position_hash(gamestate)
    tt_entry = tt.get(pos_hash)

    legal_moves = gamestate.get_all_legal_moves()
    if not legal_moves:
        return evaluate_position(gamestate), None

    # TT-based alpha/beta tightening
    if tt_entry and tt_entry.get('depth', -1) >= depth:
        if tt_entry['flag'] == 'EXACT':
            return tt_entry['score'], tt_entry.get('best_move')
        elif tt_entry['flag'] == 'LOWERBOUND':
            alpha = max(alpha, tt_entry['score'])
        elif tt_entry['flag'] == 'UPPERBOUND':
            beta = min(beta, tt_entry['score'])
        if alpha >= beta:
            return tt_entry['score'], tt_entry.get('best_move')

    # Advanced move ordering: TT best-move first, then killer moves, then MVV-LVA + history
    tt_best = tt_entry.get('best_move') if tt_entry else None
    killers = killer_moves.get(depth, [])
    
    def move_order_score(move):
        if tt_best is not None and move == tt_best:
            return 1000000  # TT move first
        elif move in killers:
            return 50000 + (100 - killers.index(move))  # Killer moves next
        else:
            return mvv_lva_score(gamestate, move)  # MVV-LVA + history
    
    legal_moves.sort(key=move_order_score, reverse=True)

    best_move_for_depth = None
    orig_alpha, orig_beta = alpha, beta
    if maximizing_player: # White
        max_eval = -float('inf')
        for move in legal_moves:
            next_state = copy.deepcopy(gamestate)
            move_made = next_state.make_move(move, is_check_game_over=False)
            if not move_made: continue
            if next_state.needs_promotion_choice:
                 best_prom_piece = 'Q' # Auto-promote to Queen (or Rook)
                 if 'Q' not in PROMOTION_PIECES_WHITE_STR and 'R' in PROMOTION_PIECES_WHITE_STR: best_prom_piece = 'R'
                 if not next_state.complete_promotion(best_prom_piece): continue

            eval_score, _ = minimax_alpha_beta(next_state, depth - 1, alpha, beta, False)

            if eval_score > max_eval:
                max_eval = eval_score
                best_move_for_depth = move # Store the move that led to max_eval
            alpha = max(alpha, eval_score)
            if alpha >= beta:
                # Update killer moves and history for cutoff move
                if best_move_for_depth and alpha >= beta:
                    move_repr = repr(best_move_for_depth)
                    history_scores[move_repr] = history_scores.get(move_repr, 0) + depth * depth
                    if depth not in killer_moves:
                        killer_moves[depth] = []
                    if best_move_for_depth not in killer_moves[depth]:
                        killer_moves[depth].insert(0, best_move_for_depth)
                        if len(killer_moves[depth]) > 2:
                            killer_moves[depth].pop()
                break # Beta cutoff
        final_score = max_eval
    else: # Black (Minimizing)
        min_eval = float('inf')
        for move in legal_moves:
            next_state = copy.deepcopy(gamestate)
            move_made = next_state.make_move(move, is_check_game_over=False)
            if not move_made: continue
            if next_state.needs_promotion_choice:
                 best_prom_piece = 'q' # Auto-promote to queen (or rook)
                 if 'q' not in PROMOTION_PIECES_BLACK_STR and 'r' in PROMOTION_PIECES_BLACK_STR: best_prom_piece = 'r'
                 if not next_state.complete_promotion(best_prom_piece): continue

            eval_score, _ = minimax_alpha_beta(next_state, depth - 1, alpha, beta, True)

            if eval_score < min_eval:
                min_eval = eval_score
                best_move_for_depth = move # Store the move that led to min_eval
            beta = min(beta, eval_score)
            if alpha >= beta:
                # Update killer moves and history for cutoff move
                if best_move_for_depth and alpha >= beta:
                    move_repr = repr(best_move_for_depth)
                    history_scores[move_repr] = history_scores.get(move_repr, 0) + depth * depth
                    if depth not in killer_moves:
                        killer_moves[depth] = []
                    if best_move_for_depth not in killer_moves[depth]:
                        killer_moves[depth].insert(0, best_move_for_depth)
                        if len(killer_moves[depth]) > 2:
                            killer_moves[depth].pop()
                break # Alpha cutoff
        final_score = min_eval

    # Store to TT
    flag = 'EXACT'
    if final_score <= orig_alpha:
        flag = 'UPPERBOUND'
    elif final_score >= orig_beta:
        flag = 'LOWERBOUND'
    tt[pos_hash] = {
        'depth': depth,
        'score': final_score,
        'flag': flag,
        'best_move': best_move_for_depth,
    }

    return final_score, best_move_for_depth


# --- Worker Function (Simplified - No TT return) ---
def evaluate_move_worker(args):
    """
    Worker function for parallel search. Evaluates a single move.
    Returns only the score.
    """
    move, depth, alpha, beta, is_maximizing, gs_pickle_dump = args
    try:
        gamestate_copy = pickle.loads(gs_pickle_dump)

        move_made = gamestate_copy.make_move(move, is_check_game_over=False)
        if not move_made:
            return -float('inf') if is_maximizing else float('inf')

        if gamestate_copy.needs_promotion_choice:
            prom_piece = ''
            if not is_maximizing: prom_piece = 'q' if 'q' in PROMOTION_PIECES_BLACK_STR else 'r'
            else: prom_piece = 'Q' if 'Q' in PROMOTION_PIECES_WHITE_STR else 'R'
            if not gamestate_copy.complete_promotion(prom_piece):
                 print(f"Error completing auto-promotion in worker for {move}")
                 return -float('inf') if is_maximizing else float('inf')

        # Call the simplified minimax
        score, _ = minimax_alpha_beta(gamestate_copy, depth - 1, alpha, beta, not is_maximizing)
        return score

    except Exception as e:
        # Log detailed error including the move being processed
        # traceback.print_exc() # Uncomment for full traceback in worker logs
        print(f"Error in worker process for move {move}: {type(e).__name__} - {e}")
        return -float('inf') if is_maximizing else float('inf')


# --- Main AI Function (Using Iterative Deepening + Cache) ---
def find_best_move(gamestate: GameState, depth=6):
    """
    Finds the best move using ITERATIVE DEEPENING with move cache.
    Searches depth 1, 2, 3... up to target depth.
    Uses results from shallower searches to improve move ordering.
    """
    print(f"AI ({gamestate.current_turn}) thinking with iterative deepening up to depth {depth}...")
    start_time = time.time()
    is_maximizing = (gamestate.current_turn == 'w')
    global move_cache # Access the global cache

    if gamestate.needs_promotion_choice:
        print("AI Error: Cannot find move, waiting for promotion choice.")
        return None

    # --- Check Move Cache (with depth) ---
    pos_hash = get_position_hash(gamestate)
    cache_key = (pos_hash, depth)  # Include depth in cache key
    cached_move_repr = move_cache.get(cache_key)
    if cached_move_repr:
        try:
            # Convert repr back to move tuple/list structure using eval
            # WARNING: eval() is a security risk if DB content is not trusted.
            # Consider safer alternatives like custom serialization/deserialization
            # or storing moves in a JSON-compatible format if needed.
            cached_move = eval(cached_move_repr)

            # Validate if the cached move is still legal
            # This requires GameState to have an 'is_move_legal' method
            if hasattr(gamestate, 'is_move_legal') and gamestate.is_move_legal(cached_move):
                 print(f"[CACHE HIT] Hash {pos_hash} Depth {depth}: Found valid move {cached_move} in cache.")
                 end_time = time.time()
                 print(f"AI ({gamestate.current_turn}) finished thinking (CACHE HIT) in {end_time - start_time:.2f}s.")
                 return cached_move
            elif not hasattr(gamestate, 'is_move_legal'):
                 print(f"[CACHE WARN] Hash {pos_hash} Depth {depth}: Cannot validate cached move {cached_move} as GameState lacks 'is_move_legal'. Using cached move.")
                 # If validation isn't possible, maybe return it anyway? Or force recalculation?
                 # For now, let's return it assuming it's likely still valid.
                 end_time = time.time()
                 print(f"AI ({gamestate.current_turn}) finished thinking (CACHE HIT - UNVALIDATED) in {end_time - start_time:.2f}s.")
                 return cached_move
            else:
                 print(f"[CACHE WARN] Hash {pos_hash} Depth {depth}: Cached move {cached_move} is no longer legal. Recalculating.")
                 # Optionally remove the invalid entry
                 # del move_cache[pos_hash]
        except Exception as e:
            print(f"[CACHE ERROR] Hash {pos_hash} Depth {depth}: Error processing cached move '{cached_move_repr}': {e}. Recalculating.")
            # Remove potentially corrupt entry
            if cache_key in move_cache: del move_cache[cache_key]


    # --- If not in cache or invalid, perform search ---
    print(f"[CACHE MISS] Hash {pos_hash} Depth {depth}: Position not in cache or invalid. Starting search...")
    best_score = -float('inf') if is_maximizing else float('inf')
    best_move = None

    # Need a copy to generate moves without altering the original state passed to minimax/workers
    gs_copy_for_moves = copy.deepcopy(gamestate)
    legal_moves = gs_copy_for_moves.get_all_legal_moves()

    if not legal_moves:
        print("AI Error: No legal moves available!")
        # Attempt to evaluate terminal state anyway?
        score = evaluate_position(gamestate)
        print(f"  Terminal state evaluation: {score}")
        return None # No move to make

    if len(legal_moves) == 1:
        print("Only one legal move available.")
        best_move = copy.deepcopy(legal_moves[0])
        # Store this single move in the cache (with depth)
        cache_key = (pos_hash, depth)
        move_cache[cache_key] = repr(best_move)
        print(f"[CACHE STORE] Hash {pos_hash} Depth {depth}: Stored single legal move {repr(best_move)}.")
        end_time = time.time()
        print(f"AI ({gamestate.current_turn}) finished thinking (Single Move) in {end_time - start_time:.2f}s.")
        return best_move


    try:
        # === ITERATIVE DEEPENING ===
        # Start from depth 1 and go up to target depth
        # Each iteration uses results from previous to improve move ordering
        best_move = None
        best_score = 0
        
        for current_depth in range(1, depth + 1):
            iteration_start = time.time()
            print(f"  [ID] Searching depth {current_depth}...")
            
            # Check cache for this specific depth first
            iter_cache_key = (pos_hash, current_depth)
            cached_for_depth = move_cache.get(iter_cache_key)
            
            if cached_for_depth and current_depth == depth:
                # Found exact depth in cache, use it
                try:
                    cached_move = eval(cached_for_depth)
                    if hasattr(gamestate, 'is_move_legal') and gamestate.is_move_legal(cached_move):
                        print(f"  [ID] Depth {current_depth} cached, using it.")
                        best_move = cached_move
                        break  # We have the answer for target depth
                except:
                    pass  # Cache error, continue with search
            
            # Search at current depth
            iter_best_move, iter_best_score = minimax(gamestate, current_depth, move_cache)
            
            if iter_best_move:
                best_move = iter_best_move
                best_score = iter_best_score
                
                # Cache this result
                iter_cache_key = (pos_hash, current_depth)
                move_cache[iter_cache_key] = repr(best_move)
                
                iteration_time = time.time() - iteration_start
                print(f"  [ID] Depth {current_depth} complete in {iteration_time:.2f}s, best: {format_move_for_print(best_move)}, score: {best_score:.1f}")
            else:
                print(f"  [ID] Depth {current_depth} failed to find move")
                break
            
            # Check if we found mate - no need to search deeper
            if abs(best_score) >= CHECKMATE_SCORE * 0.9:
                print(f"  [ID] Mate found at depth {current_depth}, stopping search")
                break

    except Exception as e:
        print(f"An error occurred during AI move calculation: {e}")
        traceback.print_exc()
        print("Selecting best move found so far or random as fallback.")
        if not best_move:
            best_move = random.choice(legal_moves) if legal_moves else None
            best_score = 0


    end_time = time.time()
    if best_move:
        print(f"AI ({gamestate.current_turn}) finished thinking in {end_time - start_time:.2f}s.")
        print(f"  Chosen Move: {best_move}, Score: {best_score:.2f}")
        # --- Store result in Move Cache (with depth) ---
        # Use repr() for storing the move; requires eval() on load.
        cache_key = (pos_hash, depth)
        move_cache[cache_key] = repr(best_move)
        print(f"[CACHE STORE] Hash {pos_hash} Depth {depth}: Stored move {repr(best_move)}.")
    else:
        # This case should ideally not happen if there are legal moves
        print(f"AI ({gamestate.current_turn}) could not find a best move after {end_time - start_time:.2f}s. Legal moves: {legal_moves}")

    return best_move

# --- Add is_move_legal stub if not present in GameState ---
# This is crucial for cache validation. Add a basic stub if your GameState lacks it.
# Ensure GameState is defined before patching
if 'GameState' in globals() and not hasattr(GameState, 'is_move_legal'):
     print("Patching GameState with basic is_move_legal stub for cache validation.")
     def is_move_legal_stub(self, move):
         # Basic check: generate all legal moves and see if the move is among them.
         # This might be slow but ensures correctness for the cache.
         # Make sure get_all_legal_moves doesn't modify the state.
         try:
            return move in self.get_all_legal_moves()
         except Exception as e:
             print(f"Error during is_move_legal_stub for move {move}: {e}")
             return False # Assume illegal on error?
     GameState.is_move_legal = is_move_legal_stub

# --- Initial DB Setup Call ---
# It's generally better to explicitly call load/save in main.py
# but ensuring setup runs once might be useful.
# setup_db() # Let load_move_cache_from_db handle this.

def minimax(gamestate: GameState, depth, move_cache):
    """Starts the parallel minimax search."""
    try:
        start_time_minimax = time.time()
        legal_moves = gamestate.get_all_legal_moves()
        if not legal_moves:
            return None, 0 # Or appropriate score for checkmate/stalemate?

        num_workers = NUM_WORKERS if NUM_WORKERS else multiprocessing.cpu_count()
        print(f"Using {num_workers} worker processes for depth {depth} search.")
        pool = multiprocessing.Pool(processes=num_workers)
        manager = multiprocessing.Manager()
        # Shared cache for workers (read-only during parallel phase is safer)
        # For simplicity, we pass a copy or don't share the writeable cache here.
        # Workers will use their own cache logic based on the passed state.
        shared_move_cache = manager.dict(move_cache) # Pass current cache state

        tasks = []
        for move in legal_moves:
            # Create a deep copy for each worker to avoid interference
            # Use pickle for full serialization to ensure complete independence
            try:
                gamestate_copy = pickle.loads(pickle.dumps(gamestate))
            except:
                # Fallback to regular deepcopy if pickle fails
                gamestate_copy = gamestate.copy()
            # Maximizing player is determined by the turn *before* the move is made
            maximizing_player = (gamestate.current_turn == 'w')
            tasks.append((move, gamestate_copy, depth, -float('inf'), float('inf'), maximizing_player, shared_move_cache))

        results = pool.starmap(_minimax_worker, tasks)
        pool.close()
        pool.join()

        all_results = []
        for result in results:
            if result is None: continue # Skip if worker failed badly
            move, score = result
            if score is not None: # Check if worker returned a valid score
                all_results.append((move, score))

        if not all_results:
            # ... (Existing handling for no results) ...
            print("[WARN] Minimax main: No valid scores returned from workers or no legal moves?")
            if gamestate.checkmate: return None, -CHECKMATE_SCORE if gamestate.current_turn == 'w' else CHECKMATE_SCORE
            if gamestate.stalemate: return None, STALEMATE_SCORE
            legal_moves_fallback = gamestate.get_all_legal_moves() # Re-check
            if not legal_moves_fallback: return None, STALEMATE_SCORE if not gamestate.is_in_check(gamestate.current_turn) else (-CHECKMATE_SCORE if gamestate.current_turn == 'w' else CHECKMATE_SCORE)
            return random.choice(legal_moves_fallback), -float('inf') # Fallback random, bad score


        # --- <<<< ПРИОРИТЕТ МАТА >>>> --- 
        current_player_color = gamestate.current_turn
        mating_score = CHECKMATE_SCORE if current_player_color == 'w' else -CHECKMATE_SCORE
        best_mate_move = None

        for move, score in all_results:
            # Check for exact mating score
            if score == mating_score:
                best_mate_move = move
                break # Found the best possible outcome

        if best_mate_move is not None:
            return best_mate_move, mating_score # Return immediately
        # --- <<<< КОНЕЦ ПРИОРИТЕТА МАТА >>>> ---

        # Find best move based on scores (standard minimax logic if no mate found)
        best_move = all_results[0][0] # Default
        if current_player_color == 'w': # Maximizing player
            best_score = -float('inf')
            for move, score in all_results:
                if score > best_score:
                    best_score = score
                    best_move = move
        else: # Minimizing player
            best_score = float('inf')
            for move, score in all_results:
                if score < best_score:
                    best_score = score
                    best_move = move

        # print(f"Minimax calculation took: {time.time() - start_time_minimax:.2f}s")
        return best_move, best_score

    except Exception as e:
        print(f"Error in minimax function: {e}")
        traceback.print_exc()
        # Fallback: return a random move if possible
        try:
             moves = gamestate.get_all_legal_moves()
             return random.choice(moves) if moves else None, 0
        except:
             return None, 0 # Ultimate fallback

def _minimax_worker(move, gamestate_copy, depth, alpha, beta, maximizing_player, move_cache):
    """Minimax function for a single move, executed by a worker process."""
    # print(f"Worker evaluating move: {move}, Depth: {depth}, Max: {maximizing_player}")
    start_time = time.time()
    try:
        # Make the move for which this worker is responsible
        if not gamestate_copy.make_move(move, is_check_game_over=False):
            # Return a bad score if the initial move is illegal (should not happen)
            return move, -CHECKMATE_SCORE if maximizing_player else CHECKMATE_SCORE

        # --- NO CACHE CHECK HERE - Cache check is done inside recursive calls --- 
        # current_hash = get_position_hash(gamestate_copy)
        # ... cache check logic removed ...

        # Call the recursive helper starting from the state AFTER the move
        # The next level alternates the player
        score = _minimax_recursive(gamestate_copy, depth - 1, alpha, beta, not maximizing_player)

        # --- NO CACHE STORE HERE - Cache is managed by main process --- 
        # gamestate_copy.undo_move() # Backtrack is done implicitly by returning

        # The score returned by _minimax_recursive is the evaluation of the position
        # from the perspective of the player who just moved (the maximizing_player here).
        return move, score
    except Exception as e:
        # ... (existing error handling) ...
        try: move_str = format_move_for_print(move)
        except: move_str = str(move)
        print(f"Error in worker process for move {move_str}: {type(e).__name__} - {e}")
        error_score = -CHECKMATE_SCORE if maximizing_player else CHECKMATE_SCORE # Assign worst score
        return move, error_score

def _minimax_recursive(gamestate: GameState, depth, alpha, beta, maximizing_player):
    """Recursive helper for minimax with alpha-beta pruning and mate priority."""

    # --- Terminal State Check --- (Check BEFORE depth limit)
    legal_moves = gamestate.get_all_legal_moves() # Get moves for the player whose turn it IS
    if not legal_moves:
        # Need is_in_check method from GameState
        if hasattr(gamestate, 'is_in_check') and gamestate.is_in_check(gamestate.current_turn):
            # Checkmate for the current player. Return score from opponent's view.
            return -CHECKMATE_SCORE if gamestate.current_turn == 'w' else CHECKMATE_SCORE
        else:
            # Stalemate
            return STALEMATE_SCORE

    # --- Depth Limit Check --- 
    if depth == 0:
        # Evaluate quiescent state
        return _quiescence_search(gamestate, alpha, beta, maximizing_player, MAX_QUIESCENCE_DEPTH)

    # --- Move Iteration with Mate Priority (using fast copy instead of undo) --- 
    if maximizing_player: # White trying to maximize
        max_eval = -float('inf')
        for move in legal_moves:
            # Create a fast copy for this branch to avoid needing undo
            next_state = gamestate.fast_copy_for_simulation()
            if not next_state.make_move(move, is_check_game_over=False): continue # Skip illegal moves
            
            eval_score = _minimax_recursive(next_state, depth - 1, alpha, beta, False) # Recursive call for Black
            # No undo needed - we used a copy

            # <<< Mate Check >>>
            if eval_score >= CHECKMATE_SCORE: 
                # This move leads to White checkmating Black
                return CHECKMATE_SCORE # Return mate score immediately
            
            max_eval = max(max_eval, eval_score)
            alpha = max(alpha, eval_score)
            if beta <= alpha:
                break # Beta cut-off
        return max_eval

    else: # Minimizing player (Black trying to minimize)
        min_eval = float('inf')
        for move in legal_moves:
            # Create a fast copy for this branch to avoid needing undo
            next_state = gamestate.fast_copy_for_simulation()
            if not next_state.make_move(move, is_check_game_over=False): continue
            
            eval_score = _minimax_recursive(next_state, depth - 1, alpha, beta, True) # Recursive call for White
            # No undo needed - we used a copy

            # <<< Mate Check >>>
            if eval_score <= -CHECKMATE_SCORE:
                 # This move leads to Black checkmating White
                 return -CHECKMATE_SCORE # Return mate score immediately
            
            min_eval = min(min_eval, eval_score)
            beta = min(beta, eval_score)
            if beta <= alpha:
                break # Alpha cut-off
        return min_eval

# --- Quiescence Search ---
def _quiescence_search(gamestate: GameState, alpha, beta, maximizing_player, depth):
    """Search only 'noisy' moves (captures, promotions, checks) to stabilize evaluation."""

    # Evaluate the standing position (score if no noisy moves are made)
    stand_pat_score = evaluate_position(gamestate)

    # --- Terminal Check within Quiescence --- 
    legal_moves_q = gamestate.get_all_legal_moves()
    if not legal_moves_q:
         if hasattr(gamestate, 'is_in_check') and gamestate.is_in_check(gamestate.current_turn):
             return -CHECKMATE_SCORE if gamestate.current_turn == 'w' else CHECKMATE_SCORE
         else:
             return STALEMATE_SCORE
             
    if depth == 0:
        return stand_pat_score # Depth limit reached

    if maximizing_player:
        if stand_pat_score >= beta:
            return beta # Fail-high (score is already too good for maximizing player)
        alpha = max(alpha, stand_pat_score)

        noisy_moves = get_noisy_moves(gamestate)
        if not noisy_moves: return stand_pat_score # No noisy moves, return static eval
        
        for move in noisy_moves:
             # Use fast copy instead of undo
             next_state = gamestate.fast_copy_for_simulation()
             if not next_state.make_move(move, is_check_game_over=False): continue
             score = _quiescence_search(next_state, alpha, beta, False, depth - 1)
             # No undo needed
             
             # <<< Mate Check >>>
             if score >= CHECKMATE_SCORE:
                 return CHECKMATE_SCORE # Return mate immediately
                 
             alpha = max(alpha, score)
             if alpha >= beta:
                 break # Beta cut-off
        return alpha # Return the best score found for maximizing player

    else: # Minimizing player
        if stand_pat_score <= alpha:
            return alpha # Fail-low (score is already too good for minimizing player)
        beta = min(beta, stand_pat_score)

        noisy_moves = get_noisy_moves(gamestate)
        if not noisy_moves: return stand_pat_score
        
        for move in noisy_moves:
             # Use fast copy instead of undo
             next_state = gamestate.fast_copy_for_simulation()
             if not next_state.make_move(move, is_check_game_over=False): continue
             score = _quiescence_search(next_state, alpha, beta, True, depth - 1)
             # No undo needed
             
             # <<< Mate Check >>>
             if score <= -CHECKMATE_SCORE:
                 return -CHECKMATE_SCORE # Return mate immediately
                 
             beta = min(beta, score)
             if beta <= alpha:
                 break # Alpha cut-off
        return beta # Return the best score found for minimizing player

# Placeholder/Helper functions needed by find_best_move's cache logic
def parse_move_string(move_str):
    """Placeholder: Converts move string (e.g., 'e2e4', 'N@c3') back to internal move format."""
    # This needs proper implementation based on your move format
    # Example for simple moves:
    try:
        if '@' in move_str: # Drop move like P@e4
            piece_char, sq_str = move_str.split('@')
            target_sq = algebraic_to_coords(sq_str)
            if target_sq:
                return ('drop', piece_char, target_sq)
        elif len(move_str) >= 4:
             start_sq_str = move_str[:2]
             end_sq_str = move_str[2:4]
             promotion_char = move_str[4] if len(move_str) == 5 else None
             start_sq = algebraic_to_coords(start_sq_str)
             end_sq = algebraic_to_coords(end_sq_str)
             if start_sq and end_sq:
                  return (start_sq, end_sq, promotion_char)
    except Exception as e:
        print(f"[ERROR] Failed to parse move string '{move_str}': {e}")
    return None

def is_move_still_legal(gamestate, move):
    """Placeholder: Checks if a move is legal in the current gamestate."""
    # This should ideally use the GameState's validation or check against get_all_legal_moves
    try:
        return move in gamestate.get_all_legal_moves()
    except Exception as e:
        print(f"[ERROR] Failed to check legality for move {move}: {e}")
        return False # Assume illegal if check fails
# --- End Placeholder --- 