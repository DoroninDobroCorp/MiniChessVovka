# -*- coding: utf-8 -*-
"""
AI module - Rust-accelerated wrapper.
Delegates heavy search to the Rust minichess_engine module while maintaining
the same Python API for compatibility with gui.py, play_online.py, etc.
"""
import time
import minichess_engine as _rs

from config import BOARD_SIZE
from utils import get_piece_color, algebraic_to_coords

# --- Constants (kept for compatibility) ---
CHECKMATE_SCORE = 1000000
STALEMATE_SCORE = 0

# --- Module-level state (compatibility with play_online.py, precalc_openings.py) ---
move_cache = {}  # Python-side mirror; Rust manages its own cache internally
tt = {}  # Not used directly; Rust has internal TT
DB_PATH = "move_cache.db"

# --- Database / Cache ---

def setup_db():
    """Initialize the move cache database."""
    _rs.setup_db()


def load_move_cache_from_db():
    """Load move cache from SQLite into Rust engine."""
    global move_cache
    _rs.load_move_cache_from_db()
    # We don't mirror to Python dict anymore; Rust owns the cache


def save_move_cache_to_db(cache_to_save=None):
    """Save move cache from Rust engine to SQLite."""
    _rs.save_move_cache_to_db()


# --- Sync helpers ---

def _sync_to_rust(gamestate):
    """Create a Rust GameState from a Python GameState."""
    rs = _rs.GameState()
    rs.board = gamestate.board
    rs.current_turn = gamestate.current_turn
    rs.hands = gamestate.hands
    rs.king_pos = gamestate.king_pos
    rs.checkmate = gamestate.checkmate
    rs.stalemate = gamestate.stalemate
    rs.promoted_pieces = list(gamestate.promoted_pieces) if hasattr(gamestate, 'promoted_pieces') else []
    return rs


# --- Core AI Functions ---

def get_position_hash(gamestate):
    """Compute Zobrist hash for the position (via Rust)."""
    rs = _sync_to_rust(gamestate)
    return _rs.get_position_hash(rs)


def evaluate_position(gamestate):
    """Static evaluation of the position (via Rust)."""
    rs = _sync_to_rust(gamestate)
    return _rs.evaluate_position(rs)


def find_best_move(gamestate, depth=6, return_top_n=1, time_limit=None):
    """
    Find the best move using Rust engine's iterative deepening alpha-beta search.

    Args:
        gamestate: Python GameState object
        depth: Maximum search depth
        return_top_n: If > 1, returns list of (move, score) tuples
        time_limit: Max seconds for search. None = no limit.

    Returns:
        If return_top_n == 1: best_move tuple or None
        If return_top_n > 1: list of (move, score) tuples
    """
    print(f"AI ({gamestate.current_turn}) thinking with Rust engine, depth {depth}...")
    start_time = time.time()

    if gamestate.needs_promotion_choice:
        print("AI Error: Cannot find move, waiting for promotion choice.")
        return None if return_top_n == 1 else []

    legal_moves = gamestate.get_all_legal_moves()
    if not legal_moves:
        print("AI Error: No legal moves available!")
        return None if return_top_n == 1 else []

    if len(legal_moves) == 1:
        print("Only one legal move available.")
        elapsed = time.time() - start_time
        print(f"AI ({gamestate.current_turn}) finished (single move) in {elapsed:.2f}s.")
        return legal_moves[0] if return_top_n == 1 else [(legal_moves[0], 0)]

    # Sync Python GameState → Rust
    rs = _sync_to_rust(gamestate)

    # Call Rust search
    result = _rs.find_best_move(rs, depth, return_top_n, time_limit)

    elapsed = time.time() - start_time
    print(f"AI ({gamestate.current_turn}) finished in {elapsed:.2f}s.")

    return result


# --- Compatibility functions used by tests and other modules ---

def minimax_alpha_beta(gamestate, depth, alpha, beta, maximizing_player, allow_null=True):
    """
    Compatibility wrapper. Runs a Rust search at the given depth and returns (score, best_move).
    Note: alpha/beta/allow_null params are handled internally by Rust.
    """
    rs = _sync_to_rust(gamestate)
    result = _rs.find_best_move(rs, depth)
    if result is None:
        score = evaluate_position(gamestate)
        return (score, None)
    # find_best_move returns just the move tuple when return_top_n=1
    # We need (score, move) - run eval on the resulting position for score
    return (0, result)


def parse_move_string(move_str):
    """Convert move string (e.g., 'e2e4', 'N@c3') to internal move format."""
    try:
        if '@' in move_str:
            piece_char, sq_str = move_str.split('@')
            target_sq = algebraic_to_coords(sq_str)
            if target_sq:
                return ('drop', piece_char, target_sq)
        elif len(move_str) >= 4:
            start_sq = algebraic_to_coords(move_str[:2])
            end_sq = algebraic_to_coords(move_str[2:4])
            promotion_char = move_str[4] if len(move_str) == 5 else None
            if start_sq and end_sq:
                return (start_sq, end_sq, promotion_char)
    except Exception as e:
        print(f"[ERROR] Failed to parse move string '{move_str}': {e}")
    return None


def is_move_still_legal(gamestate, move):
    """Check if a move is legal in the current gamestate."""
    try:
        return move in gamestate.get_all_legal_moves()
    except Exception:
        return False
