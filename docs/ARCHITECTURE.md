# MiniChess 6×6 Crazyhouse — Architecture & Design

## Overview

A 6×6 crazyhouse chess engine with a Rust-accelerated search backend + chess.com browser automation bot.
Crazyhouse = captured pieces go to your "hand" and can be dropped back onto the board.

## Directory Structure

```
MiniChess/
├── ai.py                   # AI wrapper — delegates search to Rust engine
├── gamestate.py            # Game rules, move generation, make/undo moves
├── config.py               # Board size, window dimensions, constants
├── pieces.py               # Piece definitions, movement patterns, values
├── utils.py                # Coordinate conversion, formatting helpers
├── gui.py                  # Pygame GUI — board rendering, interaction
├── main.py                 # Main entry point — game loop, event handling
├── thread_utils.py         # Background threads for AI & hint calculation
├── play_online.py          # Chess.com bot (Playwright browser automation)
├── precalc_openings.py     # Deep opening precalculation (depth 10)
├── requirements.txt        # Python dependencies
│
├── engine_rs/              # Rust search engine (PyO3 → minichess_engine)
│   ├── Cargo.toml
│   └── src/
│       ├── lib.rs          # PyO3 bindings (Python ↔ Rust interface)
│       ├── search.rs       # Alpha-beta, PVS, LMR, null-move, quiescence
│       ├── eval.rs         # Position evaluation function
│       ├── gamestate.rs    # Board representation & move generation (Rust)
│       ├── types.rs        # Shared types and constants
│       ├── cache.rs        # SQLite move cache integration
│       └── zobrist.rs      # Zobrist hashing for transposition table
│
├── engine/
│   └── env.py              # RL environment wrapper (for NN training)
│
├── nn/                     # Neural network experiments
│   ├── model.py            # PolicyValueNet (PyTorch CNN)
│   └── mcts.py             # Monte Carlo Tree Search
│
├── src/
│   ├── self_play.py        # Self-play training mode (20% exploration)
│   └── scheduled_self_play.py  # Scheduled training with logging
│
├── tests/
│   ├── test_ai_optimization.py  # Undo/redo, move validation tests
│   └── test_nightly.py          # DB schema, cache verification tests
│
├── assets/sprites/         # Chess piece images (PNG)
│
├── docs/
│   ├── ARCHITECTURE.md     # This file
│   ├── IMPROVEMENTS.md     # Future improvement roadmap
│   └── evaluation_strategy.md  # Detailed evaluation function docs
│
├── play.sh                 # Launch local GUI game
├── train.sh                # Launch self-play training
├── bot_start.sh            # Start chess.com bot
├── bot_stop.sh             # Stop chess.com bot
├── autorun_training.sh     # Automated training launcher
├── check_training_health.sh # Training health monitor
├── monitor_bot.sh          # Bot status monitor
├── training_dashboard.sh   # Training metrics dashboard
├── minichesstrain.service  # Systemd service (daily training)
└── minichesstrain.timer    # Systemd timer (00:00 UTC trigger)
```

## AI Engine (`ai.py` → `engine_rs/`)

The Python `ai.py` is a thin wrapper that delegates all heavy computation to
the Rust `minichess_engine` module (compiled via PyO3 from `engine_rs/`).

### Search Algorithm

**Iterative Deepening + Parallel Alpha-Beta + Quiescence**

1. **Iterative deepening** (depth 1→6): searches progressively deeper, using
   results from shallower searches to improve move ordering.
2. **Parallel search**: the root position fans out moves to worker processes.
   The first move is searched sequentially to establish a baseline score
   (aspiration window), then remaining moves run in parallel with a tighter
   α/β window. Moves that fail outside the window are re-searched at full width.
3. **Alpha-beta pruning**: standard minimax with α/β cutoffs.
4. **Quiescence search** (depth up to 4): at leaf nodes, continues searching
   tactical moves (captures, promotions, **and drops near the enemy king**)
   to avoid the horizon effect.
5. **Transposition table (TT)**: per-process hash table storing exact/bound
   scores and best moves for positions already evaluated.
6. **Null-move pruning**: skips a turn to test if position is so good we can
   prune. **Disabled when opponent has pieces in hand** (crazyhouse drops
   make null-move unsafe — opponent can drop a piece and create threats).
7. **Late Move Reduction (LMR)**: searches late quiet moves at reduced depth,
   re-searching at full depth only if they improve α.
8. **Killer moves + history heuristic**: move ordering improvements.

### Evaluation Function (`evaluate_position`)

- **Material**: piece values (P=100, N=320, B=330, R=500, Q=900, K=20000)
- **Hand pieces**: valued higher than board pieces (drop flexibility)
- **Center control**: bonus for pieces on central squares
- **King safety**: bonus for friendly pieces near own king, penalty for exposed king
- **King attack zone**: bonus for pieces attacking squares around enemy king
- **Pawn structure**: connected pawns bonus, passed pawn bonus
- **Piece development**: penalty for undeveloped pieces in opening
- **Drop threat**: bonus for having pieces in hand

### Move Cache (`move_cache.db`)

SQLite database storing `(position_hash, depth) → best_move`.
- Persists across sessions — no need to recalculate known positions.
- Position hash includes: board, hands, turn, castling rights, en passant.
- **Must be cleared** when evaluation function or search logic changes
  (cached moves may no longer be optimal under new logic).

## Browser Bot (`play_online.py`)

### Flow

```
launch_chrome() → login_chess_com() → auto_loop:
  ├── create_minihouse_game(casual, 30+30)
  ├── wait_for_game_start()
  ├── play_game():
  │     ├── detect_our_color()
  │     ├── loop:
  │     │   ├── read_board_from_dom()
  │     │   ├── get_ai_move() [with cycle avoidance]
  │     │   ├── make_move_on_board() / handle_promotion()
  │     │   └── wait for opponent
  │     └── detect game result
  └── dismiss_game_over() → repeat
```

### Key Components

- **Chrome/CDP**: launches Chrome with a persistent profile (`--user-data-dir`),
  connects via Chrome DevTools Protocol. Headless mode auto-detected for servers.
- **Board reading**: parses DOM (`.piece` elements with CSS classes like `square-XY`)
  to reconstruct the board state, including pocket/hand pieces.
- **Move execution**: clicks source → destination squares using grid coordinates.
  Dynamic square size from DOM (`board_rect.width / 8`).
- **Promotion handling**: chess.com shows a 2×2 overlay at the destination;
  clicks the correct quadrant based on desired piece.
- **Flip detection**: determines board orientation from clock positions and activity.

### Cycle Avoidance

Instead of tracking repeated positions (which blocks good moves), the bot tracks
the **sequence of its own moves** and detects repeating cycles of length 1–5:

```
A, A           → cycle length 1 (same move twice)
A, B, A, B     → cycle length 2
A, B, C, A, B, C → cycle length 3
```

When a candidate move would create a cycle:
1. Try alternative moves from AI top-N
2. Fall back to any non-cycling legal move
3. If all moves cycle, play the AI's choice anyway

### Stop Flag

Create `.stop_after_game` file in the project root to stop the bot after the
current game finishes (auto-deleted after stopping).

## Crazyhouse-Specific Design Decisions

### Why drops in quiescence search matter

In standard chess, quiescence only needs captures and promotions. In crazyhouse,
a drop (placing a captured piece from hand onto the board) can deliver checkmate
or create devastating threats. Without considering drops in quiescence, the engine
suffers severe horizon effects — it evaluates a position as losing (-1413) when
it actually has a forced mate via drops.

Only "tactical" drops are included (pieces dropped within distance 2 of the enemy
king, or knight drops that attack the king) to keep the search tree manageable.

### Why null-move pruning is restricted

Null-move pruning assumes "if I skip my turn and I'm still fine, this position
is good." In crazyhouse, the opponent can always drop a piece — skipping a turn
is never safe when the opponent has pieces in hand. We disable null-move pruning
entirely when `opponent_hand_count > 0`.

### Why the aspiration window helps

Without aspiration windows, each parallel worker searches with α=-∞, β=+∞,
meaning zero pruning benefit. By searching the first (likely best) move
sequentially and using its score ±150cp as the window, workers can prune
significantly more branches. Moves that fall outside the window get re-searched
at full width to ensure correctness.
