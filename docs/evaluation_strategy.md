# MiniChess 6×6 Crazyhouse — Evaluation Strategy

> **Engine**: Rust (PyO3), Alpha-Beta + PVS/LMR/Null-move/TT/Quiescence  
> **Time control**: 90 sec/move → depth 8–10  
> **Board**: 6×6, Crazyhouse variant (captured pieces go to hand, can be dropped)  
> **Promotions**: Pawn → Rook / Knight / Bishop only (no Queen)

---

## 1. Material Values

### On-Board Pieces

| Piece  | Value (cp) | Notes |
|--------|-----------|-------|
| Pawn   | 100       | Baseline unit |
| Knight | 320       | Strong in closed positions, fork potential |
| Bishop | 330       | Slightly > Knight on 6×6 (fewer diagonals but drops create open lines) |
| Rook   | 500       | Strongest promotion target |
| Queen  | 900       | Cannot be obtained via promotion, only present if variant allows |
| King   | 20000     | Effectively infinite — checkmate ends game |

### Hand Pieces (available for drop)

| Piece  | Value (cp) | Premium vs board | Rationale |
|--------|-----------|-----------------|-----------|
| Pawn   | 200       | +100% | Instant deployment anywhere; drop near promotion rank |
| Knight | 550       | +72%  | Drop-fork threats; can drop giving check |
| Bishop | 530       | +61%  | Drop to open diagonal; pair bonus potential |
| Rook   | 800       | +60%  | Drop on enemy king file/rank = devastating |
| Queen  | 1200      | +33%  | Massive if available (rare in 6×6 no-queen-promo) |

**Why hand pieces are worth more**: In Crazyhouse, a piece in hand can be deployed instantly to any empty square. This means:
- No tempo cost to "develop" it
- Surprise factor — opponent must defend every possible drop square
- Multiple pieces in hand create combinatorial threats (progressive drop threat)

---

## 2. Positional Factors

### 2.1 Center Control

| Zone | Squares | Bonus (cp) |
|------|---------|-----------|
| Inner center | (2,2) (2,3) (3,2) (3,3) | **12** per piece |
| Extended center | (1,2) (1,3) (4,2) (4,3) (2,1) (2,4) (3,1) (3,4) | **6** per piece |

Small bonus (compared to standard chess) because 6×6 board is already cramped — center control is less decisive when drops can bypass positional advantages.

### 2.2 Mobility

| Factor | Value (cp) |
|--------|-----------|
| Each piece with ≥1 adjacent empty square | **4** |

Proxy metric — doesn't count all legal moves (too expensive), just whether each piece has at least one adjacent empty square. Rewards piece activity over passive positions.

### 2.3 Development (Opening)

| Factor | Value (cp) |
|--------|-----------|
| Each undeveloped piece on back rank (N/B/R still on rank 0 or 5) | **−20** |

Only applies in non-endgame. Penalizes leaving pieces on starting squares.

### 2.4 Tempo

| Factor | Value (cp) |
|--------|-----------|
| Side to move | **+10** |

Small bonus for initiative. Having the move = having the option to create threats first.

---

## 3. Pawn Evaluation

### 3.1 Passed Pawns

A pawn is "passed" if no enemy pawns block it on its file or adjacent files.

| Steps to promotion | Bonus (cp) | + Clear path bonus | Total max |
|--------------------|-----------|-------------------|-----------|
| 1 step | 180 | +100 | **280** |
| 2 steps | 70 | +35 | **105** |
| 3 steps | 25 | +12 | **37** |
| 4 steps | 10 | +0 | **10** |
| 5+ steps | 5 | +0 | **5** |

**Why these are much lower than standard chess**:
- Promotion gives only R/N/B (not Queen) — max promo value is 500cp, not 900
- Opponent can drop a blocker on the promotion path at any time
- "Clear path" is fragile because drops can fill empty squares instantly

### 3.2 Pawn Structure

| Factor | Value (cp) |
|--------|-----------|
| Adjacent friendly pawn (pawn chain) | **+8** per pair |
| Blocked pawn (piece directly ahead) | **−30** |

### 3.3 Drop Pawn Near Promotion

| Factor | Value (cp) |
|--------|-----------|
| Have pawn in hand + empty squares on penultimate rank | **120** base + **25** per extra square |

Reduced from original 250cp because opponent awareness of drop-promo threats means they defend against it.

---

## 4. King Safety (Critical in Crazyhouse)

### 4.1 Pawn Shield

| Factor | Value (cp) |
|--------|-----------|
| Each friendly pawn in front of king (3 squares ahead) | **+55** |
| No shield + enemy has pieces in hand → EXPOSED | **−130** × min(enemy_hand_count, 3) |

In Crazyhouse, an exposed king facing an opponent with pieces in hand is **extremely dangerous**. The penalty scales with how many pieces the opponent can drop — each piece in hand is a potential check/mate threat.

### 4.2 King Position

| Factor | Value (cp) | When |
|--------|-----------|------|
| King in center (inner 4 squares) | **−40** | Opening/middlegame |
| King on edge (back rank or side files) | **+15** | Opening/middlegame |
| King in center | **+20** | Endgame |

In crazyhouse: corners and edges are safer because fewer drop squares threaten the king. In endgame, king should be active in center.

### 4.3 King Proximity

| Factor | Value (cp) |
|--------|-----------|
| Friendly non-king piece within distance 2 of own king | **+10** |

Rewards castled/compact positions where pieces defend the king.

---

## 5. Tactical Features

### 5.1 King Attack Zone

Pieces near the enemy king contribute to attack pressure:

| Attacker type | Distance ≤2 | Distance ≤3 | Direct knight attack |
|---------------|------------|------------|---------------------|
| Knight | +0.5 | — | **+2.0** (on attack square) |
| Rook/Bishop/Queen | +1.0 | +0.3 | — |
| Pawn | +1.0 | — | — |

Total attack value × **28** cp = king attack zone score.

### 5.2 Drop Threats

| Factor | Value (cp) |
|--------|-----------|
| Each piece in hand | **+35** base |
| Progressive bonus: N×(N−1)×10 for N pieces in hand | Exponential scaling |

**Example**: 3 pieces in hand = 3×35 + 3×2×10 = 105 + 60 = **165cp** total drop threat bonus.

This captures the combinatorial explosion of threats when holding multiple pieces — each additional piece doesn't just add one threat, it multiplies possibilities.

### 5.3 Drop-Check Threats

| Factor | Value (cp) | Condition |
|--------|-----------|-----------|
| Knight in hand can drop giving check | **+40** | At least one knight-distance square from enemy king is empty |
| Rook in hand on enemy king's rank | **+25** | At least one square on enemy king's rank is empty |

These are "latent" threats — the opponent must constantly defend against potential drop-checks.

---

## 6. Rook Bonuses

| Factor | Value (cp) |
|--------|-----------|
| Rook on fully open file (no pawns) | **+35** |
| Rook on semi-open file (no friendly pawns) | **+18** |

### Bishop Pair

| Factor | Value (cp) |
|--------|-----------|
| Two bishops on board | **+45** |
| Two bishops counting hand pieces | **+22** (half bonus) |

---

## 7. Game Phase Detection

The engine detects endgame when total material < 2×Rook + 2×King (≈ 41000cp threshold).

In endgame:
- King center penalty becomes king center **bonus** (+20cp)
- King edge bonus is removed
- Development penalty is removed

---

## 8. Search Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Search depth | 8 (opening book), 8-10 (play) | Iterative deepening with time control |
| Transposition table | 4M entries | Zobrist hashing, always-replace |
| Null-move reduction | R=2 | Skip when in check or endgame |
| LMR | Reduce by 1 after first 4 moves at depth ≥ 3 | Late move reduction |
| Check extension | +1 depth | Extend search when in check |
| Quiescence | Captures + check evasions | Delta pruning with 200cp margin |
| Aspiration window | ±50cp, widening ×4 on fail | Around previous iteration's score |
| Move ordering | TT best → captures (MVV-LVA) → killers → history → quiet | Critical for pruning efficiency |

---

## 9. Design Philosophy Summary

This evaluation is tuned for **6×6 Crazyhouse** specifically:

1. **Drops > Position**: Hand pieces are valued 60-100% more than their board counterparts. In standard chess, a knight is 320cp whether in play or not. Here, a knight in hand (550cp) is worth almost as much as a rook on the board (500cp) because of its instant deployment potential.

2. **King Safety > Material**: An exposed king with no pawn shield facing 3 enemy pieces in hand suffers −390cp penalty. This means the engine will sacrifice material to maintain king safety — correct for crazyhouse where drop-mates are common.

3. **Passed Pawns are Modest**: Unlike standard chess where a passed pawn 1 step from promotion can be worth a rook, here it's only 180-280cp (vs 500cp for the rook promotion it would become). This is because the opponent can drop a blocker, and promotion gives only minor pieces.

4. **Tactical Awareness**: Drop-check threats, progressive drop danger, and king attack zone scoring ensure the engine understands the explosive tactical nature of crazyhouse.

5. **Compact Design**: ~440 lines of Rust. Every factor is computed in a single pass or two. No heavy computation — the search depth (not eval complexity) determines playing strength.

---

## 10. Comparison: Before vs After Tuning

| Scenario | Before (cp) | After (cp) | Change |
|----------|------------|-----------|--------|
| Pawn 1 step from promo | 933 | 280 | −70% |
| Rook on board | 564 | 500 | −11% |
| Knight in hand | 400 | 550 | +38% |
| Rook in hand | 650 | 800 | +23% |
| Exposed king (3 enemy hand pieces) | −240 | −390 | +63% penalty |
| Drop threat (3 pieces in hand) | 0 | 165 | NEW |
| Knight drop-check threat | 0 | 40 | NEW |

The old evaluation overvalued passed pawns and undervalued hand piece threats, leading to a playstyle that chased pawn promotions while ignoring lethal drop-mate attacks.
