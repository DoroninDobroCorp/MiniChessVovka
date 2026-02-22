#!/usr/bin/env python3
"""
Deep precalculation of opening moves for minihouse.
Calculates at depth 6 (full quality):
  Level 0: Starting position → white's best first move
  Level 1: For each of white's 15 first moves → black's best response
  Level 2: For each (white_move, black_response) → white's best 2nd move
  
Total: 1 + 15 + 15*~15 = ~241 positions at depth 6
Estimated time: ~2 hours on 8-core Mac
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gamestate import GameState
import ai as ai_module
from ai import find_best_move, save_move_cache_to_db, load_move_cache_from_db, get_position_hash

DEPTH = 10  # Rust engine can handle depth 10 in ~4s per position
TIME_LIMIT = None  # No time limit — full quality search


def format_move(m):
    if m is None:
        return "None"
    if m[0] == 'drop':
        return f"drop {m[1]} @ {chr(97+m[2][1])}{6-m[2][0]}"
    sr, sc = m[0]
    er, ec = m[1]
    return f"{chr(97+sc)}{6-sr}{chr(97+ec)}{6-er}"


def calc_position(gs, label):
    """Calculate best move for a position, return (move, score, time)."""
    legal = gs.get_all_legal_moves()
    if not legal:
        print(f"  ⚠️  No legal moves for {label}")
        return None, 0, 0
    
    print(f"  🧠 Computing: {label} ({len(legal)} legal moves)...")
    t0 = time.time()
    best = find_best_move(gs, depth=DEPTH, time_limit=TIME_LIMIT)
    elapsed = time.time() - t0
    
    if best:
        print(f"  ✅ {label} → {format_move(best)} ({elapsed:.1f}s)")
    else:
        print(f"  ❌ {label} → no move found ({elapsed:.1f}s)")
    
    return best, 0, elapsed


def make_start_gs():
    """Create a GameState with the standard minihouse starting position.
    Must match how play_online.py builds the board (including Q in hands)."""
    gs = GameState()
    gs.setup_initial_board()
    # play_online.py includes Q in hands dict — must match for hash consistency
    for color in ('w', 'b'):
        if 'Q' not in gs.hands[color]:
            gs.hands[color]['Q'] = 0
    gs._hash_cache = None  # invalidate hash after modification
    return gs


def main():
    print("=" * 60)
    print("🎯 DEEP OPENING PRECALCULATION (depth 6)")
    print("=" * 60)
    
    # Load existing cache
    load_move_cache_from_db()
    
    gs0 = make_start_gs()
    total_positions = 0
    total_time = 0
    
    # ═══════════════════════════════════════════
    # LEVEL 0: Starting position (white to move)
    # ═══════════════════════════════════════════
    print("\n" + "═" * 60)
    print("LEVEL 0: Starting position — White's best first move")
    print("═" * 60)
    
    white_best, _, t = calc_position(gs0, "START")
    total_time += t
    total_positions += 1
    
    # Save after each level
    save_move_cache_to_db()
    
    # ═══════════════════════════════════════════
    # LEVEL 1: All white first moves → black's response
    # ═══════════════════════════════════════════
    white_moves = gs0.get_all_legal_moves()
    print(f"\n{'═' * 60}")
    print(f"LEVEL 1: Black's response to each of {len(white_moves)} white first moves")
    print("═" * 60)
    
    level1_positions = []  # (white_move, black_response, gamestate_after_both)
    
    for i, wmove in enumerate(white_moves):
        gs1 = gs0.copy()
        gs1.make_move(wmove)
        
        label = f"[{i+1}/{len(white_moves)}] After w:{format_move(wmove)} — Black"
        black_best, _, t = calc_position(gs1, label)
        total_time += t
        total_positions += 1
        
        if black_best:
            gs2 = gs1.copy()
            gs2.make_move(black_best)
            level1_positions.append((wmove, black_best, gs2))
        
        # Save periodically
        if (i + 1) % 5 == 0:
            save_move_cache_to_db()
            print(f"  💾 Saved cache")
    
    save_move_cache_to_db()
    print(f"  💾 Saved cache")
    
    # ═══════════════════════════════════════════
    # LEVEL 2: White's best 2nd move for each (w1, b1) pair
    # ═══════════════════════════════════════════
    print(f"\n{'═' * 60}")
    print(f"LEVEL 2: White's 2nd move for {len(level1_positions)} (w1,b1) combinations")
    print("═" * 60)
    
    for i, (wmove, bmove, gs2) in enumerate(level1_positions):
        label = f"[{i+1}/{len(level1_positions)}] After w:{format_move(wmove)} b:{format_move(bmove)} — White"
        white2_best, _, t = calc_position(gs2, label)
        total_time += t
        total_positions += 1
        
        if (i + 1) % 5 == 0:
            save_move_cache_to_db()
            print(f"  💾 Saved cache")
    
    save_move_cache_to_db()
    
    # ═══════════════════════════════════════════
    # LEVEL 2b: For the BEST white move, also calc ALL black responses → white's 2nd move
    # ═══════════════════════════════════════════
    if white_best:
        gs_after_best_white = gs0.copy()
        gs_after_best_white.make_move(white_best)
        black_moves = gs_after_best_white.get_all_legal_moves()
        
        print(f"\n{'═' * 60}")
        print(f"LEVEL 2b: After BEST white move {format_move(white_best)}, "
              f"calc white's 2nd move for ALL {len(black_moves)} black responses")
        print("═" * 60)
        
        for i, bmove in enumerate(black_moves):
            gs2b = gs_after_best_white.copy()
            gs2b.make_move(bmove)
            
            label = f"[{i+1}/{len(black_moves)}] After w:{format_move(white_best)} b:{format_move(bmove)} — White"
            w2_best, _, t = calc_position(gs2b, label)
            total_time += t
            total_positions += 1
            
            # LEVEL 3: For this white 2nd move, what does black respond?
            if w2_best:
                gs3 = gs2b.copy()
                gs3.make_move(w2_best)
                label3 = f"  └─ After w2:{format_move(w2_best)} — Black"
                b2_best, _, t = calc_position(gs3, label3)
                total_time += t
                total_positions += 1
            
            if (i + 1) % 3 == 0:
                save_move_cache_to_db()
                print(f"  💾 Saved cache")
        
        save_move_cache_to_db()
    
    # ═══════════════════════════════════════════
    # DONE
    # ═══════════════════════════════════════════
    print(f"\n{'═' * 60}")
    print(f"✅ PRECALCULATION COMPLETE")
    print(f"   Positions calculated: {total_positions}")
    print(f"   Total time: {total_time:.0f}s ({total_time/60:.1f} min)")
    print(f"   Cache size: see move_cache.db")
    print("═" * 60)


if __name__ == "__main__":
    main()
