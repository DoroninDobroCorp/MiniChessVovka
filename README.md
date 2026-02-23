# ♟️ MiniChess — 6×6 Crazyhouse Engine

A high-performance 6×6 **Crazyhouse** chess engine with a Rust-accelerated search backend, Pygame GUI, and a chess.com automation bot.

> **Crazyhouse** = captured pieces go to your "hand" and can be dropped back onto the board on any empty square.

## ✨ Features

- **Rust-powered search** — Alpha-beta with PVS, LMR, null-move pruning, quiescence search, and Zobrist hashing via [PyO3](https://pyo3.rs)
- **Iterative deepening** — depth 8–10 with parallel workers for strong play
- **Transposition table** — 4M entries with best-move caching across sessions (SQLite)
- **Crazyhouse-specific eval** — hand piece valuation, drop threats, king safety tuned for drops
- **Pygame GUI** — interactive board with undo, hints, AI toggle
- **Chess.com bot** — browser automation (Playwright) for minihouse games
- **Self-play training** — builds opening book via self-play with 20% exploration

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Rust toolchain (for building the engine)

### Setup

```bash
# Clone and enter project
git clone <repo-url> && cd MiniChess

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Build Rust engine
cd engine_rs
pip install maturin
maturin develop --release
cd ..
```

### Play

```bash
# Launch the GUI
./play.sh

# Or directly:
python main.py
```

### Train (Self-Play)

```bash
# Run self-play training (Ctrl+C to stop gracefully)
./train.sh
```

### Chess.com Bot

```bash
# 1. Create .env file with your credentials
cp .env.example .env
# Edit .env and add your chess.com email/password

# 2. Start bot (casual mode)
./bot_start.sh casual

# Start bot (rated mode)
./bot_start.sh rated

# Stop bot
./bot_stop.sh
```

## 🏗️ Architecture

```
ai.py  ──→  minichess_engine (Rust/PyO3)
  │              ├── search.rs    — parallel alpha-beta + quiescence
  │              ├── eval.rs      — position evaluation
  │              ├── gamestate.rs — move generation
  │              ├── cache.rs     — SQLite move cache
  │              └── zobrist.rs   — position hashing
  │
  ├── gamestate.py  — Python game rules & state management
  ├── gui.py        — Pygame board rendering
  ├── main.py       — game loop & event handling
  └── play_online.py — chess.com browser bot
```

### Search Algorithm

1. **Iterative deepening** (depth 1→10) with aspiration windows
2. **Parallel search** — fan out root moves to worker threads
3. **Alpha-beta + PVS** — Principal Variation Search with Late Move Reduction
4. **Quiescence search** — captures, promotions, and tactical drops near enemy king
5. **Null-move pruning** — disabled when opponent has pieces in hand (crazyhouse safety)
6. **Transposition table** — Zobrist hashing, 4M entries, persisted to SQLite

### Evaluation (Crazyhouse-Tuned)

| Factor | Notes |
|--------|-------|
| Material | P=100, N=320, B=330, R=500, Q=900, K=20000 |
| Hand pieces | Valued 60–100% higher than on-board (instant deployment) |
| King safety | Pawn shield +55/pawn, exposed king up to −390 penalty |
| Center control | +12 inner center, +6 extended center |
| Passed pawns | Conservative (opponent can drop blockers) |
| Drop threats | Progressive bonus scaling with pieces in hand |

> Full evaluation details in [`docs/evaluation_strategy.md`](docs/evaluation_strategy.md)

## 📁 Project Structure

| Path | Description |
|------|-------------|
| `ai.py` | AI wrapper — delegates to Rust engine |
| `gamestate.py` | Game rules, move generation, make/undo |
| `gui.py` | Pygame GUI rendering |
| `main.py` | Game loop entry point |
| `config.py` | Constants (board size, colors, dimensions) |
| `pieces.py` | Piece definitions & movement patterns |
| `utils.py` | Coordinate conversion helpers |
| `thread_utils.py` | Background threads for AI & hints |
| `play_online.py` | Chess.com browser bot (Playwright) |
| `precalc_openings.py` | Opening position precalculator |
| `engine_rs/` | Rust search engine (PyO3) |
| `engine/env.py` | RL environment wrapper |
| `nn/` | Neural network experiments (MCTS + CNN) |
| `src/` | Training scripts (self-play, scheduled) |
| `tests/` | Test suite |
| `docs/` | Architecture & strategy documentation |
| `assets/sprites/` | Chess piece images |

## 📖 Documentation

- [Architecture & Design](docs/ARCHITECTURE.md)
- [Evaluation Strategy](docs/evaluation_strategy.md)
- [Improvement Roadmap](docs/IMPROVEMENTS.md)

## 🛠️ Scripts

| Script | Purpose |
|--------|---------|
| `play.sh` | Launch GUI game |
| `train.sh` | Start self-play training |
| `bot_start.sh` | Start chess.com bot |
| `bot_stop.sh` | Stop chess.com bot |
| `check_training_health.sh` | Monitor training status |
| `training_dashboard.sh` | Training metrics dashboard |
| `monitor_bot.sh` | Bot activity monitor |

## 📝 License

Private project.
