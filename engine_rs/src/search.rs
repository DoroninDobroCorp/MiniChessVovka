use std::collections::HashMap;
use std::time::Instant;

use crate::types::*;
use crate::gamestate::GameState;
use crate::eval::{evaluate_position, CHECKMATE_SCORE, STALEMATE_SCORE};
use crate::zobrist;

const MAX_QUIESCENCE_DEPTH: i32 = 4;
// Parallel search disabled — single-threaded minimax_ab is correct and fast enough
// (parallel had bugs: no move ordering, stale TT, missing killer/history in workers)
const PARALLEL_DEPTH_THRESHOLD: i32 = 999;

// TT entry
#[derive(Clone)]
pub struct TTEntry {
    pub depth: i32,
    pub score: i32,
    pub flag: TTFlag,
    pub best_move: Move,
}

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum TTFlag {
    Exact,
    LowerBound,
    UpperBound,
}

pub struct SearchState {
    pub tt: HashMap<u64, TTEntry>,
    pub killer_moves: HashMap<i32, [Move; 2]>,
    pub history_scores: HashMap<u32, i32>, // move.data -> score
}

impl SearchState {
    pub fn new() -> Self {
        SearchState {
            tt: HashMap::with_capacity(1 << 20),
            killer_moves: HashMap::new(),
            history_scores: HashMap::new(),
        }
    }

    pub fn clear(&mut self) {
        self.tt.clear();
        self.killer_moves.clear();
        self.history_scores.clear();
    }
}

// Move ordering score
fn mvv_lva_score(gs: &GameState, m: Move, ss: &SearchState) -> i32 {
    let mut score = 0i32;

    if !m.is_drop() {
        let from = m.from_sq();
        let to = m.to_sq();
        let aggressor = gs.board[from];
        let victim = gs.board[to];

        if aggressor.is_empty() {
            return 0;
        }
        let aggressor_value = PIECE_VALUES[aggressor.piece_type().unwrap().index()];

        // Captures
        if !victim.is_empty() {
            let mut victim_value = PIECE_VALUES[victim.piece_type().unwrap().index()];
            if gs.promoted_pieces & (1u64 << to) != 0 {
                victim_value = (victim_value + PIECE_VALUES[PieceType::Pawn.index()]) / 2;
            }
            score += victim_value * 10 - aggressor_value;
        }

        // Promotion
        if m.promotion().is_some() {
            score += 900;
        }

        // King zone attack
        let piece_color = aggressor.color().unwrap();
        let enemy_king_sq = gs.king_pos[piece_color.opposite().index()];
        let ek_r = sq_row(enemy_king_sq) as i32;
        let ek_c = sq_file(enemy_king_sq) as i32;
        let to_r = sq_row(to) as i32;
        let to_c = sq_file(to) as i32;
        let dist = (to_r - ek_r).abs().max((to_c - ek_c).abs());
        if dist <= 2 {
            score += 500;
        }

        // Center
        if is_center_sq(to) {
            score += 30;
        }

        // Development
        if piece_color == Color::White && sq_row(from) == 5 && sq_row(to) < 5 {
            score += 20;
        } else if piece_color == Color::Black && sq_row(from) == 0 && sq_row(to) > 0 {
            score += 20;
        }

        // History heuristic
        score += *ss.history_scores.get(&m.data).unwrap_or(&0);

    } else {
        // Drop move
        let to = m.to_sq();
        let pt = m.drop_piece_type();
        let color = m.drop_color();

        let mut base = HAND_PIECE_VALUES[pt.index()] / 10;

        // Pawn drop near promotion
        if pt == PieceType::Pawn {
            let to_r = sq_row(to);
            if color == Color::White && to_r == 1 { base += 800; }
            else if color == Color::White && to_r == 2 { base += 200; }
            else if color == Color::Black && to_r == BOARD_SIZE - 2 { base += 800; }
            else if color == Color::Black && to_r == BOARD_SIZE - 3 { base += 200; }
        }

        if is_center_sq(to) {
            base += 50;
        }

        // Near enemy king
        let enemy_king_sq = gs.king_pos[color.opposite().index()];
        let ek_r = sq_row(enemy_king_sq) as i32;
        let ek_c = sq_file(enemy_king_sq) as i32;
        let to_r = sq_row(to) as i32;
        let to_c = sq_file(to) as i32;
        let dist = (to_r - ek_r).abs().max((to_c - ek_c).abs());
        if dist <= 1 { base += 200; }
        else if dist <= 2 { base += 100; }

        // Knight fork detection
        if pt == PieceType::Knight {
            let mut attacks = 0;
            let enemy_color = color.opposite();
            for &(dr, df) in &KNIGHT_OFFSETS {
                let nr = to_r + dr;
                let nf = to_c + df;
                if is_on_board(nr, nf) {
                    let target = gs.board[sq(nr as usize, nf as usize)];
                    if !target.is_empty() && target.color() == Some(enemy_color) {
                        attacks += 1;
                        if matches!(target.piece_type(), Some(PieceType::King) | Some(PieceType::Rook)) {
                            base += 300;
                        }
                    }
                }
            }
            if attacks >= 2 { base += 200; }
        }

        base += *ss.history_scores.get(&m.data).unwrap_or(&0);
        score = base;
    }

    score
}

fn is_center_sq(s: usize) -> bool {
    let r = sq_row(s);
    let c = sq_file(s);
    (r == 2 || r == 3) && (c == 2 || c == 3)
}

fn is_noisy_move(gs: &GameState, m: Move) -> bool {
    if m.is_drop() {
        return true;
    }
    let to = m.to_sq();
    if gs.board[to] != Piece::Empty {
        return true;
    }
    m.promotion().is_some()
}

fn is_check_move(gs: &mut GameState, m: Move) -> bool {
    gs.make_ai_move(m);
    let opponent = gs.current_turn;
    let in_check = gs.is_in_check(opponent);
    gs.undo_ai_move();
    in_check
}

fn is_drop_near_king(gs: &GameState, m: Move) -> bool {
    let to = m.to_sq();
    let color = m.drop_color();
    let enemy_king_sq = gs.king_pos[color.opposite().index()];
    let kr = sq_row(enemy_king_sq) as i32;
    let kf = sq_file(enemy_king_sq) as i32;
    let dr = sq_row(to) as i32;
    let df = sq_file(to) as i32;

    let pt = m.drop_piece_type();
    if pt == PieceType::Knight {
        if KNIGHT_OFFSETS.contains(&(kr - dr, kf - df)) {
            return true;
        }
    }
    (dr - kr).abs().max((df - kf).abs()) <= 2
}

fn get_noisy_moves(gs: &mut GameState) -> Vec<Move> {
    let legal = gs.get_legal_moves_vec();
    let mut noisy = Vec::new();
    let mut check_candidates = Vec::new();

    for m in &legal {
        if m.is_drop() {
            if is_drop_near_king(gs, *m) {
                noisy.push(*m);
            }
            continue;
        }
        let to = m.to_sq();
        let is_capture = gs.board[to] != Piece::Empty;
        let is_promotion = m.promotion().is_some();
        if is_capture || is_promotion {
            noisy.push(*m);
        } else {
            check_candidates.push(*m);
        }
    }

    // Also include quiet moves that give check (limit to 12)
    let limit = check_candidates.len().min(12);
    for &m in &check_candidates[..limit] {
        if is_check_move(gs, m) {
            noisy.push(m);
        }
    }

    noisy
}

// Quiescence search
fn quiescence_search(gs: &mut GameState, mut alpha: i32, mut beta: i32, maximizing: bool, depth: i32) -> i32 {
    let stand_pat = evaluate_position(gs);

    let legal = gs.get_legal_moves_vec();
    if legal.is_empty() {
        if gs.is_in_check(gs.current_turn) {
            return if gs.current_turn == Color::White { -CHECKMATE_SCORE } else { CHECKMATE_SCORE };
        }
        return STALEMATE_SCORE;
    }

    if depth == 0 {
        return stand_pat;
    }

    let delta_margin = PIECE_VALUES[PieceType::Rook.index()];
    if maximizing && stand_pat < alpha.saturating_sub(delta_margin) {
        return alpha;
    }
    if !maximizing && stand_pat > beta.saturating_add(delta_margin) {
        return beta;
    }

    if maximizing {
        if stand_pat >= beta { return beta; }
        alpha = alpha.max(stand_pat);

        let noisy = get_noisy_moves(gs);
        if noisy.is_empty() { return stand_pat; }

        for m in &noisy {
            gs.make_ai_move(*m);
            let score = quiescence_search(gs, alpha, beta, false, depth - 1);
            gs.undo_ai_move();

            if score >= CHECKMATE_SCORE { return CHECKMATE_SCORE; }
            alpha = alpha.max(score);
            if alpha >= beta { break; }
        }
        alpha
    } else {
        if stand_pat <= alpha { return alpha; }
        beta = beta.min(stand_pat);

        let noisy = get_noisy_moves(gs);
        if noisy.is_empty() { return stand_pat; }

        for m in &noisy {
            gs.make_ai_move(*m);
            let score = quiescence_search(gs, alpha, beta, true, depth - 1);
            gs.undo_ai_move();

            if score <= -CHECKMATE_SCORE { return -CHECKMATE_SCORE; }
            beta = beta.min(score);
            if beta <= alpha { break; }
        }
        beta
    }
}

// Minimax with alpha-beta, PVS, LMR, null-move, check extensions, TT
fn minimax_ab(
    gs: &mut GameState,
    mut depth: i32,
    mut alpha: i32,
    mut beta: i32,
    maximizing: bool,
    allow_null: bool,
    ss: &mut SearchState,
) -> (i32, Move) {
    let current_color = if maximizing { Color::White } else { Color::Black };
    let in_check = gs.is_in_check(current_color);
    if in_check && depth > 0 && depth < 3 {
        depth += 1;
    }

    if depth <= 0 || gs.checkmate || gs.stalemate {
        let q = quiescence_search(gs, alpha, beta, maximizing, MAX_QUIESCENCE_DEPTH);
        return (q, Move::NULL);
    }

    let pos_hash = gs.hash;
    let tt_entry = ss.tt.get(&pos_hash).cloned();

    let mut legal_moves = gs.get_legal_moves_vec();
    if legal_moves.is_empty() {
        if gs.is_in_check(gs.current_turn) {
            return (if gs.current_turn == Color::White { -CHECKMATE_SCORE } else { CHECKMATE_SCORE }, Move::NULL);
        }
        return (STALEMATE_SCORE, Move::NULL);
    }

    // TT probe
    if let Some(ref entry) = tt_entry {
        if entry.depth >= depth {
            match entry.flag {
                TTFlag::Exact => return (entry.score, entry.best_move),
                TTFlag::LowerBound => alpha = alpha.max(entry.score),
                TTFlag::UpperBound => beta = beta.min(entry.score),
            }
            if alpha >= beta {
                return (entry.score, entry.best_move);
            }
        }
    }

    // Null-move pruning
    let null_move_r = 2;
    let opponent_color = current_color.opposite();
    let opponent_hand: u8 = gs.hands[opponent_color.index()].iter().sum();
    if allow_null && depth >= null_move_r + 1 && !in_check && opponent_hand == 0 {
        gs.current_turn = gs.current_turn.opposite();
        gs.hash = gs.compute_hash();
        gs.invalidate_cache();
        let (null_score, _) = minimax_ab(gs, depth - 1 - null_move_r, alpha, beta, !maximizing, false, ss);
        gs.current_turn = gs.current_turn.opposite();
        gs.hash = gs.compute_hash();
        gs.invalidate_cache();

        if maximizing && null_score >= beta { return (beta, Move::NULL); }
        if !maximizing && null_score <= alpha { return (alpha, Move::NULL); }
    }

    // Move ordering
    let tt_best = tt_entry.as_ref().map(|e| e.best_move).unwrap_or(Move::NULL);
    let killers = ss.killer_moves.get(&depth).cloned().unwrap_or([Move::NULL; 2]);

    let mut scored: Vec<(Move, i32)> = legal_moves
        .iter()
        .map(|&m| {
            let s = if !tt_best.is_null() && m == tt_best {
                1_000_000
            } else if m == killers[0] || m == killers[1] {
                50_000
            } else {
                mvv_lva_score(gs, m, ss)
            };
            (m, s)
        })
        .collect();
    scored.sort_unstable_by(|a, b| b.1.cmp(&a.1));
    legal_moves = scored.into_iter().map(|(m, _)| m).collect();

    let orig_alpha = alpha;
    let orig_beta = beta;
    let mut best_move = Move::NULL;

    let lmr_full_depth = 4;
    let lmr_reduction_limit = 3;

    if maximizing {
        let mut max_eval = i32::MIN;
        for (i, &m) in legal_moves.iter().enumerate() {
            let noisy = is_noisy_move(gs, m);
            gs.make_ai_move(m);
            let gives_check = gs.is_in_check(gs.current_turn);

            let eval_score;
            if i == 0 {
                let (s, _) = minimax_ab(gs, depth - 1, alpha, beta, false, true, ss);
                eval_score = s;
            } else {
                let reduced = i >= lmr_full_depth && depth >= lmr_reduction_limit && !noisy && !gives_check;
                let (s, _) = if reduced {
                    minimax_ab(gs, depth - 2, alpha, alpha + 1, false, true, ss)
                } else {
                    minimax_ab(gs, depth - 1, alpha, alpha + 1, false, true, ss)
                };
                eval_score = if alpha < s && s < beta {
                    let (re, _) = minimax_ab(gs, depth - 1, alpha, beta, false, true, ss);
                    re
                } else {
                    s
                };
            }

            gs.undo_ai_move();

            if eval_score > max_eval {
                max_eval = eval_score;
                best_move = m;
            }
            alpha = alpha.max(eval_score);
            if alpha >= beta {
                // Update killer moves & history
                let h = ss.history_scores.entry(m.data).or_insert(0);
                *h += depth * depth;
                let killers = ss.killer_moves.entry(depth).or_insert([Move::NULL; 2]);
                if m != killers[0] {
                    killers[1] = killers[0];
                    killers[0] = m;
                }
                break;
            }
        }

        let flag = if max_eval <= orig_alpha {
            TTFlag::UpperBound
        } else if max_eval >= orig_beta {
            TTFlag::LowerBound
        } else {
            TTFlag::Exact
        };
        ss.tt.insert(pos_hash, TTEntry { depth, score: max_eval, flag, best_move });
        (max_eval, best_move)
    } else {
        let mut min_eval = i32::MAX;
        for (i, &m) in legal_moves.iter().enumerate() {
            let noisy = is_noisy_move(gs, m);
            gs.make_ai_move(m);
            let gives_check = gs.is_in_check(gs.current_turn);

            let eval_score;
            if i == 0 {
                let (s, _) = minimax_ab(gs, depth - 1, alpha, beta, true, true, ss);
                eval_score = s;
            } else {
                let reduced = i >= lmr_full_depth && depth >= lmr_reduction_limit && !noisy && !gives_check;
                let (s, _) = if reduced {
                    minimax_ab(gs, depth - 2, beta - 1, beta, true, true, ss)
                } else {
                    minimax_ab(gs, depth - 1, beta - 1, beta, true, true, ss)
                };
                eval_score = if alpha < s && s < beta {
                    let (re, _) = minimax_ab(gs, depth - 1, alpha, beta, true, true, ss);
                    re
                } else {
                    s
                };
            }

            gs.undo_ai_move();

            if eval_score < min_eval {
                min_eval = eval_score;
                best_move = m;
            }
            beta = beta.min(eval_score);
            if beta <= alpha {
                let h = ss.history_scores.entry(m.data).or_insert(0);
                *h += depth * depth;
                let killers = ss.killer_moves.entry(depth).or_insert([Move::NULL; 2]);
                if m != killers[0] {
                    killers[1] = killers[0];
                    killers[0] = m;
                }
                break;
            }
        }

        let flag = if min_eval >= orig_beta {
            TTFlag::LowerBound
        } else if min_eval <= orig_alpha {
            TTFlag::UpperBound
        } else {
            TTFlag::Exact
        };
        ss.tt.insert(pos_hash, TTEntry { depth, score: min_eval, flag, best_move });
        (min_eval, best_move)
    }
}

// Worker function for parallel search
fn search_worker(
    gs: &GameState,
    m: Move,
    depth: i32,
    alpha: i32,
    beta: i32,
    maximizing: bool,
    tt_snapshot: &HashMap<u64, TTEntry>,
) -> (Move, i32, HashMap<u64, TTEntry>) {
    let mut gs_copy = gs.fast_copy();
    let mut ss = SearchState::new();
    ss.tt = tt_snapshot.clone();

    gs_copy.make_ai_move(m);
    let score = minimax_recursive(&mut gs_copy, depth - 1, alpha, beta, !maximizing, true, &mut ss);

    // Collect valuable TT entries
    let min_depth = (depth - 3).max(1);
    let valuable: HashMap<u64, TTEntry> = ss.tt.into_iter()
        .filter(|(_, e)| e.depth >= min_depth && !e.best_move.is_null())
        .collect();

    (m, score, valuable)
}

// Non-tuple-returning recursive version for workers
fn minimax_recursive(
    gs: &mut GameState,
    mut depth: i32,
    mut alpha: i32,
    mut beta: i32,
    maximizing: bool,
    allow_null: bool,
    ss: &mut SearchState,
) -> i32 {
    let current_color = if maximizing { Color::White } else { Color::Black };
    let in_check = gs.is_in_check(current_color);
    if in_check && depth < 3 { depth += 1; }

    if depth <= 0 {
        return quiescence_search(gs, alpha, beta, maximizing, MAX_QUIESCENCE_DEPTH);
    }

    let mut legal_moves = gs.get_legal_moves_vec();
    if legal_moves.is_empty() {
        if gs.is_in_check(gs.current_turn) {
            return if gs.current_turn == Color::White { -CHECKMATE_SCORE } else { CHECKMATE_SCORE };
        }
        return STALEMATE_SCORE;
    }

    let pos_hash = gs.hash;
    let tt_entry = ss.tt.get(&pos_hash).cloned();
    if let Some(ref entry) = tt_entry {
        if entry.depth >= depth {
            match entry.flag {
                TTFlag::Exact => return entry.score,
                TTFlag::LowerBound => alpha = alpha.max(entry.score),
                TTFlag::UpperBound => beta = beta.min(entry.score),
            }
            if alpha >= beta { return entry.score; }
        }
    }

    // Null-move pruning
    let null_r = 2;
    let opp = current_color.opposite();
    let opp_hand: u8 = gs.hands[opp.index()].iter().sum();
    if allow_null && depth >= null_r + 1 && !in_check && opp_hand == 0 {
        gs.current_turn = gs.current_turn.opposite();
        gs.hash = gs.compute_hash();
        gs.invalidate_cache();
        let null_score = minimax_recursive(gs, depth - 1 - null_r, alpha, beta, !maximizing, false, ss);
        gs.current_turn = gs.current_turn.opposite();
        gs.hash = gs.compute_hash();
        gs.invalidate_cache();
        if maximizing && null_score >= beta { return beta; }
        if !maximizing && null_score <= alpha { return alpha; }
    }

    // Move ordering
    let tt_best = tt_entry.as_ref().map(|e| e.best_move).unwrap_or(Move::NULL);
    let mut scored: Vec<(Move, i32)> = legal_moves.iter().map(|&m| {
        let s = if !tt_best.is_null() && m == tt_best { 1_000_000 }
        else { mvv_lva_score(gs, m, ss) };
        (m, s)
    }).collect();
    scored.sort_unstable_by(|a, b| b.1.cmp(&a.1));
    legal_moves = scored.into_iter().map(|(m, _)| m).collect();

    let orig_alpha = alpha;
    let mut best_move = legal_moves[0];
    let lmr_full = 4;
    let lmr_limit = 3;

    if maximizing {
        let mut max_eval = i32::MIN;
        for (i, &m) in legal_moves.iter().enumerate() {
            let noisy = is_noisy_move(gs, m);
            gs.make_ai_move(m);
            let gives_check = gs.is_in_check(gs.current_turn);

            let eval_score = if i == 0 {
                minimax_recursive(gs, depth - 1, alpha, beta, false, true, ss)
            } else {
                let reduced = i >= lmr_full && depth >= lmr_limit && !noisy && !gives_check;
                let s = if reduced {
                    minimax_recursive(gs, depth - 2, alpha, alpha + 1, false, true, ss)
                } else {
                    minimax_recursive(gs, depth - 1, alpha, alpha + 1, false, true, ss)
                };
                if alpha < s && s < beta {
                    minimax_recursive(gs, depth - 1, alpha, beta, false, true, ss)
                } else {
                    s
                }
            };
            gs.undo_ai_move();

            if eval_score >= CHECKMATE_SCORE { return CHECKMATE_SCORE; }
            if eval_score > max_eval { max_eval = eval_score; best_move = m; }
            alpha = alpha.max(eval_score);
            if beta <= alpha { break; }
        }
        let flag = if max_eval <= orig_alpha { TTFlag::UpperBound }
                   else if max_eval >= beta { TTFlag::LowerBound }
                   else { TTFlag::Exact };
        ss.tt.insert(pos_hash, TTEntry { depth, score: max_eval, flag, best_move });
        max_eval
    } else {
        let mut min_eval = i32::MAX;
        for (i, &m) in legal_moves.iter().enumerate() {
            let noisy = is_noisy_move(gs, m);
            gs.make_ai_move(m);
            let gives_check = gs.is_in_check(gs.current_turn);

            let eval_score = if i == 0 {
                minimax_recursive(gs, depth - 1, alpha, beta, true, true, ss)
            } else {
                let reduced = i >= lmr_full && depth >= lmr_limit && !noisy && !gives_check;
                let s = if reduced {
                    minimax_recursive(gs, depth - 2, beta - 1, beta, true, true, ss)
                } else {
                    minimax_recursive(gs, depth - 1, beta - 1, beta, true, true, ss)
                };
                if alpha < s && s < beta {
                    minimax_recursive(gs, depth - 1, alpha, beta, true, true, ss)
                } else {
                    s
                }
            };
            gs.undo_ai_move();

            if eval_score <= -CHECKMATE_SCORE { return -CHECKMATE_SCORE; }
            if eval_score < min_eval { min_eval = eval_score; best_move = m; }
            beta = beta.min(eval_score);
            if beta <= alpha { break; }
        }
        let flag = if min_eval >= beta { TTFlag::LowerBound }
                   else if min_eval <= orig_alpha { TTFlag::UpperBound }
                   else { TTFlag::Exact };
        ss.tt.insert(pos_hash, TTEntry { depth, score: min_eval, flag, best_move });
        min_eval
    }
}

// Parallel minimax at root level
fn minimax_parallel(
    gs: &mut GameState,
    depth: i32,
    ss: &mut SearchState,
) -> (Move, i32, Vec<(Move, i32)>) {
    let legal_moves = gs.get_legal_moves_vec();
    if legal_moves.is_empty() {
        return (Move::NULL, 0, vec![]);
    }

    let maximizing = gs.current_turn == Color::White;

    // TT snapshot for workers (filter by useful depth)
    let min_useful = (depth - 3).max(1);
    let tt_snapshot: HashMap<u64, TTEntry> = ss.tt.iter()
        .filter(|(_, e)| e.depth >= min_useful)
        .map(|(k, v)| (*k, v.clone()))
        .collect();

    // Search first move sequentially for baseline
    let first_move = legal_moves[0];
    let (_, baseline, first_tt) = search_worker(gs, first_move, depth, i32::MIN, i32::MAX, maximizing, &tt_snapshot);
    let asp_window = 150;
    let asp_alpha = baseline - asp_window;
    let asp_beta = baseline + asp_window;

    // Merge first worker's TT
    for (h, e) in &first_tt {
        let existing = ss.tt.get(h);
        if existing.map_or(true, |ex| e.depth > ex.depth) {
            ss.tt.insert(*h, e.clone());
        }
    }

    // Search remaining moves in parallel
    let remaining: Vec<Move> = legal_moves[1..].to_vec();
    let gs_snapshot = gs.fast_copy();
    let tt_snap = tt_snapshot.clone();

    let results: Vec<(Move, i32, HashMap<u64, TTEntry>)> = {
        use rayon::prelude::*;
        remaining.par_iter().map(|&m| {
            search_worker(&gs_snapshot, m, depth, asp_alpha, asp_beta, maximizing, &tt_snap)
        }).collect()
    };

    let mut all_results: Vec<(Move, i32)> = vec![(first_move, baseline)];
    let mut re_search = Vec::new();

    for (m, score, worker_tt) in results {
        // Merge worker TT
        for (h, e) in &worker_tt {
            let existing = ss.tt.get(h);
            if existing.map_or(true, |ex| e.depth > ex.depth) {
                ss.tt.insert(*h, e.clone());
            }
        }

        if score <= asp_alpha || score >= asp_beta {
            re_search.push(m);
        } else {
            all_results.push((m, score));
        }
    }

    // Re-search moves outside aspiration window
    for m in re_search {
        let (_, score, worker_tt) = search_worker(gs, m, depth, i32::MIN, i32::MAX, maximizing, &tt_snapshot);
        for (h, e) in &worker_tt {
            let existing = ss.tt.get(h);
            if existing.map_or(true, |ex| e.depth > ex.depth) {
                ss.tt.insert(*h, e.clone());
            }
        }
        all_results.push((m, score));
    }

    if all_results.is_empty() {
        return (Move::NULL, 0, vec![]);
    }

    // Check for mate
    let mating_score = if maximizing { CHECKMATE_SCORE } else { -CHECKMATE_SCORE };
    for &(m, s) in &all_results {
        if s == mating_score {
            return (m, s, all_results);
        }
    }

    // Find best
    let (best_move, best_score) = if maximizing {
        *all_results.iter().max_by_key(|(_, s)| *s).unwrap()
    } else {
        *all_results.iter().min_by_key(|(_, s)| *s).unwrap()
    };

    (best_move, best_score, all_results)
}

/// Main entry: iterative deepening + cache
pub fn find_best_move(
    gs: &mut GameState,
    depth: i32,
    move_cache: &mut HashMap<(String, i32), String>,
    time_limit: Option<f64>,
) -> (Move, i32) {
    let start = Instant::now();
    let maximizing = gs.current_turn == Color::White;
    let pos_hash_str = gs.hash.to_string();

    // Check cache
    let cache_key = (pos_hash_str.clone(), depth);
    if let Some(cached_repr) = move_cache.get(&cache_key) {
        if let Some(m) = parse_move_repr(cached_repr) {
            let legal = gs.get_legal_moves_vec();
            if legal.contains(&m) {
                eprintln!("[CACHE HIT] depth {} in {:.2}s", depth, start.elapsed().as_secs_f64());
                return (m, 0);
            }
        }
    }

    let legal = gs.get_legal_moves_vec();
    if legal.is_empty() {
        return (Move::NULL, evaluate_position(gs));
    }
    if legal.len() == 1 {
        let m = legal[0];
        move_cache.insert((pos_hash_str.clone(), depth), format_move_repr(m));
        return (m, 0);
    }

    let mut ss = SearchState::new();
    let mut best_move = Move::NULL;
    let mut best_score = 0i32;

    for current_depth in 1..=depth {
        eprintln!("  [ID] depth {}...", current_depth);
        let iter_start = Instant::now();

        if current_depth < PARALLEL_DEPTH_THRESHOLD {
            let (score, m) = minimax_ab(gs, current_depth, i32::MIN + 1, i32::MAX - 1, maximizing, true, &mut ss);
            if !m.is_null() {
                best_move = m;
                best_score = score;
                move_cache.insert((pos_hash_str.clone(), current_depth), format_move_repr(m));
            }
        } else {
            let (m, score, _) = minimax_parallel(gs, current_depth, &mut ss);
            if !m.is_null() {
                best_move = m;
                best_score = score;
                move_cache.insert((pos_hash_str.clone(), current_depth), format_move_repr(m));
            }
        }

        let elapsed = iter_start.elapsed().as_secs_f64();
        eprintln!("  [ID] depth {} done in {:.2}s, score={}", current_depth, elapsed, best_score);

        if best_score.abs() >= CHECKMATE_SCORE * 9 / 10 {
            eprintln!("  Mate found at depth {}", current_depth);
            break;
        }

        if let Some(limit) = time_limit {
            if start.elapsed().as_secs_f64() >= limit {
                eprintln!("  Time limit reached after depth {}", current_depth);
                break;
            }
        }
    }

    // Store best
    if !best_move.is_null() {
        move_cache.insert((pos_hash_str.clone(), depth), format_move_repr(best_move));

        // Persist TT entries to cache
        let mut tt_saved = 0;
        for (h, e) in &ss.tt {
            if e.depth >= 4 && e.flag == TTFlag::Exact && !e.best_move.is_null() {
                let key = (h.to_string(), e.depth);
                if !move_cache.contains_key(&key) {
                    move_cache.insert(key, format_move_repr(e.best_move));
                    tt_saved += 1;
                }
            }
        }
        if tt_saved > 0 {
            eprintln!("  [TT→CACHE] saved {} positions", tt_saved);
        }
    }

    eprintln!("AI done in {:.2}s", start.elapsed().as_secs_f64());
    (best_move, best_score)
}

// Move repr formatting for cache compatibility
pub fn format_move_repr(m: Move) -> String {
    if m.is_null() {
        return "None".to_string();
    }
    if m.is_drop() {
        let to = m.to_sq();
        let r = sq_row(to);
        let f = sq_file(to);
        let color_char = match m.drop_color() {
            Color::White => 'w',
            Color::Black => 'b',
        };
        let pt_char = match m.drop_piece_type() {
            PieceType::Pawn => 'P',
            PieceType::Knight => 'N',
            PieceType::Bishop => 'B',
            PieceType::Rook => 'R',
            PieceType::Queen => 'Q',
            _ => '?',
        };
        format!("('drop', '{}{}'  , ({}, {}))", color_char, pt_char, r, f)
    } else {
        let from = m.from_sq();
        let to = m.to_sq();
        let fr = sq_row(from);
        let ff = sq_file(from);
        let tr = sq_row(to);
        let tf = sq_file(to);
        match m.promotion() {
            Some(pt) => {
                let pc = match pt {
                    PieceType::Rook => if fr > tr { "R" } else { "r" },
                    PieceType::Knight => if fr > tr { "N" } else { "n" },
                    PieceType::Bishop => if fr > tr { "B" } else { "b" },
                    _ => "?",
                };
                format!("(({}, {}), ({}, {}), '{}')", fr, ff, tr, tf, pc)
            }
            None => format!("(({}, {}), ({}, {}), None)", fr, ff, tr, tf),
        }
    }
}

pub fn parse_move_repr(s: &str) -> Option<Move> {
    // Parse Python repr format: ((<r1>, <f1>), (<r2>, <f2>), None/'R'/etc) or ('drop', '<code>', (<r>, <f>))
    let s = s.trim();
    if s.starts_with("('drop'") {
        // Drop format: ('drop', 'wN', (3, 3))
        let parts: Vec<&str> = s.split('\'').collect();
        if parts.len() >= 4 {
            let code = parts[3];
            if code.len() >= 2 {
                let color = match code.chars().next()? {
                    'w' => Color::White,
                    'b' => Color::Black,
                    _ => return None,
                };
                let pt = match code.chars().nth(1)? {
                    'P' => PieceType::Pawn,
                    'N' => PieceType::Knight,
                    'B' => PieceType::Bishop,
                    'R' => PieceType::Rook,
                    'Q' => PieceType::Queen,
                    _ => return None,
                };
                // Parse (r, f) from the end
                let nums: Vec<usize> = s.chars()
                    .filter(|c| c.is_ascii_digit())
                    .map(|c| c.to_digit(10).unwrap() as usize)
                    .collect();
                if nums.len() >= 2 {
                    let r = nums[nums.len() - 2];
                    let f = nums[nums.len() - 1];
                    if r < BOARD_SIZE && f < BOARD_SIZE {
                        return Some(Move::new_drop(sq(r, f), pt, color));
                    }
                }
            }
        }
        None
    } else {
        // Normal: ((r1, f1), (r2, f2), None/'R')
        let nums: Vec<usize> = s.chars()
            .filter(|c| c.is_ascii_digit())
            .map(|c| c.to_digit(10).unwrap() as usize)
            .collect();
        if nums.len() >= 4 {
            let from = sq(nums[0], nums[1]);
            let to = sq(nums[2], nums[3]);
            // Check for promotion
            let promo = if s.contains("'R'") { Some(PieceType::Rook) }
                else if s.contains("'r'") { Some(PieceType::Rook) }
                else if s.contains("'N'") { Some(PieceType::Knight) }
                else if s.contains("'n'") { Some(PieceType::Knight) }
                else if s.contains("'B'") { Some(PieceType::Bishop) }
                else if s.contains("'b'") { Some(PieceType::Bishop) }
                else { None };
            Some(Move::new_normal(from, to, promo))
        } else {
            None
        }
    }
}
