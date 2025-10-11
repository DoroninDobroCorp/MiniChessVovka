# Будущие Улучшения для Mini Chess 6x6 Crazyhouse

Этот документ содержит список рекомендованных улучшений, которые можно реализовать для повышения силы AI, скорости работы и качества кода.

---

## 🚀 Срочные улучшения (быстрая реализация + большой эффект)

### 1. Opening Book (Библиотека дебютов)
**Проблема:** AI тратит 10-60 секунд на расчёт первых 5-8 ходов, хотя дебютные позиции хорошо изучены.

**Решение:**
- Создать базу данных из 50-100 лучших дебютных позиций
- Сохранить первые 5-8 ходов для популярных дебютов
- Формат: SQLite таблица `openings(position_hash, move, frequency)`

**Реализация:**
```python
def load_opening_book():
    """Загружает дебютную книгу из opening_book.db"""
    conn = sqlite3.connect('opening_book.db')
    # ... загрузка
    
def get_opening_move(position_hash):
    """Возвращает дебютный ход если позиция в книге"""
    return opening_book.get(position_hash)
```

**Эффект:**
- ⚡ Мгновенные первые 5-8 ходов (0.01с вместо 10-60с)
- 📈 Более качественная игра в дебюте

**Оценка времени:** 2-4 часа

---

### 2. Aspiration Windows
**Проблема:** Iterative deepening работает без aspiration windows, что замедляет поиск.

**Решение:**
- Добавить "окна ожидания" на основе предыдущих итераций
- Использовать узкий диапазон [alpha, beta] вокруг предыдущего результата
- При выходе за границы - расширять окно

**Реализация:**
```python
# В функции find_best_move, внутри iterative deepening
aspiration_window = 50
for d in range(1, depth + 1):
    if d >= 4 and best_score is not None:
        alpha = best_score - aspiration_window
        beta = best_score + aspiration_window
    else:
        alpha, beta = -float('inf'), float('inf')
    
    score, move = minimax_alpha_beta(gamestate, d, alpha, beta, is_maximizing)
    
    # Если вышли за границы - повторить с полными границами
    if score <= alpha or score >= beta:
        score, move = minimax_alpha_beta(gamestate, d, -float('inf'), float('inf'), is_maximizing)
```

**Эффект:**
- ⚡ +20-30% скорости в мидгейме
- 📉 Меньше узлов для исследования

**Оценка времени:** 1-2 часа

---

### 3. Null-Move Pruning
**Проблема:** AI исследует все ходы даже когда позиция явно выигрышная.

**Решение:**
- Пропустить ход (null move)
- Если даже после этого позиция выигрышная - можно отсечь ветку
- Уменьшить глубину поиска на 2-3 при null-move

**Реализация:**
```python
def minimax_alpha_beta(gamestate, depth, alpha, beta, maximizing_player):
    # ... existing code ...
    
    # Null-move pruning (для не-концевых узлов и не-PV узлов)
    if depth >= 3 and not gamestate.is_in_check(gamestate.current_turn):
        # Симулируем пропуск хода
        gamestate.current_turn = get_opposite_color(gamestate.current_turn)
        null_score = -minimax_alpha_beta(gamestate, depth - 3, -beta, -beta + 1, not maximizing_player)
        gamestate.current_turn = get_opposite_color(gamestate.current_turn)
        
        if null_score >= beta:
            return beta  # Отсечение
    
    # ... rest of minimax ...
```

**Эффект:**
- ⚡ +30-50% скорости поиска
- 🎯 Особенно эффективно в эндшпиле

**Оценка времени:** 2-3 часа

---

### 4. Чистка кода и оптимизация
**Проблема:** ~~Множество DEBUG принтов замедляют работу~~ ✅ **ИСПРАВЛЕНО**

**Дополнительно:**
- Добавить type hints для всех функций
- Написать docstrings в едином стиле
- Профилировать код для поиска узких мест

**Реализация:**
```python
# Профилирование
import cProfile
cProfile.run('ai.find_best_move(gamestate, depth=16)', 'ai_profile.stats')

# Анализ
import pstats
p = pstats.Stats('ai_profile.stats')
p.sort_stats('cumulative').print_stats(20)
```

**Эффект:**
- ~~⚡ +5-10% скорости~~ ✅ Достигнуто
- 🧹 Читаемый код
- 📊 Понимание узких мест

**Оценка времени:** 2-4 часа

---

## 🎯 Средние улучшения (несколько дней работы)

### 5. Late Move Reduction (LMR)
**Проблема:** Все ходы исследуются на полную глубину, даже явно плохие.

**Решение:**
- После исследования нескольких лучших ходов на полную глубину
- Остальные ходы исследовать на уменьшенную глубину (depth - 2)
- Если найден хороший ход - повторить поиск на полную глубину

**Эффект:**
- ⚡ +20-30% скорости
- 🎯 Можно увеличить depth на 1-2

**Оценка времени:** 4-6 часов

---

### 6. Principal Variation Search (PVS)
**Решение:**
- Первый ход исследуется с полным окном [alpha, beta]
- Остальные - с нулевым окном [alpha, alpha+1] (scout search)
- При опровержении - повторный поиск с полным окном

**Эффект:**
- ⚡ +15-25% скорости
- 🎯 Более точная оценка лучших ходов

**Оценка времени:** 6-8 часов

---

### 7. Улучшенная оценочная функция
**Текущая:** Базовая оценка (материал + позиция + центр + король)

**Добавить:**
- Mobility (подвижность фигур)
- King safety (продвинутая оценка безопасности короля)
- Piece coordination (взаимодействие фигур)
- Pawn shield (пешечный щит короля)
- Outposts (форпосты для коней)

**Эффект:**
- 📈 +100-200 ELO
- 🎯 Более точная позиционная игра

**Оценка времени:** 8-12 часов

---

## 🔥 Долгосрочные улучшения (недели работы)

### 8. Bitboards (Битовые доски)
**Проблема:** 2D массив `board[r][c]` медленный для операций.

**Решение:**
- Представить доску как набор 64-битных чисел (bitboards)
- Каждая фигура - отдельный bitboard
- Использовать битовые операции (&, |, ^, ~, <<, >>)

**Пример:**
```python
class Bitboard:
    def __init__(self):
        self.white_pawns = 0b0000000000000000  # 6x6 = 36 бит
        self.black_pawns = 0b0000000000000000
        # ... для каждой фигуры
    
    def get_piece_attacks(self, square):
        """Возвращает атакуемые клетки за O(1)"""
        return ATTACK_TABLES[piece_type][square]
```

**Эффект:**
- ⚡ **x10-20 ускорение** операций
- 🎯 Depth 20-24 становится реальным
- 📈 +300-500 ELO от глубины

**Оценка времени:** 40-80 часов (полная переработка)

---

### 9. Neural Network Evaluation
**Текущее:** Рукописная оценочная функция

**Решение:**
- Обучить нейросеть на self-play партиях
- Архитектура: CNN или Transformer
- Вход: board state (6x6x12 каналов для каждой фигуры)
- Выход: value (-1 до +1) + policy (вероятности ходов)

**Реализация:**
```python
# Уже есть заготовка в nn/model.py!
import torch
from nn.model import ChessNet

model = ChessNet()
model.load_state_dict(torch.load('best_model.pth'))

def nn_evaluate(board_state):
    tensor = board_to_tensor(board_state)
    with torch.no_grad():
        value, policy = model(tensor)
    return value.item()
```

**Обучение:**
1. Self-play (AI играет сам с собой)
2. Сохранение партий
3. Обучение на результатах
4. Итеративное улучшение (AlphaZero style)

**Эффект:**
- 📈 +300-500 ELO
- 🎯 Более точная оценка сложных позиций
- 🧠 Понимание тонких нюансов

**Оценка времени:** 60-120 часов + GPU для обучения

---

### 10. Monte Carlo Tree Search (MCTS) + NN
**Решение:**
- Комбинация MCTS с нейросетевой оценкой (как AlphaZero)
- Уже есть заготовка в `nn/mcts.py`!

**Алгоритм:**
1. Selection: выбор узла по UCB
2. Expansion: расширение узла
3. Evaluation: оценка через NN
4. Backpropagation: обновление статистики

**Эффект:**
- 📈 +500-800 ELO
- 🎯 ~2800-3000 ELO (топовый уровень)
- 🧠 AlphaZero-подобная сила

**Оценка времени:** 80-150 часов + GPU

---

### 11. Endgame Tablebase
**Решение:**
- Предрасчитать все позиции с ≤4 фигурами
- Сохранить в базу данных (SQLite или rocksDB)
- Использовать для идеальной игры в эндшпиле

**Формат:**
```
position_hash -> {result: 'WIN/LOSS/DRAW', moves_to_mate: 12}
```

**Эффект:**
- ♟️ Идеальная игра в эндшпиле
- 📈 +50-100 ELO в эндшпиле
- ⏱️ Мгновенные ходы в простых позициях

**Оценка времени:** 30-50 часов + вычислительная мощность

---

## 📊 Приоритеты реализации

### Фаза 1: Быстрые победы (1-2 недели)
1. ✅ Чистка DEBUG кода (завершено)
2. Opening Book
3. Aspiration Windows
4. Null-Move Pruning

**Результат:** +40-60% скорости, depth 18-20, ~2200-2400 ELO

---

### Фаза 2: Алгоритмические улучшения (2-4 недели)
5. Late Move Reduction
6. Principal Variation Search
7. Улучшенная оценочная функция

**Результат:** еще +30% скорости, ~2400-2600 ELO

---

### Фаза 3: Масштабные изменения (2-4 месяца)
8. Bitboards (полная переработка)
9. Neural Network Evaluation
10. MCTS + NN (AlphaZero approach)
11. Endgame Tablebase

**Результат:** ~2800-3200 ELO, профессиональный уровень

---

## 🛠️ Инструменты и библиотеки

### Для обучения нейросетей:
- PyTorch (уже есть в requirements.txt)
- TensorBoard для визуализации
- CUDA для GPU ускорения

### Для профилирования:
```bash
# Профилирование Python
python -m cProfile -o profile.stats main.py

# Анализ
python -c "import pstats; pstats.Stats('profile.stats').sort_stats('cumulative').print_stats(30)"

# Визуализация
pip install snakeviz
snakeviz profile.stats
```

### Для тестирования силы:
```python
# AI vs AI турнир
def tournament(ai_versions, games_per_pair=10):
    for ai1, ai2 in combinations(ai_versions, 2):
        results = play_matches(ai1, ai2, games_per_pair)
        print(f"{ai1.name} vs {ai2.name}: {results}")
```

---

## 📚 Ресурсы для изучения

### Шахматное программирование:
- Chess Programming Wiki: https://www.chessprogramming.org
- Stockfish source code: https://github.com/official-stockfish/Stockfish
- Sunfish (простой движок на Python): https://github.com/thomasahle/sunfish

### AlphaZero / Нейросети:
- AlphaZero paper: https://arxiv.org/abs/1712.01815
- Leela Chess Zero: https://lczero.org
- PyTorch tutorial: https://pytorch.org/tutorials/

### Оптимизация:
- Python Performance Tips: https://wiki.python.org/moin/PythonSpeed
- Numba (JIT compilation): http://numba.pydata.org

---

## 📝 Заметки

- **Текущая сила:** ~2000-2200 ELO (depth 16)
- **Потенциал без нейросетей:** ~2600-2800 ELO (bitboards + оптимизации)
- **Потенциал с нейросетями:** ~3000-3200 ELO (MCTS + NN)

**Приоритет:** Начните с Фазы 1 (Opening Book, Aspiration, Null-Move) - это даст максимальный эффект за минимальное время.

---

*Документ создан: 2024*  
*Последнее обновление: после чистки DEBUG кода*
