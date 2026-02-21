# --- Imports and Constants ---
import sqlite3
import time
from datetime import datetime
import copy
import random
import math
import concurrent.futures
import pickle # For deep copying complex objects like GameState

import hashlib
import traceback
from utils import format_move_for_print, algebraic_to_coords, get_piece_color, get_opposite_color, is_on_board
from config import BOARD_SIZE

# Multiprocessing start method handling is done via concurrent.futures context


 

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
OPEN_FILE_ROOK_BONUS = 30 # Bonus for rook on a file with no friendly pawns
SEMI_OPEN_FILE_ROOK_BONUS = 15 # Bonus for rook on a file with no enemy pawns blocked

# King safety: pawn shield is critical in crazyhouse (opponents can drop near your king)
PAWN_SHIELD_BONUS = 40  # per pawn in front of king
EXPOSED_KING_PENALTY = 80  # penalty when no pawn shield and opponent has drops
BISHOP_PAIR_BONUS = 50  # having both bishops on 6x6

# Passed pawn bonus by distance to promotion (exponential scaling for 6x6 board)
# Index = steps remaining to promotion rank (1=one step away, 4=just left start)
PASSED_PAWN_BONUS = {1: 500, 2: 200, 3: 80, 4: 30}
# Extra bonus for a passed pawn with no piece blocking its path (truly open road)
UNSTOPPABLE_PAWN_BONUS = {1: 300, 2: 120, 3: 40}
# Penalty for a pawn blocked by any piece directly ahead
BLOCKED_PAWN_PENALTY = 25
# Bonus for having pawns in hand that could be dropped near promotion
DROP_PAWN_PROMO_BONUS = 250

# --- Transposition Table (Now a simple Move Cache) ---
# Stores: {(position_hash, depth): best_move_repr} - includes depth to avoid shallow cached moves
move_cache = {}

# --- Transposition Table for Alpha-Beta ---
# key: position hash; value: dict(depth=int, score=float, flag=str('EXACT'|'LOWERBOUND'|'UPPERBOUND'), best_move=move)
tt = {}

# Depth threshold: depths below this use single-threaded (to build TT), depths >= this use parallel workers
PARALLEL_DEPTH_THRESHOLD = 4

# --- Killer Moves and History Heuristic ---
killer_moves = {}  # {depth: [move1, move2]}
history_scores = {}  # {move_repr: score}

# --- Database Handling for Move Cache ---
DB_PATH = "move_cache.db" # Renamed DB file

# --- Configuration ---
CACHE_ENABLED = True
# How many worker processes to use for parallel search
# Use None to let multiprocessing decide (usually number of CPU cores)
NUM_WORKERS = 7  # Оставляем 1 core свободным

# --- Training Time Configuration ---
# is_training_time removed as it is handled by the main loop


# --- Constants ---
CHECKMATE_SCORE = 1000000 # Large score for checkmate
STALEMATE_SCORE = 0       # Score for stalemate
MAX_QUIESCENCE_DEPTH = 4  # Limit quiescence search depth (increased for better tactics)

def setup_db():
    """Creates the move_cache table if it doesn't exist, migrates old schema if needed."""
    try:
        conn = sqlite3.connect(DB_PATH) # No timeout needed for simple ops
        cursor = conn.cursor()
        
        # Check if table exists and has correct schema
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='move_cache'")
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            # Check if depth column exists
            cursor.execute("PRAGMA table_info(move_cache)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'depth' not in columns:
                print(f"Old schema detected in {DB_PATH}, migrating to new schema with depth column...")
                cursor.execute("DROP TABLE move_cache")
                conn.commit()
        
        # Schema with depth tracking: (hash, depth) -> best_move
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS move_cache (
                hash TEXT NOT NULL,
                depth INTEGER NOT NULL,
                best_move_repr TEXT NOT NULL,
                PRIMARY KEY (hash, depth)
            )
        ''')
        conn.commit()
        conn.close()
        print(f"Database {DB_PATH} checked/created successfully.")
    except Exception as e:
        print(f"Error setting up database: {e}")

def load_move_cache_from_db():
    """Loads the move cache from the SQLite database with depth tracking."""
    global move_cache
    setup_db() # Ensure DB and table exist
    loaded_count = 0
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT hash, depth, best_move_repr FROM move_cache")
        rows = cursor.fetchall()
        # Load with (hash, depth) tuple keys
        move_cache = {(row[0], row[1]): row[2] for row in rows}
        loaded_count = len(move_cache)
        conn.close()
        print(f"Loaded {loaded_count} entries from move cache database.")
    except Exception as e:
        print(f"Error loading move cache from database: {e}")
        move_cache = {} # Start with empty cache on error

def save_move_cache_to_db(cache_to_save):
    """Saves the current move cache to the SQLite database with depth tracking."""
    if not cache_to_save:
        print(f"Move cache is empty, nothing to save.")
        return
    
    print(f"Attempting to save {len(cache_to_save)} cache entries...")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # Convert (hash, depth) tuple keys to separate columns
        entries_to_save = [(hash_val, depth, move_repr) for (hash_val, depth), move_repr in cache_to_save.items()]
        cursor.executemany("INSERT OR REPLACE INTO move_cache (hash, depth, best_move_repr) VALUES (?, ?, ?)", entries_to_save)
        conn.commit()
        conn.close()
        print(f"Successfully saved {len(entries_to_save)} entries to move cache database.")
    except Exception as e:
        print(f"Error saving move cache to database: {e}")


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
        promoted = tuple(sorted(getattr(gamestate, 'promoted_pieces', set())))
        state_tuple = (board_tuple, white_hand_tuple, black_hand_tuple, turn, en_passant, castling, promoted)

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

    # 2. Mobility proxy (cheap: count pieces with at least one adjacent empty square)
    white_mobile = 0
    black_mobile = 0
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            piece = gamestate.board[r][c]
            if piece == EMPTY_SQUARE or piece.upper() == 'K':
                continue
            has_adjacent_empty = False
            for dr, dc in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and gamestate.board[nr][nc] == EMPTY_SQUARE:
                    has_adjacent_empty = True
                    break
            if has_adjacent_empty:
                if get_piece_color(piece) == 'w':
                    white_mobile += 1
                else:
                    black_mobile += 1
    score += (white_mobile - black_mobile) * MOBILITY_BONUS

    # 3. Pawn Structure (very simple: connected pawns)
    for r, c in white_pawns:
        # Check adjacent files for friendly pawns
        if c > 0 and gamestate.board[r][c-1] == 'P': score += PAWN_STRUCTURE_BONUS
        if c < BOARD_SIZE-1 and gamestate.board[r][c+1] == 'P': score += PAWN_STRUCTURE_BONUS
        # Blocked pawn penalty
        if r > 0 and gamestate.board[r-1][c] != EMPTY_SQUARE:
            score -= BLOCKED_PAWN_PENALTY
        # Add bonus for passed pawns (no opponent pawns ahead in this or adjacent files) - simplified
        is_passed = True
        path_clear = True  # no pieces at all on the file ahead
        for scan_r in range(r - 1, -1, -1): # Check rows ahead
            if gamestate.board[scan_r][c] == 'p': is_passed = False; break
            if c > 0 and gamestate.board[scan_r][c-1] == 'p': is_passed = False; break
            if c < BOARD_SIZE-1 and gamestate.board[scan_r][c+1] == 'p': is_passed = False; break
            if gamestate.board[scan_r][c] != EMPTY_SQUARE: path_clear = False
        if is_passed:
            steps_to_promo = r  # white pawn at row r needs r steps to reach row 0
            score += PASSED_PAWN_BONUS.get(steps_to_promo, 15)
            if path_clear:
                score += UNSTOPPABLE_PAWN_BONUS.get(steps_to_promo, 0)

    for r, c in black_pawns:
        if c > 0 and gamestate.board[r][c-1] == 'p': score -= PAWN_STRUCTURE_BONUS
        if c < BOARD_SIZE-1 and gamestate.board[r][c+1] == 'p': score -= PAWN_STRUCTURE_BONUS
        # Blocked pawn penalty
        if r < BOARD_SIZE-1 and gamestate.board[r+1][c] != EMPTY_SQUARE:
            score += BLOCKED_PAWN_PENALTY
        is_passed = True
        path_clear = True
        for scan_r in range(r + 1, BOARD_SIZE): # Check rows ahead
            if gamestate.board[scan_r][c] == 'P': is_passed = False; break
            if c > 0 and gamestate.board[scan_r][c-1] == 'P': is_passed = False; break
            if c < BOARD_SIZE-1 and gamestate.board[scan_r][c+1] == 'P': is_passed = False; break
            if gamestate.board[scan_r][c] != EMPTY_SQUARE: path_clear = False
        if is_passed:
            steps_to_promo = BOARD_SIZE - 1 - r  # black pawn at row r needs (5-r) steps to row 5
            score -= PASSED_PAWN_BONUS.get(steps_to_promo, 15)
            if path_clear:
                score -= UNSTOPPABLE_PAWN_BONUS.get(steps_to_promo, 0)

    # 4. King Safety — pawn shield is CRITICAL in crazyhouse
    black_hand_total = sum(gamestate.hands.get('b', {}).values())
    white_hand_total = sum(gamestate.hands.get('w', {}).values())
    
    if white_king_r != -1:
        # White king pawn shield: pawns on rank directly in front (row - 1) and diagonals
        w_shield = 0
        for dc in (-1, 0, 1):
            sc = white_king_c + dc
            sr = white_king_r - 1  # row in front of white king
            if 0 <= sr < BOARD_SIZE and 0 <= sc < BOARD_SIZE:
                if gamestate.board[sr][sc] == 'P':
                    w_shield += 1
        score += w_shield * PAWN_SHIELD_BONUS
        # Exposed king penalty scales with opponent's hand (more drops = more danger)
        if w_shield == 0 and black_hand_total > 0:
            score -= EXPOSED_KING_PENALTY * min(black_hand_total, 3)
        # Center king penalty (opening)
        if phase == OPENING_PHASE:
            if (white_king_r, white_king_c) in CENTER_SQUARES: score -= 30
    
    if black_king_r != -1:
        b_shield = 0
        for dc in (-1, 0, 1):
            sc = black_king_c + dc
            sr = black_king_r + 1  # row in front of black king
            if 0 <= sr < BOARD_SIZE and 0 <= sc < BOARD_SIZE:
                if gamestate.board[sr][sc] == 'p':
                    b_shield += 1
        score -= b_shield * PAWN_SHIELD_BONUS
        if b_shield == 0 and white_hand_total > 0:
            score += EXPOSED_KING_PENALTY * min(white_hand_total, 3)
        if phase == OPENING_PHASE:
            if (black_king_r, black_king_c) in CENTER_SQUARES: score += 30
    
    if phase == ENDGAME_PHASE:
        # Endgame: king should be active / closer to center
        if white_king_r != -1 and (white_king_r, white_king_c) in CENTER_SQUARES: score += 15
        if black_king_r != -1 and (black_king_r, black_king_c) in CENTER_SQUARES: score -= 15

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

    # 6. IMPROVED: King Attack Evaluation (proximity-based, no false attacks through pieces)
    if white_king_r != -1 and black_king_r != -1:
        white_attackers_on_black_king = 0
        black_attackers_on_white_king = 0
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                piece = gamestate.board[r][c]
                if piece == EMPTY_SQUARE:
                    continue
                piece_type = piece.upper()
                if piece_type == 'K':
                    continue
                color = get_piece_color(piece)
                if color == 'w':
                    # Distance to black king
                    dist = max(abs(r - black_king_r), abs(c - black_king_c))
                    if piece_type == 'N':
                        if (black_king_r - r, black_king_c - c) in KNIGHT_MOVES:
                            white_attackers_on_black_king += 2  # Knight directly attacks king
                        elif dist <= 2:
                            white_attackers_on_black_king += 0.5
                    elif dist <= 2:
                        white_attackers_on_black_king += 1
                    elif dist <= 3 and piece_type in ('R', 'Q', 'B'):
                        white_attackers_on_black_king += 0.3
                else:
                    dist = max(abs(r - white_king_r), abs(c - white_king_c))
                    if piece_type == 'N':
                        if (white_king_r - r, white_king_c - c) in KNIGHT_MOVES:
                            black_attackers_on_white_king += 2
                        elif dist <= 2:
                            black_attackers_on_white_king += 0.5
                    elif dist <= 2:
                        black_attackers_on_white_king += 1
                    elif dist <= 3 and piece_type in ('R', 'Q', 'B'):
                        black_attackers_on_white_king += 0.3
        
        score += white_attackers_on_black_king * ATTACK_KING_ZONE_BONUS
        score -= black_attackers_on_white_king * ATTACK_KING_ZONE_BONUS

    # 7. Tempo bonus for side to move (slight advantage)
    score += 10 if gamestate.current_turn == 'w' else -10

    # 8. Drop pawn near promotion bonus (scale with opportunities)
    white_hand_pawns = gamestate.hands.get('w', {}).get('P', 0)
    black_hand_pawns = gamestate.hands.get('b', {}).get('P', 0)
    if white_hand_pawns > 0:
        # Rank 5 = row 1 for white. Each empty square is a potential drop+promote
        drop_spots = sum(1 for c in range(BOARD_SIZE) if gamestate.board[1][c] == EMPTY_SQUARE)
        if drop_spots > 0:
            score += DROP_PAWN_PROMO_BONUS + (drop_spots - 1) * 50
    if black_hand_pawns > 0:
        drop_spots = sum(1 for c in range(BOARD_SIZE) if gamestate.board[BOARD_SIZE - 2][c] == EMPTY_SQUARE)
        if drop_spots > 0:
            score -= DROP_PAWN_PROMO_BONUS + (drop_spots - 1) * 50

    # 9. Rook on open/semi-open file bonus
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            piece = gamestate.board[r][c]
            if piece == EMPTY_SQUARE:
                continue
            if piece.upper() != 'R':
                continue
            color = get_piece_color(piece)
            has_friendly_pawn = False
            has_enemy_pawn = False
            friendly_pawn = 'P' if color == 'w' else 'p'
            enemy_pawn = 'p' if color == 'w' else 'P'
            for scan_r in range(BOARD_SIZE):
                if gamestate.board[scan_r][c] == friendly_pawn:
                    has_friendly_pawn = True
                if gamestate.board[scan_r][c] == enemy_pawn:
                    has_enemy_pawn = True
            bonus = 0
            if not has_friendly_pawn and not has_enemy_pawn:
                bonus = OPEN_FILE_ROOK_BONUS
            elif not has_friendly_pawn:
                bonus = SEMI_OPEN_FILE_ROOK_BONUS
            if color == 'w':
                score += bonus
            else:
                score -= bonus

    # 10. Bishop pair bonus — strong diagonal control on small board
    white_bishops = 0
    black_bishops = 0
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            p = gamestate.board[r][c]
            if p == 'B': white_bishops += 1
            elif p == 'b': black_bishops += 1
    if white_bishops >= 2: score += BISHOP_PAIR_BONUS
    if black_bishops >= 2: score -= BISHOP_PAIR_BONUS
    # Also count bishops in hand
    if white_bishops + gamestate.hands.get('w', {}).get('B', 0) >= 2: score += BISHOP_PAIR_BONUS // 2
    if black_bishops + gamestate.hands.get('b', {}).get('B', 0) >= 2: score -= BISHOP_PAIR_BONUS // 2

    return score


# --- Quiescence Search ---
def is_noisy_move(gamestate, move):
    """Check if move is a capture, promotion, or drop (tactical move)."""
    try:
        if isinstance(move, tuple) and move and move[0] == 'drop':
            return True  # Drops are tactical in Crazyhouse
        (start_r, start_c), (end_r, end_c), promotion = move
        if gamestate.board[end_r][end_c] != EMPTY_SQUARE:
            return True  # Capture
        if promotion is not None:
            return True  # Promotion
    except Exception:
        pass
    return False

def is_check_move(gamestate, move):
    """Quick check: does this move give check to the opponent?"""
    try:
        gamestate.make_ai_move(move)
        opponent = gamestate.current_turn  # after move, it's opponent's turn
        in_check = gamestate.is_in_check(opponent)
        gamestate.undo_ai_move()
        return in_check
    except Exception:
        try:
            gamestate.undo_ai_move()
        except Exception:
            pass
        return False

def _is_drop_near_king(gamestate, move):
    """Check if a drop lands adjacent to (or attacks) the enemy king."""
    _, piece_code, (dr, df) = move
    drop_color = piece_code[0]
    enemy_color = 'b' if drop_color == 'w' else 'w'
    enemy_king_pos = gamestate.king_pos.get(enemy_color)
    if not enemy_king_pos:
        return False
    kr, kf = enemy_king_pos
    piece_type = piece_code[1].upper()
    # Knight drops: check if square attacks the king
    if piece_type == 'N':
        if (kr - dr, kf - df) in KNIGHT_MOVES:
            return True
    # Any piece dropped adjacent to king (distance <= 2) is tactical
    if max(abs(dr - kr), abs(df - kf)) <= 2:
        return True
    return False


def get_noisy_moves(gamestate: GameState):
    """Get tactical moves for quiescence: captures, promotions, checks, and drops near enemy king."""
    moves = gamestate.get_all_legal_moves()
    noisy_moves = []
    check_candidates = []  # test checks only for non-noisy moves to save time
    for move in moves:
        try:
            if isinstance(move, tuple) and move and move[0] == 'drop':
                # Include drops that land near the enemy king (tactical threats)
                if _is_drop_near_king(gamestate, move):
                    noisy_moves.append(move)
                continue
            # Normal move: ((r1,f1),(r2,f2), promotion)
            (start_r, start_c), (end_r, end_c), promotion = move
            is_capture = gamestate.board[end_r][end_c] != EMPTY_SQUARE
            is_promotion = promotion is not None
            if is_capture or is_promotion:
                noisy_moves.append(move)
            else:
                check_candidates.append(move)
        except Exception:
            continue
    # Also include quiet moves that give check (limit to save performance)
    for move in check_candidates[:12]:
        if is_check_move(gamestate, move):
            noisy_moves.append(move)
    return noisy_moves


def quiescence_search(gamestate: GameState, alpha, beta, depth):
    """ Search only captures and promotions until a quiet position is reached. """
    if gamestate.checkmate or gamestate.stalemate:
         return evaluate_position(gamestate)

    stand_pat_score = evaluate_position(gamestate)

    if depth == 0:
        return stand_pat_score

    # Delta Pruning: if position is so bad that even winning a rook won't help, prune
    DELTA_MARGIN = PIECE_VALUES['R']
    if gamestate.current_turn == 'w' and stand_pat_score < alpha - DELTA_MARGIN:
        return alpha
    if gamestate.current_turn != 'w' and stand_pat_score > beta + DELTA_MARGIN:
        return beta

    if gamestate.current_turn == 'w': # Maximizing
        if stand_pat_score >= beta:
            return beta # Fail high
        alpha = max(alpha, stand_pat_score)

        noisy_moves = get_noisy_moves(gamestate)
        # Sort noisy moves? MVV-LVA might be good here too.
        noisy_moves.sort(key=lambda m: mvv_lva_score(gamestate, m), reverse=True)

        for move in noisy_moves:
            # Use reversible moves instead of deepcopy for performance
            gamestate.make_ai_move(move)

            score = quiescence_search(gamestate, alpha, beta, depth - 1)

            gamestate.undo_ai_move()

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
            # Use reversible moves instead of deepcopy for performance
            gamestate.make_ai_move(move)

            score = quiescence_search(gamestate, alpha, beta, depth - 1)

            gamestate.undo_ai_move()

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
        
        # 1. CAPTURES - MVV-LVA (account for promoted pieces yielding only P in hand)
        if victim_piece != EMPTY_SQUARE:
            victim_value = PIECE_VALUES.get(victim_piece.upper(), 0)
            # In crazyhouse, capturing a promoted piece only gives P in hand
            promoted_set = getattr(gamestate, 'promoted_pieces', set())
            if (end_r, end_c) in promoted_set:
                # Still removes a strong piece from board, but hand value is only P
                # Use average: board removal value + hand gain value
                victim_value = (victim_value + PIECE_VALUES['P']) // 2
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
            
            # PAWN DROP NEAR PROMOTION — highest priority drop
            if piece_type == 'P':
                if piece_color == 'w' and drop_r == 1:  # one step from promotion
                    base_score += 800
                elif piece_color == 'w' and drop_r == 2:  # two steps
                    base_score += 200
                elif piece_color == 'b' and drop_r == BOARD_SIZE - 2:
                    base_score += 800
                elif piece_color == 'b' and drop_r == BOARD_SIZE - 3:
                    base_score += 200
            
            # DROP IN CENTER
            if (drop_r, drop_c) in CENTER_SQUARES:
                base_score += 50
            
            # DROP NEAR ENEMY KING
            enemy_color = get_opposite_color(piece_color)
            enemy_king_pos = gamestate.king_pos.get(enemy_color)
            if enemy_king_pos:
                ek_r, ek_c = enemy_king_pos
                dist = max(abs(drop_r - ek_r), abs(drop_c - ek_c))
                if dist <= 1:
                    base_score += 200  # Adjacent to king!
                elif dist <= 2:
                    base_score += 100  # Drop in king zone
            
            # KNIGHT FORK DETECTION — knight drop attacking multiple pieces
            if piece_type == 'N':
                attacks = 0
                for dr, df in KNIGHT_MOVES:
                    nr, nf = drop_r + dr, drop_c + df
                    if 0 <= nr < BOARD_SIZE and 0 <= nf < BOARD_SIZE:
                        target = gamestate.board[nr][nf]
                        if target != EMPTY_SQUARE and get_piece_color(target) == enemy_color:
                            attacks += 1
                            if target.upper() in ('K', 'R'):
                                base_score += 300  # Forking king or rook
                if attacks >= 2:
                    base_score += 200  # Fork bonus
            
            move_repr = repr(move)
            history_bonus = history_scores.get(move_repr, 0)
            return base_score + history_bonus
        return 0
    
    return 0 # Unknown format


# --- Minimax with Alpha-Beta (Simplified - No TT logic inside) ---
def minimax_alpha_beta(gamestate: GameState, depth, alpha, beta, maximizing_player, allow_null=True):
    """
    Performs minimax search with alpha-beta pruning and null-move pruning.
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

    # --- Null-Move Pruning ---
    # Skip if: in check, depth too shallow, or opponent has pieces in hand (crazyhouse drops are too dangerous)
    NULL_MOVE_R = 2  # Reduction factor
    current_color = 'w' if maximizing_player else 'b'
    opponent_color = 'b' if maximizing_player else 'w'
    opponent_hand_count = sum(gamestate.hands.get(opponent_color, {}).values())
    if (allow_null and depth >= NULL_MOVE_R + 1 
            and not gamestate.is_in_check(current_color)
            and opponent_hand_count == 0):
        # Make null move (just flip turn)
        gamestate.current_turn = get_opposite_color(gamestate.current_turn)
        gamestate._all_legal_moves_cache = None
        
        null_score, _ = minimax_alpha_beta(gamestate, depth - 1 - NULL_MOVE_R, 
                                            alpha, beta, not maximizing_player, allow_null=False)
        
        # Undo null move
        gamestate.current_turn = get_opposite_color(gamestate.current_turn)
        gamestate._all_legal_moves_cache = None
        
        if maximizing_player and null_score >= beta:
            return beta, None
        if not maximizing_player and null_score <= alpha:
            return alpha, None

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
    
    # LMR parameters
    LMR_FULL_DEPTH_MOVES = 4  # Search first N moves at full depth
    LMR_REDUCTION_LIMIT = 3   # Don't reduce below this depth
    
    if maximizing_player: # White
        max_eval = -float('inf')
        for i, move in enumerate(legal_moves):
            # Check if noisy BEFORE making the move (board state is still original)
            noisy = is_noisy_move(gamestate, move)
            gamestate.make_ai_move(move)
            
            # Late Move Reduction: reduce depth for late quiet moves
            if (i >= LMR_FULL_DEPTH_MOVES and depth >= LMR_REDUCTION_LIMIT 
                    and not noisy):
                # Reduced search
                eval_score, _ = minimax_alpha_beta(gamestate, depth - 2, alpha, beta, False)
                # Re-search at full depth if score improves
                if eval_score > alpha:
                    eval_score, _ = minimax_alpha_beta(gamestate, depth - 1, alpha, beta, False)
            else:
                eval_score, _ = minimax_alpha_beta(gamestate, depth - 1, alpha, beta, False)
            
            gamestate.undo_ai_move()

            if eval_score > max_eval:
                max_eval = eval_score
                best_move_for_depth = move
            alpha = max(alpha, eval_score)
            if alpha >= beta:
                if best_move_for_depth:
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
        for i, move in enumerate(legal_moves):
            noisy = is_noisy_move(gamestate, move)
            gamestate.make_ai_move(move)
            
            # Late Move Reduction
            if (i >= LMR_FULL_DEPTH_MOVES and depth >= LMR_REDUCTION_LIMIT
                    and not noisy):
                eval_score, _ = minimax_alpha_beta(gamestate, depth - 2, alpha, beta, True)
                if eval_score < beta:
                    eval_score, _ = minimax_alpha_beta(gamestate, depth - 1, alpha, beta, True)
            else:
                eval_score, _ = minimax_alpha_beta(gamestate, depth - 1, alpha, beta, True)
            
            gamestate.undo_ai_move()

            if eval_score < min_eval:
                min_eval = eval_score
                best_move_for_depth = move
            beta = min(beta, eval_score)
            if alpha >= beta:
                if best_move_for_depth:
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
        # Deserialize the GameState copy for this worker
        gamestate_copy = pickle.loads(gs_pickle_dump)

        # Use make_ai_move for the root move of this worker
        # Note: make_ai_move handles promotion automatically if passed in the move tuple
        gamestate_copy.make_ai_move(move)

        # Call the optimized minimax (which uses make_ai_move/undo_ai_move internally)
        score, _ = minimax_alpha_beta(gamestate_copy, depth - 1, alpha, beta, not is_maximizing)
        return score

    except Exception as e:
        # Log detailed error including the move being processed
        # traceback.print_exc() # Uncomment for full traceback in worker logs
        print(f"Error in worker process for move {move}: {type(e).__name__} - {e}")
        return -float('inf') if is_maximizing else float('inf')


# --- Main AI Function (Using Iterative Deepening + Cache) ---
def find_best_move(gamestate: GameState, depth=6, return_top_n=1, time_limit=None):
    """
    Finds the best move using ITERATIVE DEEPENING with move cache.
    Searches depth 1, 2, 3... up to target depth.
    Uses results from shallower searches to improve move ordering.
    
    Args:
        gamestate: Current game state
        depth: Maximum search depth
        return_top_n: If > 1, returns list of (move, score) tuples sorted by score
        time_limit: Max seconds for search (stops between depth iterations). None = no limit.
    
    Returns:
        If return_top_n == 1: best_move
        If return_top_n > 1: list of (move, score) tuples, sorted best to worst
    """
    # Training time check removed - scheduled_self_play.py handles scheduling
    
    print(f"AI ({gamestate.current_turn}) thinking with iterative deepening up to depth {depth}...")
    start_time = time.time()
    is_maximizing = (gamestate.current_turn == 'w')
    global move_cache # Access the global cache

    if gamestate.needs_promotion_choice:
        print("AI Error: Cannot find move, waiting for promotion choice.")
        return None if return_top_n == 1 else []

    # --- Check Move Cache (with depth, fallback to best available) ---
    pos_hash = get_position_hash(gamestate)
    cache_key = (pos_hash, depth)  # Include depth in cache key
    cached_move_repr = move_cache.get(cache_key)
    
    # Fallback: if exact depth not cached, use best available (highest depth <= requested)
    if not cached_move_repr and return_top_n == 1:
        best_fallback_depth = -1
        for (h, d), mr in move_cache.items():
            if h == pos_hash and d <= depth and d > best_fallback_depth:
                best_fallback_depth = d
                cached_move_repr = mr
        if cached_move_repr:
            print(f"[CACHE FALLBACK] Hash {pos_hash}: No depth {depth} entry, using depth {best_fallback_depth} entry.")

    # Only use cache if we want single best move
    if return_top_n == 1 and cached_move_repr:
        try:
            cached_move = eval(cached_move_repr)
            if hasattr(gamestate, 'is_move_legal') and gamestate.is_move_legal(cached_move):
                 print(f"[CACHE HIT] Hash {pos_hash} Depth {depth}: Found valid move {cached_move} in cache.")
                 end_time = time.time()
                 print(f"AI ({gamestate.current_turn}) finished thinking (CACHE HIT) in {end_time - start_time:.2f}s.")
                 return cached_move
            elif not hasattr(gamestate, 'is_move_legal'):
                 print(f"[CACHE WARN] Hash {pos_hash} Depth {depth}: Cannot validate cached move {cached_move} as GameState lacks 'is_move_legal'. Using cached move.")
                 end_time = time.time()
                 print(f"AI ({gamestate.current_turn}) finished thinking (CACHE HIT - UNVALIDATED) in {end_time - start_time:.2f}s.")
                 return cached_move
            else:
                 print(f"[CACHE WARN] Hash {pos_hash} Depth {depth}: Cached move {cached_move} is no longer legal. Recalculating.")
        except Exception as e:
            print(f"[CACHE ERROR] Hash {pos_hash} Depth {depth}: Error processing cached move '{cached_move_repr}': {e}. Recalculating.")
            if cache_key in move_cache: del move_cache[cache_key]

    # --- If not in cache or invalid, perform search ---
    print(f"[CACHE MISS] Hash {pos_hash} Depth {depth}: Position not in cache or invalid. Starting search...")
    best_score = -float('inf') if is_maximizing else float('inf')
    best_move = None

    legal_moves = gamestate.get_all_legal_moves()

    if not legal_moves:
        print("AI Error: No legal moves available!")
        score = evaluate_position(gamestate)
        print(f"  Terminal state evaluation: {score}")
        return None if return_top_n == 1 else []

    if len(legal_moves) == 1:
        print("Only one legal move available.")
        best_move = legal_moves[0]
        cache_key = (pos_hash, depth)
        move_cache[cache_key] = repr(best_move)
        print(f"[CACHE STORE] Hash {pos_hash} Depth {depth}: Stored single legal move {repr(best_move)}.")
        end_time = time.time()
        print(f"AI ({gamestate.current_turn}) finished thinking (Single Move) in {end_time - start_time:.2f}s.")
        return best_move if return_top_n == 1 else [(best_move, 0)]

    try:
        # === ITERATIVE DEEPENING ===
        # Depths 1 to PARALLEL_DEPTH_THRESHOLD-1: single-threaded (builds TT for move ordering)
        # Depths PARALLEL_DEPTH_THRESHOLD+: parallel workers (receive TT snapshot)
        best_move = None
        best_score = 0
        all_move_scores = []  # For return_top_n > 1
        
        # Clear TT at start of new search to avoid stale entries
        global tt
        tt.clear()
        
        for current_depth in range(1, depth + 1):
            iteration_start = time.time()
            print(f"  [ID] Searching depth {current_depth}...")
            
            # Check cache for this specific depth first (only if return_top_n == 1)
            if return_top_n == 1:
                iter_cache_key = (pos_hash, current_depth)
                cached_for_depth = move_cache.get(iter_cache_key)
                
                if cached_for_depth and current_depth == depth:
                    try:
                        cached_move = eval(cached_for_depth)
                        if hasattr(gamestate, 'is_move_legal') and gamestate.is_move_legal(cached_move):
                            print(f"  [ID] Depth {current_depth} cached, using it.")
                            best_move = cached_move
                            break
                    except:
                        pass
            
            # Choose single-threaded vs parallel based on depth
            if current_depth < PARALLEL_DEPTH_THRESHOLD:
                # Single-threaded: builds global TT for deeper searches
                iter_best_move_score = minimax_alpha_beta(
                    gamestate, current_depth, -float('inf'), float('inf'), is_maximizing)
                iter_best_move = iter_best_move_score[1]
                iter_best_score = iter_best_move_score[0]
                # minimax_alpha_beta returns (score, best_move) — score is from perspective of position
                if is_maximizing:
                    iter_best_score = iter_best_move_score[0]
                else:
                    iter_best_score = iter_best_move_score[0]
            elif return_top_n > 1 and current_depth == depth:
                # Parallel: final depth, get all move scores
                tt_snapshot = dict(tt) if tt else None
                iter_best_move, iter_best_score, all_move_scores = minimax(
                    gamestate, current_depth, move_cache, return_all_scores=True, tt_data=tt_snapshot)
            else:
                # Parallel: pass TT snapshot from single-threaded iterations
                tt_snapshot = dict(tt) if tt else None
                iter_best_move, iter_best_score = minimax(
                    gamestate, current_depth, move_cache, tt_data=tt_snapshot)
            
            if iter_best_move:
                best_move = iter_best_move
                best_score = iter_best_score
                
                if return_top_n == 1:
                    iter_cache_key = (pos_hash, current_depth)
                    move_cache[iter_cache_key] = repr(best_move)
                
                iteration_time = time.time() - iteration_start
                print(f"  [ID] Depth {current_depth} complete in {iteration_time:.2f}s, best: {format_move_for_print(best_move)}, score: {best_score:.1f}")
            else:
                print(f"  [ID] Depth {current_depth} failed to find move")
                break
            
            if abs(best_score) >= CHECKMATE_SCORE * 0.9:
                print(f"  [ID] Mate found at depth {current_depth}, stopping search")
                break
            
            # Time limit check between depth iterations
            if time_limit and (time.time() - start_time) >= time_limit:
                print(f"  [ID] Time limit ({time_limit}s) reached after depth {current_depth}, using best so far")
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
        # Store best move in cache regardless of return_top_n
        cache_key = (pos_hash, depth)
        move_cache[cache_key] = repr(best_move)
        print(f"[CACHE STORE] Hash {pos_hash} Depth {depth}: Stored move {repr(best_move)}.")
        
        # Persist valuable TT entries to move_cache for future games
        tt_saved = 0
        for tt_hash, tt_entry in tt.items():
            tt_d = tt_entry.get('depth', 0)
            if tt_d >= 4 and tt_entry.get('flag') == 'EXACT' and tt_entry.get('best_move'):
                tt_key = (tt_hash, tt_d)
                if tt_key not in move_cache:
                    move_cache[tt_key] = repr(tt_entry['best_move'])
                    tt_saved += 1
        if tt_saved > 0:
            print(f"  [TT→CACHE] Saved {tt_saved} intermediate positions from TT (depth≥4, EXACT)")
    else:
        print(f"AI ({gamestate.current_turn}) could not find a best move after {end_time - start_time:.2f}s. Legal moves: {legal_moves}")

    # Return based on return_top_n
    if return_top_n == 1:
        return best_move
    else:
        # Return top N moves sorted by score
        if all_move_scores:
            # Sort: for white (maximizing), descending; for black, ascending
            all_move_scores.sort(key=lambda x: x[1], reverse=is_maximizing)
            return all_move_scores[:return_top_n]
        else:
            return [(best_move, best_score)] if best_move else []

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

def minimax(gamestate: GameState, depth, move_cache, return_all_scores=False, tt_data=None):
    """Starts the parallel minimax search.
    
    Args:
        return_all_scores: If True, returns (best_move, best_score, all_move_scores_list)
                          If False, returns (best_move, best_score)
        tt_data: Optional TT snapshot from single-threaded iterations for move ordering
    """
    try:
        start_time_minimax = time.time()
        legal_moves = gamestate.get_all_legal_moves()
        if not legal_moves:
            result = (None, 0, []) if return_all_scores else (None, 0)
            return result

        num_workers = NUM_WORKERS if NUM_WORKERS else multiprocessing.cpu_count()
        print(f"Using {num_workers} worker processes for depth {depth} search.")
        
        # Serialize TT snapshot for workers (if available)
        tt_dump = pickle.dumps(tt_data) if tt_data else None
        
        # Use ProcessPoolExecutor for better cleanup
        with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            try:
                gamestate_dump = pickle.dumps(gamestate)
            except:
                print(f"Error pickling gamestate")
                result = (None, 0, []) if return_all_scores else (None, 0)
                return result
            maximizing_player = (gamestate.current_turn == 'w')
            
            # Search first move sequentially to get a baseline score for aspiration window
            first_move = legal_moves[0]
            first_result = _minimax_worker(first_move, gamestate_dump, depth, -float('inf'), float('inf'), maximizing_player, None, tt_dump)
            baseline_score = first_result[1] if first_result else 0
            ASPIRATION_WINDOW = 150  # centipawns
            asp_alpha = baseline_score - ASPIRATION_WINDOW
            asp_beta = baseline_score + ASPIRATION_WINDOW
            
            # Search remaining moves in parallel with tighter window
            for move in legal_moves[1:]:
                future = executor.submit(_minimax_worker, move, gamestate_dump, depth, asp_alpha, asp_beta, maximizing_player, None, tt_dump)
                futures.append(future)

            results = [first_result]
            re_search_moves = []
            for future in concurrent.futures.as_completed(futures):
                try:
                    res = future.result()
                    if res:
                        move, score = res
                        # If score is at window boundary, it may be truncated — re-search with full window
                        if score is not None and (score <= asp_alpha or score >= asp_beta):
                            re_search_moves.append(move)
                        else:
                            results.append(res)
                except Exception as e:
                    print(f"Worker task failed: {e}")
            
            # Re-search moves that fell outside aspiration window with full alpha/beta
            for move in re_search_moves:
                try:
                    res = _minimax_worker(move, gamestate_dump, depth, -float('inf'), float('inf'), maximizing_player, None, tt_dump)
                    if res:
                        results.append(res)
                except Exception as e:
                    print(f"Re-search failed for {move}: {e}")

        all_results = []
        for result in results:
            if result is None: continue
            move, score = result
            if score is not None:
                all_results.append((move, score))

        if not all_results:
            print("[WARN] Minimax main: No valid scores returned from workers or no legal moves?")
            if gamestate.checkmate: 
                score = -CHECKMATE_SCORE if gamestate.current_turn == 'w' else CHECKMATE_SCORE
                result = (None, score, []) if return_all_scores else (None, score)
                return result
            if gamestate.stalemate:
                result = (None, STALEMATE_SCORE, []) if return_all_scores else (None, STALEMATE_SCORE)
                return result
            legal_moves_fallback = gamestate.get_all_legal_moves()
            if not legal_moves_fallback:
                score = STALEMATE_SCORE if not gamestate.is_in_check(gamestate.current_turn) else (-CHECKMATE_SCORE if gamestate.current_turn == 'w' else CHECKMATE_SCORE)
                result = (None, score, []) if return_all_scores else (None, score)
                return result
            fallback_move = random.choice(legal_moves_fallback)
            result = (fallback_move, -float('inf'), [(fallback_move, -float('inf'))]) if return_all_scores else (fallback_move, -float('inf'))
            return result

        # --- ПРИОРИТЕТ МАТА ---
        current_player_color = gamestate.current_turn
        mating_score = CHECKMATE_SCORE if current_player_color == 'w' else -CHECKMATE_SCORE
        best_mate_move = None

        for move, score in all_results:
            if score == mating_score:
                best_mate_move = move
                break

        if best_mate_move is not None:
            result = (best_mate_move, mating_score, all_results) if return_all_scores else (best_mate_move, mating_score)
            return result

        # Find best move based on scores
        best_move = all_results[0][0]
        if current_player_color == 'w':
            best_score = -float('inf')
            for move, score in all_results:
                if score > best_score:
                    best_score = score
                    best_move = move
        else:
            best_score = float('inf')
            for move, score in all_results:
                if score < best_score:
                    best_score = score
                    best_move = move

        result = (best_move, best_score, all_results) if return_all_scores else (best_move, best_score)
        return result

    except Exception as e:
        print(f"Error in minimax function: {e}")
        traceback.print_exc()
        try:
             moves = gamestate.get_all_legal_moves()
             fallback_move = random.choice(moves) if moves else None
             result = (fallback_move, 0, [(fallback_move, 0)]) if return_all_scores else (fallback_move, 0)
             return result
        except:
             result = (None, 0, []) if return_all_scores else (None, 0)
             return result

def _minimax_worker(move, gamestate_dump, depth, alpha, beta, maximizing_player, move_cache, tt_dump=None):
    """Minimax function for a single move, executed by a worker process."""
    try:
        # Initialize worker's TT from snapshot (if available)
        global tt
        if tt_dump:
            try:
                tt = pickle.loads(tt_dump)
            except:
                tt = {}
        
        # Deserialize inside the worker
        gamestate_copy = pickle.loads(gamestate_dump)
        
        # Make the move for which this worker is responsible using optimized method
        # Note: make_ai_move handles promotion if it's in the move tuple
        gamestate_copy.make_ai_move(move)

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

def _minimax_recursive(gamestate: GameState, depth, alpha, beta, maximizing_player, allow_null=True):
    """Recursive helper for minimax with alpha-beta pruning, null-move pruning, LMR, check extensions, TT."""

    # --- Check Extension: if we're in check, don't lose depth ---
    current_color = 'w' if maximizing_player else 'b'
    in_check = gamestate.is_in_check(current_color)
    if in_check and depth < 3:
        depth += 1  # extend search when in check (cap to avoid explosion)

    # --- Depth Limit Check ---
    if depth <= 0:
        return _quiescence_search(gamestate, alpha, beta, maximizing_player, MAX_QUIESCENCE_DEPTH)

    # --- Terminal State Check ---
    legal_moves = gamestate.get_all_legal_moves()
    if not legal_moves:
        if hasattr(gamestate, 'is_in_check') and gamestate.is_in_check(gamestate.current_turn):
            return -CHECKMATE_SCORE if gamestate.current_turn == 'w' else CHECKMATE_SCORE
        else:
            return STALEMATE_SCORE

    # --- Transposition Table Probe ---
    pos_hash = get_position_hash(gamestate)
    tt_entry = tt.get(pos_hash)
    if tt_entry and tt_entry.get('depth', -1) >= depth:
        if tt_entry['flag'] == 'EXACT':
            return tt_entry['score']
        elif tt_entry['flag'] == 'LOWERBOUND':
            alpha = max(alpha, tt_entry['score'])
        elif tt_entry['flag'] == 'UPPERBOUND':
            beta = min(beta, tt_entry['score'])
        if alpha >= beta:
            return tt_entry['score']

    # --- Null-Move Pruning ---
    # Skip when in check or opponent has pieces in hand (crazyhouse drops make null-move dangerous)
    NULL_MOVE_R = 2
    opponent_color = 'b' if maximizing_player else 'w'
    opponent_hand_count = sum(gamestate.hands.get(opponent_color, {}).values())
    if (allow_null and depth >= NULL_MOVE_R + 1
            and not in_check
            and opponent_hand_count == 0):
        gamestate.current_turn = get_opposite_color(gamestate.current_turn)
        gamestate._all_legal_moves_cache = None
        
        null_score = _minimax_recursive(gamestate, depth - 1 - NULL_MOVE_R,
                                        alpha, beta, not maximizing_player, allow_null=False)
        
        gamestate.current_turn = get_opposite_color(gamestate.current_turn)
        gamestate._all_legal_moves_cache = None
        
        if maximizing_player and null_score >= beta:
            return beta
        if not maximizing_player and null_score <= alpha:
            return alpha

    # --- Move ordering: TT best-move first, then MVV-LVA ---
    tt_best = tt_entry.get('best_move') if tt_entry else None
    def _move_order(move):
        if tt_best is not None and move == tt_best:
            return 1000000
        return mvv_lva_score(gamestate, move)
    legal_moves.sort(key=_move_order, reverse=True)

    # LMR parameters
    LMR_FULL_DEPTH_MOVES = 4
    LMR_REDUCTION_LIMIT = 3

    orig_alpha = alpha
    best_move_here = legal_moves[0] if legal_moves else None

    # --- Move Iteration with Mate Priority, LMR, and Check Extensions ---
    if maximizing_player:
        max_eval = -float('inf')
        for i, move in enumerate(legal_moves):
            noisy = is_noisy_move(gamestate, move)
            gamestate.make_ai_move(move)
            
            # Check if this move gives check (don't reduce checking moves)
            gives_check = gamestate.is_in_check(gamestate.current_turn)
            
            # Late Move Reduction — skip for noisy or checking moves
            if (i >= LMR_FULL_DEPTH_MOVES and depth >= LMR_REDUCTION_LIMIT
                    and not noisy and not gives_check):
                eval_score = _minimax_recursive(gamestate, depth - 2, alpha, beta, False)
                if eval_score > alpha:
                    eval_score = _minimax_recursive(gamestate, depth - 1, alpha, beta, False)
            else:
                eval_score = _minimax_recursive(gamestate, depth - 1, alpha, beta, False)
            
            gamestate.undo_ai_move()

            # <<< Mate Check >>>
            if eval_score >= CHECKMATE_SCORE: 
                return CHECKMATE_SCORE
            
            if eval_score > max_eval:
                max_eval = eval_score
                best_move_here = move
            alpha = max(alpha, eval_score)
            if beta <= alpha:
                break # Beta cut-off

        # Store in TT
        if max_eval <= orig_alpha:
            tt_flag = 'UPPERBOUND'
        elif max_eval >= beta:
            tt_flag = 'LOWERBOUND'
        else:
            tt_flag = 'EXACT'
        tt[pos_hash] = {'depth': depth, 'score': max_eval, 'flag': tt_flag, 'best_move': best_move_here}
        return max_eval

    else: # Minimizing player (Black trying to minimize)
        min_eval = float('inf')
        for i, move in enumerate(legal_moves):
            noisy = is_noisy_move(gamestate, move)
            gamestate.make_ai_move(move)
            
            gives_check = gamestate.is_in_check(gamestate.current_turn)
            
            # Late Move Reduction — skip for noisy or checking moves
            if (i >= LMR_FULL_DEPTH_MOVES and depth >= LMR_REDUCTION_LIMIT
                    and not noisy and not gives_check):
                eval_score = _minimax_recursive(gamestate, depth - 2, alpha, beta, True)
                if eval_score < beta:
                    eval_score = _minimax_recursive(gamestate, depth - 1, alpha, beta, True)
            else:
                eval_score = _minimax_recursive(gamestate, depth - 1, alpha, beta, True)
            
            gamestate.undo_ai_move()

            # <<< Mate Check >>>
            if eval_score <= -CHECKMATE_SCORE:
                 return -CHECKMATE_SCORE
            
            if eval_score < min_eval:
                min_eval = eval_score
                best_move_here = move
            beta = min(beta, eval_score)
            if beta <= alpha:
                break # Alpha cut-off

        # Store in TT
        if min_eval >= beta:
            tt_flag = 'LOWERBOUND'  
        elif min_eval <= orig_alpha:
            tt_flag = 'UPPERBOUND'
        else:
            tt_flag = 'EXACT'
        tt[pos_hash] = {'depth': depth, 'score': min_eval, 'flag': tt_flag, 'best_move': best_move_here}
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

    # Delta Pruning
    DELTA_MARGIN = PIECE_VALUES['R']
    if maximizing_player and stand_pat_score < alpha - DELTA_MARGIN:
        return alpha
    if not maximizing_player and stand_pat_score > beta + DELTA_MARGIN:
        return beta

    if maximizing_player:
        if stand_pat_score >= beta:
            return beta # Fail-high (score is already too good for maximizing player)
        alpha = max(alpha, stand_pat_score)

        noisy_moves = get_noisy_moves(gamestate)
        if not noisy_moves: return stand_pat_score # No noisy moves, return static eval
        
        for move in noisy_moves:
             # OPTIMIZATION: Use reversible moves
             gamestate.make_ai_move(move)
             
             score = _quiescence_search(gamestate, alpha, beta, False, depth - 1)
             
             # Undo move
             gamestate.undo_ai_move()
             
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
             # OPTIMIZATION: Use reversible moves
             gamestate.make_ai_move(move)
             
             score = _quiescence_search(gamestate, alpha, beta, True, depth - 1)
             
             # Undo move
             gamestate.undo_ai_move()
             
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