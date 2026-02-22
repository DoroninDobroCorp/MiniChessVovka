use crate::types::*;
use crate::gamestate::GameState;

// Constants matching Python ai.py
const CENTER_SQUARES: [usize; 4] = [
    2 * BOARD_SIZE + 2, // (2,2)
    2 * BOARD_SIZE + 3, // (2,3)
    3 * BOARD_SIZE + 2, // (3,2)
    3 * BOARD_SIZE + 3, // (3,3)
];
const CENTER_BONUS: i32 = 15;
const KING_SAFETY_BONUS: i32 = 8;
const MOBILITY_BONUS: i32 = 3;
const PAWN_STRUCTURE_BONUS: i32 = 5;
const ATTACK_KING_ZONE_BONUS: i32 = 20;
const DROP_THREAT_BONUS: i32 = 25;
const OPEN_FILE_ROOK_BONUS: i32 = 30;
const SEMI_OPEN_FILE_ROOK_BONUS: i32 = 15;
const PAWN_SHIELD_BONUS: i32 = 40;
const EXPOSED_KING_PENALTY: i32 = 80;
const BISHOP_PAIR_BONUS: i32 = 50;
const BLOCKED_PAWN_PENALTY: i32 = 25;
const DROP_PAWN_PROMO_BONUS: i32 = 250;

pub const CHECKMATE_SCORE: i32 = 1_000_000;
pub const STALEMATE_SCORE: i32 = 0;

fn is_center(s: usize) -> bool {
    CENTER_SQUARES.contains(&s)
}

pub fn evaluate_position(gs: &GameState) -> i32 {
    if gs.checkmate {
        return if gs.current_turn == Color::White {
            -CHECKMATE_SCORE
        } else {
            CHECKMATE_SCORE
        };
    }
    if gs.stalemate {
        let (mut wm, mut bm) = (0i32, 0i32);
        for s in 0..NUM_SQUARES {
            let p = gs.board[s];
            if p.is_empty() { continue; }
            let val = PIECE_VALUES[p.piece_type().unwrap().index()];
            match p.color().unwrap() {
                Color::White => wm += val,
                Color::Black => bm += val,
            }
        }
        for pt in 0..5 {
            wm += HAND_PIECE_VALUES[pt] * gs.hands[0][pt] as i32;
            bm += HAND_PIECE_VALUES[pt] * gs.hands[1][pt] as i32;
        }
        let diff = wm - bm;
        if gs.current_turn == Color::White && diff > 100 { return -10000; }
        if gs.current_turn == Color::Black && diff < -100 { return 10000; }
        return 0;
    }

    let mut score: i32 = 0;
    let wk_sq = gs.king_pos[0];
    let bk_sq = gs.king_pos[1];
    let (wk_r, wk_c) = (sq_row(wk_sq) as i32, sq_file(wk_sq) as i32);
    let (bk_r, bk_c) = (sq_row(bk_sq) as i32, sq_file(bk_sq) as i32);
    let mut total_material: i32 = 0;

    let mut white_pawns: Vec<(usize, usize)> = Vec::new();
    let mut black_pawns: Vec<(usize, usize)> = Vec::new();

    // 1. Material + center + king safety proximity
    for s in 0..NUM_SQUARES {
        let piece = gs.board[s];
        if piece.is_empty() { continue; }
        let pt = piece.piece_type().unwrap();
        let val = PIECE_VALUES[pt.index()];
        total_material += val;
        let r = sq_row(s) as i32;
        let c = sq_file(s) as i32;

        match piece.color().unwrap() {
            Color::White => {
                score += val;
                if is_center(s) { score += CENTER_BONUS; }
                if pt == PieceType::Pawn { white_pawns.push((r as usize, c as usize)); }
                if pt != PieceType::King {
                    let dist = (r - wk_r).abs().max((c - wk_c).abs());
                    if dist <= 2 { score += KING_SAFETY_BONUS; }
                }
            }
            Color::Black => {
                score -= val;
                if is_center(s) { score -= CENTER_BONUS; }
                if pt == PieceType::Pawn { black_pawns.push((r as usize, c as usize)); }
                if pt != PieceType::King {
                    let dist = (r - bk_r).abs().max((c - bk_c).abs());
                    if dist <= 2 { score -= KING_SAFETY_BONUS; }
                }
            }
        }
    }

    // Hand material
    let wh_total: u8 = gs.hands[0].iter().sum();
    let bh_total: u8 = gs.hands[1].iter().sum();
    for pt in 0..5 {
        score += HAND_PIECE_VALUES[pt] * gs.hands[0][pt] as i32;
        total_material += PIECE_VALUES[pt] * gs.hands[0][pt] as i32;
        score -= HAND_PIECE_VALUES[pt] * gs.hands[1][pt] as i32;
        total_material += PIECE_VALUES[pt] * gs.hands[1][pt] as i32;
    }
    score += wh_total as i32 * DROP_THREAT_BONUS;
    score -= bh_total as i32 * DROP_THREAT_BONUS;

    // Phase detection
    let endgame = total_material < 2 * PIECE_VALUES[PieceType::Rook.index()] + 2 * PIECE_VALUES[PieceType::King.index()];

    // 2. Mobility proxy
    let (mut wm, mut bmo) = (0i32, 0i32);
    for s in 0..NUM_SQUARES {
        let piece = gs.board[s];
        if piece.is_empty() || piece.piece_type() == Some(PieceType::King) { continue; }
        let r = sq_row(s) as i32;
        let c = sq_file(s) as i32;
        let mut has_adj = false;
        for &(dr, dc) in &KING_OFFSETS {
            let nr = r + dr;
            let nc = c + dc;
            if nr >= 0 && nr < BOARD_SIZE as i32 && nc >= 0 && nc < BOARD_SIZE as i32 {
                if gs.board[sq(nr as usize, nc as usize)].is_empty() {
                    has_adj = true;
                    break;
                }
            }
        }
        if has_adj {
            match piece.color().unwrap() {
                Color::White => wm += 1,
                Color::Black => bmo += 1,
            }
        }
    }
    score += (wm - bmo) * MOBILITY_BONUS;

    // 3. Pawn structure
    for &(r, c) in &white_pawns {
        if c > 0 && gs.board[sq(r, c - 1)] == Piece::WhitePawn { score += PAWN_STRUCTURE_BONUS; }
        if c < BOARD_SIZE - 1 && gs.board[sq(r, c + 1)] == Piece::WhitePawn { score += PAWN_STRUCTURE_BONUS; }
        if r > 0 && gs.board[sq(r - 1, c)] != Piece::Empty { score -= BLOCKED_PAWN_PENALTY; }
        // Passed pawn
        let mut is_passed = true;
        let mut path_clear = true;
        for scan_r in (0..r).rev() {
            if gs.board[sq(scan_r, c)] == Piece::BlackPawn { is_passed = false; break; }
            if c > 0 && gs.board[sq(scan_r, c - 1)] == Piece::BlackPawn { is_passed = false; break; }
            if c < BOARD_SIZE - 1 && gs.board[sq(scan_r, c + 1)] == Piece::BlackPawn { is_passed = false; break; }
            if gs.board[sq(scan_r, c)] != Piece::Empty { path_clear = false; }
        }
        if is_passed {
            let steps = r; // steps to row 0
            let bonus = match steps { 1 => 500, 2 => 200, 3 => 80, 4 => 30, _ => 15 };
            score += bonus;
            if path_clear {
                let ub = match steps { 1 => 300, 2 => 120, 3 => 40, _ => 0 };
                score += ub;
            }
        }
    }

    for &(r, c) in &black_pawns {
        if c > 0 && gs.board[sq(r, c - 1)] == Piece::BlackPawn { score -= PAWN_STRUCTURE_BONUS; }
        if c < BOARD_SIZE - 1 && gs.board[sq(r, c + 1)] == Piece::BlackPawn { score -= PAWN_STRUCTURE_BONUS; }
        if r < BOARD_SIZE - 1 && gs.board[sq(r + 1, c)] != Piece::Empty { score += BLOCKED_PAWN_PENALTY; }
        let mut is_passed = true;
        let mut path_clear = true;
        for scan_r in (r + 1)..BOARD_SIZE {
            if gs.board[sq(scan_r, c)] == Piece::WhitePawn { is_passed = false; break; }
            if c > 0 && gs.board[sq(scan_r, c - 1)] == Piece::WhitePawn { is_passed = false; break; }
            if c < BOARD_SIZE - 1 && gs.board[sq(scan_r, c + 1)] == Piece::WhitePawn { is_passed = false; break; }
            if gs.board[sq(scan_r, c)] != Piece::Empty { path_clear = false; }
        }
        if is_passed {
            let steps = BOARD_SIZE - 1 - r;
            let bonus = match steps { 1 => 500, 2 => 200, 3 => 80, 4 => 30, _ => 15 };
            score -= bonus;
            if path_clear {
                let ub = match steps { 1 => 300, 2 => 120, 3 => 40, _ => 0 };
                score -= ub;
            }
        }
    }

    // 4. King safety — pawn shield
    {
        let mut w_shield = 0i32;
        for dc in -1..=1i32 {
            let sc = wk_c + dc;
            let sr = wk_r - 1;
            if sr >= 0 && sr < BOARD_SIZE as i32 && sc >= 0 && sc < BOARD_SIZE as i32 {
                if gs.board[sq(sr as usize, sc as usize)] == Piece::WhitePawn {
                    w_shield += 1;
                }
            }
        }
        score += w_shield * PAWN_SHIELD_BONUS;
        if w_shield == 0 && bh_total > 0 {
            score -= EXPOSED_KING_PENALTY * (bh_total as i32).min(3);
        }
        if !endgame && is_center(gs.king_pos[0]) { score -= 30; }

        let mut b_shield = 0i32;
        for dc in -1..=1i32 {
            let sc = bk_c + dc;
            let sr = bk_r + 1;
            if sr >= 0 && sr < BOARD_SIZE as i32 && sc >= 0 && sc < BOARD_SIZE as i32 {
                if gs.board[sq(sr as usize, sc as usize)] == Piece::BlackPawn {
                    b_shield += 1;
                }
            }
        }
        score -= b_shield * PAWN_SHIELD_BONUS;
        if b_shield == 0 && wh_total > 0 {
            score += EXPOSED_KING_PENALTY * (wh_total as i32).min(3);
        }
        if !endgame && is_center(gs.king_pos[1]) { score += 30; }
    }

    // Endgame king activity
    if endgame {
        if is_center(gs.king_pos[0]) { score += 15; }
        if is_center(gs.king_pos[1]) { score -= 15; }
    }

    // 5. Development (opening)
    if !endgame {
        let mut w_undev = 0i32;
        for c in 0..BOARD_SIZE {
            let p = gs.board[sq(5, c)];
            if p == Piece::WhiteKnight || p == Piece::WhiteBishop || p == Piece::WhiteRook {
                w_undev += 1;
            }
        }
        score -= w_undev * 15;

        let mut b_undev = 0i32;
        for c in 0..BOARD_SIZE {
            let p = gs.board[sq(0, c)];
            if p == Piece::BlackKnight || p == Piece::BlackBishop || p == Piece::BlackRook {
                b_undev += 1;
            }
        }
        score += b_undev * 15;
    }

    // 6. King attack zone
    {
        let mut w_atk = 0.0f32;
        let mut b_atk = 0.0f32;
        for s in 0..NUM_SQUARES {
            let piece = gs.board[s];
            if piece.is_empty() { continue; }
            let pt = piece.piece_type().unwrap();
            if pt == PieceType::King { continue; }
            let r = sq_row(s) as i32;
            let c = sq_file(s) as i32;
            match piece.color().unwrap() {
                Color::White => {
                    let dist = (r - bk_r).abs().max((c - bk_c).abs());
                    if pt == PieceType::Knight {
                        let offset = (bk_r - r, bk_c - c);
                        if KNIGHT_OFFSETS.contains(&offset) {
                            w_atk += 2.0;
                        } else if dist <= 2 {
                            w_atk += 0.5;
                        }
                    } else if dist <= 2 {
                        w_atk += 1.0;
                    } else if dist <= 3 && matches!(pt, PieceType::Rook | PieceType::Queen | PieceType::Bishop) {
                        w_atk += 0.3;
                    }
                }
                Color::Black => {
                    let dist = (r - wk_r).abs().max((c - wk_c).abs());
                    if pt == PieceType::Knight {
                        let offset = (wk_r - r, wk_c - c);
                        if KNIGHT_OFFSETS.contains(&offset) {
                            b_atk += 2.0;
                        } else if dist <= 2 {
                            b_atk += 0.5;
                        }
                    } else if dist <= 2 {
                        b_atk += 1.0;
                    } else if dist <= 3 && matches!(pt, PieceType::Rook | PieceType::Queen | PieceType::Bishop) {
                        b_atk += 0.3;
                    }
                }
            }
        }
        score += (w_atk * ATTACK_KING_ZONE_BONUS as f32) as i32;
        score -= (b_atk * ATTACK_KING_ZONE_BONUS as f32) as i32;
    }

    // 7. Tempo
    score += if gs.current_turn == Color::White { 10 } else { -10 };

    // 8. Drop pawn near promotion
    if gs.hands[0][PieceType::Pawn.index()] > 0 {
        let mut spots = 0;
        for c in 0..BOARD_SIZE {
            if gs.board[sq(1, c)].is_empty() { spots += 1; }
        }
        if spots > 0 { score += DROP_PAWN_PROMO_BONUS + (spots - 1) * 50; }
    }
    if gs.hands[1][PieceType::Pawn.index()] > 0 {
        let mut spots = 0;
        for c in 0..BOARD_SIZE {
            if gs.board[sq(BOARD_SIZE - 2, c)].is_empty() { spots += 1; }
        }
        if spots > 0 { score -= DROP_PAWN_PROMO_BONUS + (spots - 1) * 50; }
    }

    // 9. Rook on open/semi-open file
    for s in 0..NUM_SQUARES {
        let piece = gs.board[s];
        if piece.is_empty() { continue; }
        let pt = piece.piece_type().unwrap();
        if pt != PieceType::Rook { continue; }
        let c = sq_file(s);
        let color = piece.color().unwrap();
        let (fp, ep) = match color {
            Color::White => (Piece::WhitePawn, Piece::BlackPawn),
            Color::Black => (Piece::BlackPawn, Piece::WhitePawn),
        };
        let mut has_friendly = false;
        let mut has_enemy = false;
        for scan_r in 0..BOARD_SIZE {
            let sp = gs.board[sq(scan_r, c)];
            if sp == fp { has_friendly = true; }
            if sp == ep { has_enemy = true; }
        }
        let bonus = if !has_friendly && !has_enemy {
            OPEN_FILE_ROOK_BONUS
        } else if !has_friendly {
            SEMI_OPEN_FILE_ROOK_BONUS
        } else {
            0
        };
        match color {
            Color::White => score += bonus,
            Color::Black => score -= bonus,
        }
    }

    // 10. Bishop pair
    let mut wb = 0;
    let mut bb = 0;
    for s in 0..NUM_SQUARES {
        match gs.board[s] {
            Piece::WhiteBishop => wb += 1,
            Piece::BlackBishop => bb += 1,
            _ => {}
        }
    }
    if wb >= 2 { score += BISHOP_PAIR_BONUS; }
    if bb >= 2 { score -= BISHOP_PAIR_BONUS; }
    if wb as u8 + gs.hands[0][PieceType::Bishop.index()] >= 2 { score += BISHOP_PAIR_BONUS / 2; }
    if bb as u8 + gs.hands[1][PieceType::Bishop.index()] >= 2 { score -= BISHOP_PAIR_BONUS / 2; }

    score
}
