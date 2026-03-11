# Письмо Chess.com — Эрику Аллебесту (Erik Allebest)

> **Это русская версия для твоего review.** Отправлять нужно НА АНГЛИЙСКОМ — перевод ниже.  
> **Куда:** DM на https://www.chess.com/member/erik  
> **Также:** пост в https://www.chess.com/club/chess-com-developer-community

---

## 🇷🇺 Русская версия (для чтения)

Привет, Эрик!

Меня зовут Владимир, я бэкенд-разработчик. Пишу по совету участников сообщества — после публикации моей статьи о проекте мне посоветовали обратиться к вам напрямую.

### Что я сделал

Я создал **open-source шахматный движок для Minihouse (6×6 Crazyhouse)** — варианта, который есть на chess.com в разделе Variants.

Характеристики движка:
- **Rust-ядро** (~3300 строк) с Python-биндингами через PyO3
- Alpha-beta поиск + PVS + quiescence search, глубина **8–10 ходов**
- Функция оценки, специально настроенная под Crazyhouse-механику (угрозы сброса, фигуры в руке, безопасность короля)
- **27 500+ предрассчитанных позиций** из ночного self-play обучения
- Движок достиг **#1 в рейтинге Minihouse** на chess.com в феврале 2026

### Почему это может быть полезно chess.com

- Для 6×6 Crazyhouse **не существует других движков** — ни Stockfish, ни другие инструменты не поддерживают этот вариант
- На chess.com есть отличные боты для обычных шахмат, но **в разделе Variants нет ботов-соперников** для тренировки
- Minihouse-бот мог бы повысить вовлечённость игроков в Variants — возможность играть против бота разной силы, анализ партий, режим обучения

### Что я предлагаю

Мне бы хотелось обсудить возможность **официальной интеграции** движка как бота для Minihouse на chess.com. Варианты:
- Бот-аккаунт с разными уровнями сложности (для обучения и для челленджа)
- Движок для анализа позиций в Minihouse
- Интеграция в раздел "Play vs Computer" для Variants

Движок модульный — Rust-ядро легко адаптируется под любой интерфейс (API, WebSocket и т.д.).

### Масштабирование на другие варианты

Архитектура движка позволяет адаптировать его для **других мини-вариантов** на chess.com. Eval-функция и параметры поиска параметризованы — при наличии правил варианта, можно создать движок для любого мини-формата и **повторить тот же путь до топа рейтинга**, создавая качественных ботов для каждого.

### Публикации и отзывы

Проект получил положительные отклики в сообществе:
- **Статья на Хабре** (4000+ просмотров): https://habr.com/ru/articles/1008978/
- **Статья на Dev.to** (англ.): https://dev.to/doronindobro/i-built-a-chess-engine-for-6x6-crazyhouse-now-its-1-on-chesscom-43lb
- **GitHub** (полный исходный код): https://github.com/DoroninDobroCorp/MiniChessVovka
- Именно в комментариях на Хабре мне посоветовали связаться с вами — человек, который раньше работал с chess.com, предложил обратиться

Я знаю что аккаунт бота был забанен за fair play — и это справедливо, правила есть правила. Хотя я открыто предупреждал всех соперников в профиле и в чатах что с ними играет бот, и это был исследовательский эксперимент, а не попытка обмануть систему — я полностью понимаю позицию chess.com. Именно поэтому **официальная интеграция** имеет гораздо больше смысла, чем игровой аккаунт.

Открыт к любой форме сотрудничества. Буду рад обсудить детали или провести демо.

С уважением,
Владимир Доронин

---

## 🇬🇧 English version (ДЛЯ ОТПРАВКИ)

Hi Erik,

I'm Vladimir, a backend developer. I'm reaching out on the recommendation of community members — after publishing an article about my project, several people suggested I contact you directly.

### What I Built

I've created an **open-source chess engine for Minihouse (6×6 Crazyhouse)** — the variant available in chess.com's Variants section.

Engine specs:
- **Rust core** (~3,300 LOC) with Python bindings via PyO3
- Alpha-beta + PVS + quiescence search, depth **8–10 moves**
- Evaluation function specifically tuned for Crazyhouse mechanics (drop threats, hand piece valuation, king safety)
- **27,500+ pre-calculated positions** from overnight self-play training
- Reached **#1 on the Minihouse leaderboard** on chess.com in February 2026

### Why This Could Be Valuable for Chess.com

- There are **no existing engines** for 6×6 Crazyhouse — Stockfish and similar tools don't support this variant
- Chess.com has great bots for standard chess, but **Variants have no bot opponents** for players to practice against
- A Minihouse bot could boost engagement in the Variants section — players could practice against different difficulty levels, analyze games, and learn in a training mode

### My Proposal

I'd love to discuss **officially integrating** this engine as a Minihouse bot on chess.com:
- Bot account with adjustable difficulty levels (for learning and for challenge)
- Position analysis tool for Minihouse
- Integration into "Play vs Computer" for Variants

The engine is modular — the Rust core can be adapted to any interface (API, WebSocket, etc.).

### Scaling to Other Variants

The engine architecture is designed to be **adaptable to other mini-variants** on chess.com. The eval function and search parameters are configurable — given variant rules, I can build an engine for any mini-format and **replicate the path to the top of the leaderboard**, creating quality bots for each variant.

### Publications & Community Response

The project has received positive reception:
- **Habr article** (4,000+ views, Russian dev community): https://habr.com/ru/articles/1008978/
- **Dev.to article** (English): https://dev.to/doronindobro/i-built-a-chess-engine-for-6x6-crazyhouse-now-its-1-on-chesscom-43lb
- **GitHub** (full source): https://github.com/DoroninDobroCorp/MiniChessVovka
- Community members who previously collaborated with chess.com specifically recommended I reach out to you

I know the bot account was banned for fair play — and that's fair, rules are rules. Although I openly informed all opponents in my profile and in chats that they were playing against a bot, and this was a research experiment rather than an attempt to game the system — I fully understand chess.com's position. That's exactly why an **official integration** makes much more sense than a player account.

I'm open to any form of collaboration and happy to discuss details or do a live demo.

Best regards,
Vladimir Doronin
