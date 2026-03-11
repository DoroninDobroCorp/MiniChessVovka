🇬🇧 [English](#-english) | 🇷🇺 [Русский](#-русский)

---

# 🇬🇧 English

<div align="center">

# ♟️ MiniChess

**A Rust-powered 6×6 Crazyhouse chess engine that reached #1 in the world 🏆**

*Alpha-beta search · PyO3 bindings · Self-play training · Chess.com bot*

[![Rust](https://img.shields.io/badge/Engine-Rust-b7410e?logo=rust&logoColor=white)](engine_rs/)
[![PyO3](https://img.shields.io/badge/Bindings-PyO3-3776ab?logo=python&logoColor=white)](https://pyo3.rs)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

<br>

<img src="assets/screenshots/top1.jpg" width="420" alt="MiniChess — #1 in the world" />

*☝️ Yes, that's #1 on Chess.com minihouse leaderboard*

</div>

---

> 🤯 **Crazyhouse** — captured pieces go to your "hand" and can be dropped back onto the board on any empty square. This engine plays a 6×6 variant ("minihouse").

## 🏆 Results

The bot plays on Chess.com in the **minihouse** variant and has reached the **#1 spot on the global leaderboard**:

<div align="center">
<img src="assets/screenshots/win_vs_top2.jpg" width="420" alt="Winning against the former #1" />

*Beating the former top player 💪*
</div>

The engine trains overnight via self-play, improving its opening book and evaluation every day 📈

## 🦀 Engine Highlights

The core engine is written in **Rust** (~3 300 LOC) and exposed to Python via [PyO3](https://pyo3.rs):

| Module | LOC | What it does |
|--------|-----|--------------|
| [`search.rs`](engine_rs/src/search.rs) | 1 011 | Parallel alpha-beta with PVS, LMR, null-move pruning, aspiration windows |
| [`gamestate.rs`](engine_rs/src/gamestate.rs) | 755 | Full move generation for 6×6 Crazyhouse (incl. drops) |
| [`eval.rs`](engine_rs/src/eval.rs) | 440 | Crazyhouse-tuned evaluation (material, king safety, drops) |
| [`types.rs`](engine_rs/src/types.rs) | 331 | Board representation and core types |
| [`cache.rs`](engine_rs/src/cache.rs) | 96 | SQLite-backed transposition table (4M entries) |
| [`zobrist.rs`](engine_rs/src/zobrist.rs) | 74 | Position hashing |

### 🔍 Search Features

- 🌀 **Iterative deepening** (depth 1 → 10) with aspiration windows
- ⚡ **Parallel search** — root moves fanned out to worker threads via Rayon
- 🎯 **PVS + LMR** — Principal Variation Search with Late Move Reduction
- 💥 **Quiescence search** — captures, promotions, and tactical drops near enemy king
- 🚫 **Null-move pruning** — automatically disabled when opponent holds pieces in hand
- 💾 **Transposition table** — Zobrist hashing, 4M entries, persisted to SQLite across sessions

### ⚖️ Evaluation

| Factor | Details |
|--------|---------|
| Material | P=100 · N=320 · B=330 · R=500 · Q=900 · K=20 000 |
| Hand pieces | Valued 60–100 % higher than on-board (instant deployment) 🖐️ |
| King safety | Pawn shield +55/pawn, exposed king up to −390 penalty 🛡️ |
| Center control | +12 inner center, +6 extended center |
| Drop threats | Progressive bonus scaling with pieces in hand 📈 |

> Full writeup → [`docs/evaluation_strategy.md`](docs/evaluation_strategy.md)

## 🚀 Quick Start

### 🔧 Prerequisites

- **Rust** toolchain (`rustup`)
- Python 3.11+ (for GUI & bot)

### 🎮 Build & Run

```bash
git clone <repo-url> && cd MiniChess

# Build the Rust engine
cd engine_rs
pip install maturin
maturin develop --release
cd ..

# Install Python deps
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Play!
./play.sh
```

### 🧠 Self-Play Training

```bash
./train.sh          # Ctrl+C to stop gracefully
```

### 🤖 Chess.com Bot

```bash
cp .env.example .env   # add your credentials
pip install -r requirements.txt
python -m playwright install chromium

./bot_start.sh casual  # or: rated
./bot_stop.sh
./monitor_bot.sh
```

> ⚠️ Make sure you comply with chess.com's Terms of Service.

## 🏗️ Architecture

```
                    ┌──────────────────────────────┐
                    │   minichess_engine (Rust)     │
                    │                              │
  ai.py ──PyO3──▶  │  search.rs ◄── eval.rs       │
                    │      │           │            │
                    │  gamestate.rs  zobrist.rs     │
                    │      │                       │
                    │  cache.rs (SQLite)            │
                    └──────────────────────────────┘
                              ▲
      ┌───────────────────────┼────────────────────┐
      │                       │                    │
  main.py + gui.py      play_online.py       self_play.py
  (Pygame GUI)          (Chess.com bot)      (Training)
```

## 📂 Project Layout

```
engine_rs/              ← Rust engine (core)
  src/
    search.rs           — parallel alpha-beta + quiescence
    eval.rs             — position evaluation
    gamestate.rs        — move generation & board state
    types.rs            — core types & board representation
    cache.rs            — SQLite transposition table
    zobrist.rs          — position hashing
    lib.rs              — PyO3 module entry point

*.py                    ← Python layer (GUI, bot, training)
  ai.py                 — AI wrapper delegating to Rust
  gamestate.py          — game rules & state management
  gui.py                — Pygame board rendering
  main.py               — game loop entry point
  play_online.py        — chess.com browser bot
  config.py / pieces.py / utils.py

docs/                   ← Documentation
tests/                  ← Test suite
```

## 📖 Documentation

| Doc | Content |
|-----|---------|
| [Architecture](docs/ARCHITECTURE.md) | System design & component interactions |
| [Evaluation Strategy](docs/evaluation_strategy.md) | Detailed scoring heuristics |
| [Improvement Roadmap](docs/IMPROVEMENTS.md) | Planned enhancements |

## 📝 License

[MIT License](LICENSE) — free to use, modify, and distribute.

---

<div align="center">

*Built with 🦀 Rust + 🐍 Python + ☕ lots of coffee*

</div>

---

# 🇷🇺 Русский

<div align="center">

# ♟️ MiniChess

**Шахматный движок для 6×6 Crazyhouse на Rust, занявший 1-е место в мире 🏆**

*Alpha-beta поиск · PyO3 привязки · Обучение через самоигру · Бот для Chess.com*

[![Rust](https://img.shields.io/badge/Engine-Rust-b7410e?logo=rust&logoColor=white)](engine_rs/)
[![PyO3](https://img.shields.io/badge/Bindings-PyO3-3776ab?logo=python&logoColor=white)](https://pyo3.rs)
[![License](https://img.shields.io/badge/License-Private-grey)]()

<br>

<img src="assets/screenshots/top1.jpg" width="420" alt="MiniChess — №1 в мире" />

*☝️ Да, это первое место в рейтинге minihouse на Chess.com*

</div>

---

> 🤯 **Crazyhouse** — взятые фигуры попадают в «руку» и могут быть выставлены обратно на доску на любое свободное поле. Этот движок играет в вариант 6×6 («minihouse»).

## 🏆 Результаты

Бот играет на Chess.com в варианте **minihouse** и занял **1-е место в мировом рейтинге**:

<div align="center">
<img src="assets/screenshots/win_vs_top2.jpg" width="420" alt="Победа над бывшим №1" />

*Победа над бывшим лидером 💪*
</div>

Движок тренируется ночами через самоигру, ежедневно улучшая дебютную книгу и оценочную функцию 📈

## 🦀 Ключевые особенности движка

Ядро движка написано на **Rust** (~3 300 строк кода) и подключается к Python через [PyO3](https://pyo3.rs):

| Модуль | Строк | Что делает |
|--------|-------|------------|
| [`search.rs`](engine_rs/src/search.rs) | 1 011 | Параллельный alpha-beta с PVS, LMR, null-move pruning, aspiration windows |
| [`gamestate.rs`](engine_rs/src/gamestate.rs) | 755 | Полная генерация ходов для 6×6 Crazyhouse (включая выставление фигур) |
| [`eval.rs`](engine_rs/src/eval.rs) | 440 | Оценочная функция, настроенная под Crazyhouse (материал, безопасность короля, выставление) |
| [`types.rs`](engine_rs/src/types.rs) | 331 | Представление доски и базовые типы |
| [`cache.rs`](engine_rs/src/cache.rs) | 96 | Таблица транспозиций на SQLite (4M записей) |
| [`zobrist.rs`](engine_rs/src/zobrist.rs) | 74 | Хеширование позиций |

### 🔍 Возможности поиска

- 🌀 **Итеративное углубление** (глубина 1 → 10) с aspiration windows
- ⚡ **Параллельный поиск** — корневые ходы распределяются по потокам через Rayon
- 🎯 **PVS + LMR** — Principal Variation Search с Late Move Reduction
- 💥 **Поиск покоя (quiescence)** — взятия, превращения и тактические выставления вблизи вражеского короля
- 🚫 **Null-move pruning** — автоматически отключается, когда у противника есть фигуры в руке
- 💾 **Таблица транспозиций** — Zobrist хеширование, 4M записей, сохраняется в SQLite между сессиями

### ⚖️ Оценочная функция

| Фактор | Подробности |
|--------|-------------|
| Материал | P=100 · N=320 · B=330 · R=500 · Q=900 · K=20 000 |
| Фигуры в руке | Ценятся на 60–100 % выше, чем на доске (мгновенное развёртывание) 🖐️ |
| Безопасность короля | Пешечное прикрытие +55/пешка, открытый король — штраф до −390 🛡️ |
| Контроль центра | +12 внутренний центр, +6 расширенный центр |
| Угрозы выставления | Прогрессивный бонус, растущий с количеством фигур в руке 📈 |

> Подробное описание → [`docs/evaluation_strategy.md`](docs/evaluation_strategy.md)

## 🚀 Быстрый старт

### 🔧 Предварительные требования

- Тулчейн **Rust** (`rustup`)
- Python 3.11+ (для GUI и бота)

### 🎮 Сборка и запуск

```bash
git clone <repo-url> && cd MiniChess

# Собрать движок на Rust
cd engine_rs
pip install maturin
maturin develop --release
cd ..

# Установить Python-зависимости
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Играть!
./play.sh
```

### 🧠 Обучение через самоигру

```bash
./train.sh          # Ctrl+C для корректной остановки
```

### 🤖 Бот для Chess.com

```bash
cp .env.example .env   # добавьте свои учётные данные
pip install -r requirements.txt
python -m playwright install chromium

./bot_start.sh casual  # или: rated
./bot_stop.sh
./monitor_bot.sh
```

> ⚠️ Убедитесь, что вы соблюдаете Условия использования Chess.com.

## 🏗️ Архитектура

```
                    ┌──────────────────────────────┐
                    │   minichess_engine (Rust)     │
                    │                              │
  ai.py ──PyO3──▶  │  search.rs ◄── eval.rs       │
                    │      │           │            │
                    │  gamestate.rs  zobrist.rs     │
                    │      │                       │
                    │  cache.rs (SQLite)            │
                    └──────────────────────────────┘
                              ▲
      ┌───────────────────────┼────────────────────┐
      │                       │                    │
  main.py + gui.py      play_online.py       self_play.py
  (Pygame GUI)          (Бот Chess.com)      (Обучение)
```

## 📂 Структура проекта

```
engine_rs/              ← Движок на Rust (ядро)
  src/
    search.rs           — параллельный alpha-beta + quiescence
    eval.rs             — оценка позиции
    gamestate.rs        — генерация ходов и состояние доски
    types.rs            — базовые типы и представление доски
    cache.rs            — таблица транспозиций на SQLite
    zobrist.rs          — хеширование позиций
    lib.rs              — точка входа модуля PyO3

*.py                    ← Python-слой (GUI, бот, обучение)
  ai.py                 — обёртка ИИ, делегирующая в Rust
  gamestate.py          — правила игры и управление состоянием
  gui.py                — отрисовка доски на Pygame
  main.py               — точка входа игрового цикла
  play_online.py        — браузерный бот для Chess.com
  config.py / pieces.py / utils.py

docs/                   ← Документация
tests/                  ← Тесты
```

## 📖 Документация

| Документ | Содержание |
|----------|------------|
| [Архитектура](docs/ARCHITECTURE.md) | Проектирование системы и взаимодействие компонентов |
| [Стратегия оценки](docs/evaluation_strategy.md) | Подробные эвристики оценки |
| [План улучшений](docs/IMPROVEMENTS.md) | Запланированные доработки |

## 📝 Лицензия

Частный проект.

---

<div align="center">

*Создано с 🦀 Rust + 🐍 Python + ☕ литрами кофе*

</div>
