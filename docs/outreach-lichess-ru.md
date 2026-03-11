# Письмо Lichess — Discord / Forum

> **Это русская версия для твоего review.** Отправлять нужно НА АНГЛИЙСКОМ — перевод ниже.  
> **Куда:** Discord https://discord.gg/lichess (канал #programming)  
> **Также:** форум https://lichess.org/forum/lichess-feedback  
> **Также:** GitHub https://github.com/lichess-org/lila/discussions

---

## 🇷🇺 Русская версия (для чтения)

Привет, сообщество Lichess! 👋

Меня зовут Владимир, я бэкенд-разработчик. Я создал open-source движок для **6×6 Crazyhouse (Minihouse)** — шахматный вариант с доской 6×6 и Crazyhouse-механикой сбросов. Движок написан на Rust с Python-биндингами, использует классический alpha-beta поиск (без нейросетей).

### Что за движок

- **Rust-ядро** (~3300 строк) с Python-биндингами через PyO3
- Alpha-beta + PVS + quiescence search, глубина 8–10 ходов
- Функция оценки, специально настроенная под Crazyhouse (угрозы сброса, фигуры в руке, безопасность короля)
- 27 500+ предрассчитанных позиций из self-play обучения
- Достиг **#1 в рейтинге Minihouse** на chess.com
- Полностью open source: https://github.com/DoroninDobroCorp/MiniChessVovka

### Что я хочу предложить Lichess

Я бы хотел **бесплатно вложить** этот проект в экосистему Lichess. Варианты, которые вижу:

1. **Бот-аккаунт** через Lichess Bot API — если вариант 6×6 Crazyhouse поддерживается или может быть добавлен
2. **Адаптация движка под стандартный Crazyhouse (8×8)** — Lichess уже поддерживает Crazyhouse, и архитектура движка позволяет масштабировать на другую размерность доски
3. **Инструмент анализа** для варианта
4. **Бот с режимом обучения** — разные уровни сложности, подсказки, разбор ошибок

### Масштабирование

Архитектура движка параметризована — eval-функция и параметры поиска настраиваются под конкретный вариант. Это значит, что при наличии правил, я могу создать движки для других вариантов тоже. Мне интересно развивать это направление.

### Публикации

Проект получил хорошие отзывы в сообществе разработчиков:
- **Статья на Хабре** (4000+ просмотров): https://habr.com/ru/articles/1008978/
- **Статья на Dev.to** (англ.): https://dev.to/doronindobro/i-built-a-chess-engine-for-6x6-crazyhouse-now-its-1-on-chesscom-43lb
- Комментаторы из сообщества (включая человека, который раньше работал с chess.com) посоветовали мне обратиться и к Lichess тоже

### Почему бесплатно

Lichess — это open-source проект, который делает шахматы доступными для всех. Мой движок — тоже open-source. Мне важнее опыт и то, чтобы проект приносил пользу людям, чем деньги. Я готов адаптировать код под любой API или протокол, который использует Lichess.

Буду рад обсудить!

Владимир

---

## 🇬🇧 English version (ДЛЯ ОТПРАВКИ)

### Discord-сообщение (короткое, для #programming)

Hey Lichess community! 👋

I've built an open-source engine for **6×6 Crazyhouse (Minihouse)** — a chess variant with a 6×6 board and Crazyhouse drop mechanics. Written in Rust (~3,300 LOC) with Python bindings via PyO3. Classical alpha-beta search, no neural networks. Reached **#1 on chess.com's Minihouse leaderboard**.

I'd love to **contribute this to Lichess for free** — either as:
- A **bot account** via the Bot API (if the variant can be supported)
- **Adapting the engine for standard 8×8 Crazyhouse** (the architecture scales)
- A **training bot** with adjustable difficulty levels

The engine architecture is parameterized and can be scaled to other variants too.

Articles about the project:
- Habr (Russian, 4K+ views): https://habr.com/ru/articles/1008978/
- Dev.to (English): https://dev.to/doronindobro/i-built-a-chess-engine-for-6x6-crazyhouse-now-its-1-on-chesscom-43lb
- GitHub: https://github.com/DoroninDobroCorp/MiniChessVovka

Community members (including someone who previously worked with chess.com) suggested I reach out to Lichess as well, given the open-source nature of both projects.

I'm happy to adapt the code to any API or protocol Lichess uses. Would there be interest in something like this?

Vladimir

---

### Форум-пост (длинный, для lichess-feedback)

**Title: Open-Source 6×6 Crazyhouse Engine — Free Contribution to Lichess**

Hi everyone,

I'm Vladimir, a backend developer. Over the past 9 months, I've built an open-source chess engine specifically for **6×6 Crazyhouse (Minihouse)**. The engine reached #1 on chess.com's Minihouse leaderboard using pure alpha-beta search — no neural networks.

**Technical specs:**
- Rust core (~3,300 LOC) with Python bindings via PyO3
- Alpha-beta + PVS + quiescence search, depth 8–10
- Crazyhouse-specific eval: drop threats, hand piece valuation, king safety
- 27,500+ cached positions from self-play training

**I'd like to contribute this to Lichess for free.** Some ideas:
1. **Bot account** via Bot API — if the 6×6 variant could be supported
2. **Adapt for standard Crazyhouse (8×8)** — the architecture is parameterized and scalable
3. **Training mode** with adjustable difficulty, hints, and game analysis
4. **Scale to other variants** — the engine can be adapted to different rule sets

The project has been well-received in the developer community:
- Habr article (4K+ views): https://habr.com/ru/articles/1008978/
- Dev.to article: https://dev.to/doronindobro/i-built-a-chess-engine-for-6x6-crazyhouse-now-its-1-on-chesscom-43lb
- Full source: https://github.com/DoroninDobroCorp/MiniChessVovka

Community members specifically recommended reaching out to Lichess given its open-source philosophy and official bot support.

I love what Lichess stands for — free, open-source chess for everyone. My engine shares that spirit. I'm ready to adapt the code to any format, protocol, or API that Lichess uses.

Looking forward to hearing your thoughts!

Vladimir
