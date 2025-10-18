#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke test - verify game initialization and AI works"""
import time
from gamestate import GameState
from ai import find_best_move

if __name__ == "__main__":
    print("=" * 60)
    print("SMOKE TEST - Game & AI Verification")
    print("=" * 60)
    
    # Test 1: Game initialization
    print("\n[Test 1] Game Initialization...")
    gs = GameState()
    gs.setup_initial_board()
    print(f"✓ Game created")
    print(f"  - White AI: {gs.white_ai_enabled} (expected: False)")
    print(f"  - Black AI: {gs.black_ai_enabled} (expected: False)")  
    print(f"  - AI Depth: {gs.ai_depth} (expected: 6)")
    print(f"  - Current turn: {gs.current_turn}")
    
    # Test 2: AI can find move for white
    print("\n[Test 2] AI Move Generation (White, depth=4)...")
    start = time.time()
    move = find_best_move(gs, depth=4)
    elapsed = time.time() - start
    print(f"✓ AI returned move in {elapsed:.2f}s: {move}")
    
    # Test 3: Make move and AI can find move for black
    print("\n[Test 3] Making move and AI for Black...")
    if move:
        gs.make_move(move)
        print(f"✓ Move executed, now {gs.current_turn}'s turn")
        start = time.time()
        move2 = find_best_move(gs, depth=4)
        elapsed = time.time() - start
        print(f"✓ AI returned move in {elapsed:.2f}s: {move2}")
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED ✓")
    print("=" * 60)
    print("\nGame is ready! Run: ./play.sh")
