use crate::types::*;
use crate::zobrist;

/// Undo information for fast make/undo during search
#[derive(Clone)]
pub struct UndoInfo {
    pub mov: Move,
    pub captured: Piece,
    pub prev_king_pos: Option<usize>,
    pub prev_checkmate: bool,
    pub prev_stalemate: bool,
    pub prev_last_move: Move,
    pub was_promoted: bool,       // captured piece was promoted (reverts to pawn)
    pub moved_promoted: bool,     // moved piece was a promoted piece
    pub new_promotion: bool,      // this move is a new promotion
    pub prev_hash: u64,
}

#[derive(Clone)]
pub struct GameState {
    pub board: [Piece; NUM_SQUARES],
    pub current_turn: Color,
    pub hands: [[u8; 5]; 2], // [color_index][piece_type_index] = count
    pub king_pos: [usize; 2], // [color_index] = square
    pub checkmate: bool,
    pub stalemate: bool,
    pub last_move: Move,
    pub game_over_message: String,
    pub promoted_pieces: u64, // bitset: bit i = square i has a promoted piece
    pub hash: u64,

    // UI-related fields (not used in search, but needed for Python compat)
    pub needs_promotion_choice: bool,
    pub promotion_square: Option<usize>,

    // Search stack
    pub ai_history: Vec<UndoInfo>,

    // Cached legal moves
    legal_moves_cache: Option<Vec<Move>>,
}

impl GameState {
    pub fn new() -> Self {
        GameState {
            board: [Piece::Empty; NUM_SQUARES],
            current_turn: Color::White,
            hands: [[0u8; 5]; 2],
            king_pos: [0; 2],
            checkmate: false,
            stalemate: false,
            last_move: Move::NULL,
            game_over_message: String::new(),
            promoted_pieces: 0,
            hash: 0,
            needs_promotion_choice: false,
            promotion_square: None,
            ai_history: Vec::with_capacity(128),
            legal_moves_cache: None,
        }
    }

    pub fn setup_initial_board(&mut self) {
        // Row 0: ['.', '.', 'b', 'n', 'r', 'k']
        // Row 1: ['.', '.', '.', '.', '.', 'p']
        // Row 2-3: empty
        // Row 4: ['P', '.', '.', '.', '.', '.']
        // Row 5: ['K', 'R', 'N', 'B', '.', '.']
        self.board = [Piece::Empty; NUM_SQUARES];
        self.board[sq(0, 2)] = Piece::BlackBishop;
        self.board[sq(0, 3)] = Piece::BlackKnight;
        self.board[sq(0, 4)] = Piece::BlackRook;
        self.board[sq(0, 5)] = Piece::BlackKing;
        self.board[sq(1, 5)] = Piece::BlackPawn;
        self.board[sq(4, 0)] = Piece::WhitePawn;
        self.board[sq(5, 0)] = Piece::WhiteKing;
        self.board[sq(5, 1)] = Piece::WhiteRook;
        self.board[sq(5, 2)] = Piece::WhiteKnight;
        self.board[sq(5, 3)] = Piece::WhiteBishop;

        self.king_pos = [sq(5, 0), sq(0, 5)]; // [White, Black]
        self.current_turn = Color::White;
        self.hands = [[0; 5]; 2];
        self.checkmate = false;
        self.stalemate = false;
        self.last_move = Move::NULL;
        self.game_over_message.clear();
        self.promoted_pieces = 0;
        self.needs_promotion_choice = false;
        self.promotion_square = None;
        self.ai_history.clear();
        self.legal_moves_cache = None;
        self.hash = self.compute_hash();
    }

    pub fn compute_hash(&self) -> u64 {
        zobrist::get_position_hash(&self.board, self.current_turn, &self.hands, self.promoted_pieces)
    }

    #[inline]
    pub fn hand_count(&self, color: Color, pt: PieceType) -> u8 {
        self.hands[color.index()][pt.index()]
    }

    #[inline]
    pub fn hand_total(&self, color: Color) -> u8 {
        self.hands[color.index()].iter().sum()
    }

    pub fn invalidate_cache(&mut self) {
        self.legal_moves_cache = None;
    }

    // ============================================================
    // Move generation
    // ============================================================

    fn gen_pawn_moves(&self, r: usize, f: usize, color: Color, moves: &mut Vec<Move>) {
        let s = sq(r, f);
        let dir: i32 = if color == Color::White { -1 } else { 1 };
        let promo_rank = if color == Color::White { 0 } else { BOARD_SIZE - 1 };

        // Forward
        let nr = r as i32 + dir;
        let nf = f as i32;
        if is_on_board(nr, nf) {
            let to = sq(nr as usize, nf as usize);
            if self.board[to].is_empty() {
                if nr as usize == promo_rank {
                    for &pp in &PROMOTION_PIECES {
                        moves.push(Move::new_normal(s, to, Some(pp)));
                    }
                } else {
                    moves.push(Move::new_normal(s, to, None));
                }
            }
        }

        // Captures
        for df in [-1i32, 1] {
            let nr = r as i32 + dir;
            let nf = f as i32 + df;
            if is_on_board(nr, nf) {
                let to = sq(nr as usize, nf as usize);
                let target = self.board[to];
                if !target.is_empty() && target.color() != Some(color) {
                    if nr as usize == promo_rank {
                        for &pp in &PROMOTION_PIECES {
                            moves.push(Move::new_normal(s, to, Some(pp)));
                        }
                    } else {
                        moves.push(Move::new_normal(s, to, None));
                    }
                }
            }
        }
    }

    fn gen_knight_moves(&self, r: usize, f: usize, color: Color, moves: &mut Vec<Move>) {
        let s = sq(r, f);
        for &(dr, df) in &KNIGHT_OFFSETS {
            let nr = r as i32 + dr;
            let nf = f as i32 + df;
            if is_on_board(nr, nf) {
                let to = sq(nr as usize, nf as usize);
                let target = self.board[to];
                if target.is_empty() || target.color() != Some(color) {
                    moves.push(Move::new_normal(s, to, None));
                }
            }
        }
    }

    fn gen_sliding_moves(
        &self,
        r: usize,
        f: usize,
        color: Color,
        dirs: &[(i32, i32)],
        moves: &mut Vec<Move>,
    ) {
        let s = sq(r, f);
        for &(dr, df) in dirs {
            let mut nr = r as i32 + dr;
            let mut nf = f as i32 + df;
            while is_on_board(nr, nf) {
                let to = sq(nr as usize, nf as usize);
                let target = self.board[to];
                if target.is_empty() {
                    moves.push(Move::new_normal(s, to, None));
                } else if target.color() != Some(color) {
                    moves.push(Move::new_normal(s, to, None));
                    break;
                } else {
                    break;
                }
                nr += dr;
                nf += df;
            }
        }
    }

    fn gen_king_moves(&self, r: usize, f: usize, color: Color, moves: &mut Vec<Move>) {
        let s = sq(r, f);
        for &(dr, df) in &KING_OFFSETS {
            let nr = r as i32 + dr;
            let nf = f as i32 + df;
            if is_on_board(nr, nf) {
                let to = sq(nr as usize, nf as usize);
                let target = self.board[to];
                if target.is_empty() || target.color() != Some(color) {
                    moves.push(Move::new_normal(s, to, None));
                }
            }
        }
    }

    fn gen_drop_moves(&self, color: Color, moves: &mut Vec<Move>) {
        let ci = color.index();
        let promo_rank = if color == Color::White { 0 } else { BOARD_SIZE - 1 };

        for (pti, &count) in self.hands[ci].iter().enumerate() {
            if count == 0 {
                continue;
            }
            let pt = match pti {
                0 => PieceType::Pawn,
                1 => PieceType::Knight,
                2 => PieceType::Bishop,
                3 => PieceType::Rook,
                4 => PieceType::Queen,
                _ => continue,
            };
            let is_pawn = pt == PieceType::Pawn;
            for r in 0..BOARD_SIZE {
                if is_pawn && r == promo_rank {
                    continue;
                }
                for f in 0..BOARD_SIZE {
                    if self.board[sq(r, f)].is_empty() {
                        moves.push(Move::new_drop(sq(r, f), pt, color));
                    }
                }
            }
        }
    }

    pub fn generate_pseudo_legal_moves(&self, color: Color) -> Vec<Move> {
        let mut moves = Vec::with_capacity(128);

        for r in 0..BOARD_SIZE {
            for f in 0..BOARD_SIZE {
                let piece = self.board[sq(r, f)];
                if piece.is_empty() || piece.color() != Some(color) {
                    continue;
                }
                match piece.piece_type().unwrap() {
                    PieceType::Pawn => self.gen_pawn_moves(r, f, color, &mut moves),
                    PieceType::Knight => self.gen_knight_moves(r, f, color, &mut moves),
                    PieceType::Bishop => self.gen_sliding_moves(r, f, color, &DIAGONAL_OFFSETS, &mut moves),
                    PieceType::Rook => self.gen_sliding_moves(r, f, color, &STRAIGHT_OFFSETS, &mut moves),
                    PieceType::Queen => {
                        self.gen_sliding_moves(r, f, color, &DIAGONAL_OFFSETS, &mut moves);
                        self.gen_sliding_moves(r, f, color, &STRAIGHT_OFFSETS, &mut moves);
                    }
                    PieceType::King => self.gen_king_moves(r, f, color, &mut moves),
                }
            }
        }

        self.gen_drop_moves(color, &mut moves);
        moves
    }

    pub fn get_all_legal_moves(&mut self) -> &[Move] {
        if self.legal_moves_cache.is_some() {
            return self.legal_moves_cache.as_ref().unwrap();
        }
        if self.needs_promotion_choice {
            self.legal_moves_cache = Some(Vec::new());
            return self.legal_moves_cache.as_ref().unwrap();
        }

        let color = self.current_turn;
        let pseudo = self.generate_pseudo_legal_moves(color);
        let mut legal = Vec::with_capacity(pseudo.len());

        for m in pseudo {
            self.make_ai_move(m);
            let in_check = self.is_in_check(color);
            self.undo_ai_move();
            if !in_check {
                legal.push(m);
            }
        }

        self.legal_moves_cache = Some(legal);
        self.legal_moves_cache.as_ref().unwrap()
    }

    /// Non-caching version that returns owned Vec (for use in search where we need ownership)
    pub fn get_legal_moves_vec(&mut self) -> Vec<Move> {
        if let Some(ref cache) = self.legal_moves_cache {
            return cache.clone();
        }
        if self.needs_promotion_choice {
            return Vec::new();
        }

        let color = self.current_turn;
        let pseudo = self.generate_pseudo_legal_moves(color);
        let mut legal = Vec::with_capacity(pseudo.len());

        for m in pseudo {
            self.make_ai_move(m);
            let in_check = self.is_in_check(color);
            self.undo_ai_move();
            if !in_check {
                legal.push(m);
            }
        }

        self.legal_moves_cache = Some(legal.clone());
        legal
    }

    // ============================================================
    // Attack detection
    // ============================================================

    pub fn is_square_attacked(&self, target_sq: usize, attacker_color: Color) -> bool {
        let r = sq_row(target_sq) as i32;
        let f = sq_file(target_sq) as i32;

        // Pawn attacks
        let pawn_piece = Piece::from_color_type(attacker_color, PieceType::Pawn);
        let pawn_dir: i32 = if attacker_color == Color::White { -1 } else { 1 };
        for df in [-1i32, 1] {
            let pr = r - pawn_dir;
            let pf = f + df;
            if is_on_board(pr, pf) && self.board[sq(pr as usize, pf as usize)] == pawn_piece {
                return true;
            }
        }

        // Knight attacks
        let knight_piece = Piece::from_color_type(attacker_color, PieceType::Knight);
        for &(dr, df) in &KNIGHT_OFFSETS {
            let nr = r + dr;
            let nf = f + df;
            if is_on_board(nr, nf) && self.board[sq(nr as usize, nf as usize)] == knight_piece {
                return true;
            }
        }

        // Sliding attacks (Bishop/Queen on diagonals, Rook/Queen on straights)
        let bishop = Piece::from_color_type(attacker_color, PieceType::Bishop);
        let queen = Piece::from_color_type(attacker_color, PieceType::Queen);
        for &(dr, df) in &DIAGONAL_OFFSETS {
            let mut cr = r + dr;
            let mut cf = f + df;
            while is_on_board(cr, cf) {
                let p = self.board[sq(cr as usize, cf as usize)];
                if p != Piece::Empty {
                    if p == bishop || p == queen {
                        return true;
                    }
                    break;
                }
                cr += dr;
                cf += df;
            }
        }

        let rook = Piece::from_color_type(attacker_color, PieceType::Rook);
        for &(dr, df) in &STRAIGHT_OFFSETS {
            let mut cr = r + dr;
            let mut cf = f + df;
            while is_on_board(cr, cf) {
                let p = self.board[sq(cr as usize, cf as usize)];
                if p != Piece::Empty {
                    if p == rook || p == queen {
                        return true;
                    }
                    break;
                }
                cr += dr;
                cf += df;
            }
        }

        // King attacks
        let king_piece = Piece::from_color_type(attacker_color, PieceType::King);
        for &(dr, df) in &KING_OFFSETS {
            let kr = r + dr;
            let kf = f + df;
            if is_on_board(kr, kf) && self.board[sq(kr as usize, kf as usize)] == king_piece {
                return true;
            }
        }

        false
    }

    pub fn is_in_check(&self, color: Color) -> bool {
        let king_sq = self.king_pos[color.index()];
        self.is_square_attacked(king_sq, color.opposite())
    }

    pub fn check_game_over(&mut self) -> bool {
        if self.needs_promotion_choice {
            return false;
        }
        let legal = self.get_legal_moves_vec();
        if legal.is_empty() {
            if self.is_in_check(self.current_turn) {
                self.checkmate = true;
                let winner = if self.current_turn == Color::White { "Black" } else { "White" };
                self.game_over_message = format!("Checkmate! {} wins.", winner);
            } else {
                self.stalemate = true;
                self.game_over_message = "Stalemate! Draw.".to_string();
            }
            return true;
        }
        self.checkmate = false;
        self.stalemate = false;
        self.game_over_message.clear();
        false
    }

    // ============================================================
    // AI-optimized make/undo
    // ============================================================

    pub fn make_ai_move(&mut self, m: Move) {
        let prev_hash = self.hash;
        let mut undo = UndoInfo {
            mov: m,
            captured: Piece::Empty,
            prev_king_pos: None,
            prev_checkmate: self.checkmate,
            prev_stalemate: self.stalemate,
            prev_last_move: self.last_move,
            was_promoted: false,
            moved_promoted: false,
            new_promotion: false,
            prev_hash: prev_hash,
        };

        if m.is_drop() {
            let to = m.to_sq();
            let pt = m.drop_piece_type();
            let color = m.drop_color();
            let piece = Piece::from_color_type(color, pt);

            self.board[to] = piece;
            self.hands[color.index()][pt.index()] -= 1;
            self.last_move = m;
            self.current_turn = self.current_turn.opposite();
        } else {
            let from = m.from_sq();
            let to = m.to_sq();
            let piece = self.board[from];
            let target = self.board[to];
            let color = piece.color().unwrap();

            // Handle capture
            if target != Piece::Empty {
                undo.captured = target;
                let mut captured_type = target.piece_type().unwrap();
                // Crazyhouse: promoted piece reverts to pawn
                if self.promoted_pieces & (1u64 << to) != 0 {
                    captured_type = PieceType::Pawn;
                    self.promoted_pieces &= !(1u64 << to);
                    undo.was_promoted = true;
                }
                self.hands[color.index()][captured_type.index()] += 1;
            }

            // Track promoted piece movement
            if self.promoted_pieces & (1u64 << from) != 0 {
                self.promoted_pieces &= !(1u64 << from);
                self.promoted_pieces |= 1u64 << to;
                undo.moved_promoted = true;
            }

            // Update board
            self.board[from] = Piece::Empty;
            if let Some(promo_pt) = m.promotion() {
                self.board[to] = Piece::from_color_type(color, promo_pt);
                self.promoted_pieces |= 1u64 << to;
                undo.new_promotion = true;
            } else {
                self.board[to] = piece;
            }

            // Update king position
            if piece.piece_type() == Some(PieceType::King) {
                undo.prev_king_pos = Some(self.king_pos[color.index()]);
                self.king_pos[color.index()] = to;
            }

            self.last_move = m;
            self.current_turn = self.current_turn.opposite();
        }

        self.ai_history.push(undo);
        self.legal_moves_cache = None;
        self.hash = self.compute_hash();
    }

    pub fn undo_ai_move(&mut self) {
        let undo = match self.ai_history.pop() {
            Some(u) => u,
            None => return,
        };
        let m = undo.mov;

        self.current_turn = self.current_turn.opposite();

        if m.is_drop() {
            let to = m.to_sq();
            let pt = m.drop_piece_type();
            let color = m.drop_color();
            self.board[to] = Piece::Empty;
            self.hands[color.index()][pt.index()] += 1;
        } else {
            let from = m.from_sq();
            let to = m.to_sq();
            let moved_piece = self.board[to];
            let color = moved_piece.color().unwrap();

            // Undo new promotion tracking
            if undo.new_promotion {
                self.promoted_pieces &= !(1u64 << to);
            }

            // Undo promoted piece movement
            if undo.moved_promoted {
                self.promoted_pieces &= !(1u64 << to);
                self.promoted_pieces |= 1u64 << from;
            }

            // If was promotion, revert to pawn
            let original_piece = if m.promotion().is_some() {
                Piece::from_color_type(color, PieceType::Pawn)
            } else {
                moved_piece
            };

            self.board[from] = original_piece;

            // Restore captured piece
            if undo.captured != Piece::Empty {
                self.board[to] = undo.captured;
                if undo.was_promoted {
                    self.hands[color.index()][PieceType::Pawn.index()] -= 1;
                    self.promoted_pieces |= 1u64 << to;
                } else {
                    let captured_type = undo.captured.piece_type().unwrap();
                    self.hands[color.index()][captured_type.index()] -= 1;
                }
            } else {
                self.board[to] = Piece::Empty;
            }

            // Restore king position
            if let Some(prev_kp) = undo.prev_king_pos {
                self.king_pos[color.index()] = prev_kp;
            }
        }

        self.checkmate = undo.prev_checkmate;
        self.stalemate = undo.prev_stalemate;
        self.last_move = undo.prev_last_move;
        self.legal_moves_cache = None;
        self.hash = undo.prev_hash;
    }

    /// Full make_move (for GUI/online play, handles promotion choice)
    pub fn make_move(&mut self, m: Move, check_game_over: bool) -> bool {
        self.legal_moves_cache = None;

        if self.needs_promotion_choice {
            return false;
        }

        if m.is_drop() {
            let to = m.to_sq();
            let pt = m.drop_piece_type();
            let color = m.drop_color();

            if !self.board[to].is_empty() {
                return false;
            }
            if color != self.current_turn {
                return false;
            }
            if self.hands[color.index()][pt.index()] == 0 {
                return false;
            }
            // Pawn drop restriction
            let promo_rank = if color == Color::White { 0 } else { BOARD_SIZE - 1 };
            if pt == PieceType::Pawn && sq_row(to) == promo_rank {
                return false;
            }

            let piece = Piece::from_color_type(color, pt);
            self.board[to] = piece;
            self.hands[color.index()][pt.index()] -= 1;
            self.last_move = m;
            self.current_turn = self.current_turn.opposite();
            self.hash = self.compute_hash();

            if check_game_over {
                self.check_game_over();
            }
            return true;
        }

        // Normal move
        let from = m.from_sq();
        let to = m.to_sq();
        let piece = self.board[from];

        if piece.is_empty() {
            return false;
        }
        let color = match piece.color() {
            Some(c) => c,
            None => return false,
        };
        if color != self.current_turn {
            return false;
        }

        let target = self.board[to];
        let is_capture = target != Piece::Empty;

        self.board[from] = Piece::Empty;

        if is_capture {
            let mut captured_type = target.piece_type().unwrap();
            if self.promoted_pieces & (1u64 << to) != 0 {
                captured_type = PieceType::Pawn;
                self.promoted_pieces &= !(1u64 << to);
            }
            self.hands[color.index()][captured_type.index()] += 1;
        }

        // Track promoted piece movement
        if self.promoted_pieces & (1u64 << from) != 0 {
            self.promoted_pieces &= !(1u64 << from);
            self.promoted_pieces |= 1u64 << to;
        }

        if piece.piece_type() == Some(PieceType::King) {
            self.king_pos[color.index()] = to;
        }

        let is_pawn = piece.piece_type() == Some(PieceType::Pawn);
        let promo_rank = if color == Color::White { 0 } else { BOARD_SIZE - 1 };

        if is_pawn && sq_row(to) == promo_rank {
            if let Some(promo_pt) = m.promotion() {
                self.board[to] = Piece::from_color_type(color, promo_pt);
                self.promoted_pieces |= 1u64 << to;
                self.needs_promotion_choice = false;
                self.promotion_square = None;
            } else {
                // Pawn reached promotion rank, waiting for choice
                self.board[to] = piece;
                self.needs_promotion_choice = true;
                self.promotion_square = Some(to);
                self.last_move = m;
                self.hash = self.compute_hash();
                return true; // partial success
            }
        } else {
            self.board[to] = piece;
        }

        self.last_move = m;
        self.current_turn = self.current_turn.opposite();
        self.hash = self.compute_hash();

        if check_game_over {
            self.check_game_over();
        }
        true
    }

    pub fn complete_promotion(&mut self, promo_pt: PieceType) -> bool {
        if !self.needs_promotion_choice {
            return false;
        }
        let to = match self.promotion_square {
            Some(s) => s,
            None => return false,
        };
        // Color is the one who just moved (turn hasn't switched yet during promotion wait)
        let color = self.current_turn;
        let piece = Piece::from_color_type(color, promo_pt);
        self.board[to] = piece;
        self.promoted_pieces |= 1u64 << to;

        self.needs_promotion_choice = false;
        self.promotion_square = None;
        self.current_turn = self.current_turn.opposite();
        self.legal_moves_cache = None;
        self.hash = self.compute_hash();
        self.check_game_over();
        true
    }

    pub fn fast_copy(&self) -> GameState {
        GameState {
            board: self.board,
            current_turn: self.current_turn,
            hands: self.hands,
            king_pos: self.king_pos,
            checkmate: self.checkmate,
            stalemate: self.stalemate,
            last_move: self.last_move,
            game_over_message: String::new(),
            promoted_pieces: self.promoted_pieces,
            hash: self.hash,
            needs_promotion_choice: self.needs_promotion_choice,
            promotion_square: self.promotion_square,
            ai_history: Vec::new(),
            legal_moves_cache: None,
        }
    }

    pub fn find_kings(&mut self) {
        self.king_pos = [0; 2];
        for s in 0..NUM_SQUARES {
            match self.board[s] {
                Piece::WhiteKing => self.king_pos[0] = s,
                Piece::BlackKing => self.king_pos[1] = s,
                _ => {}
            }
        }
    }
}
