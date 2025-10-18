#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quick test to verify parallel AI works"""
import time
import multiprocessing
from gamestate import GameState
from ai import find_best_move

if __name__ == "__main__":
    print("=" * 50)
    print("Testing Parallel AI Search")
    print("=" * 50)
    
    # Create initial position
    gs = GameState()
    gs.setup_initial_board()
    
    print(f"CPU cores: {multiprocessing.cpu_count()}")
    print(f"Testing with depth=4 (should be quick)")
    print("-" * 50)
    
    start = time.time()
    best_move = find_best_move(gs, depth=4)
    elapsed = time.time() - start
    
    print("-" * 50)
    print(f"Result: {best_move}")
    print(f"Time: {elapsed:.2f}s")
    print("=" * 50)
    
    if best_move:
        print("✓ Test PASSED - AI returned a move")
    else:
        print("✗ Test FAILED - AI returned None")
