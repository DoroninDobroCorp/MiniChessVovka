use std::fmt;

pub const BOARD_SIZE: usize = 6;
pub const NUM_SQUARES: usize = BOARD_SIZE * BOARD_SIZE;

#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
#[repr(u8)]
pub enum Piece {
    Empty = 0,
    WhitePawn = 1,
    WhiteKnight = 2,
    WhiteBishop = 3,
    WhiteRook = 4,
    WhiteQueen = 5,
    WhiteKing = 6,
    BlackPawn = 7,
    BlackKnight = 8,
    BlackBishop = 9,
    BlackRook = 10,
    BlackQueen = 11,
    BlackKing = 12,
}

#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Color {
    White,
    Black,
}

impl Color {
    #[inline]
    pub fn opposite(self) -> Color {
        match self {
            Color::White => Color::Black,
            Color::Black => Color::White,
        }
    }

    #[inline]
    pub fn index(self) -> usize {
        self as usize
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
#[repr(u8)]
pub enum PieceType {
    Pawn = 0,
    Knight = 1,
    Bishop = 2,
    Rook = 3,
    Queen = 4,
    King = 5,
}

pub const HAND_PIECE_TYPES: [PieceType; 5] = [
    PieceType::Pawn,
    PieceType::Knight,
    PieceType::Bishop,
    PieceType::Rook,
    PieceType::Queen,
];

impl PieceType {
    #[inline]
    pub fn index(self) -> usize {
        self as usize
    }
}

impl Piece {
    #[inline]
    pub fn color(self) -> Option<Color> {
        match self {
            Piece::Empty => None,
            Piece::WhitePawn | Piece::WhiteKnight | Piece::WhiteBishop
            | Piece::WhiteRook | Piece::WhiteQueen | Piece::WhiteKing => Some(Color::White),
            _ => Some(Color::Black),
        }
    }

    #[inline]
    pub fn piece_type(self) -> Option<PieceType> {
        match self {
            Piece::Empty => None,
            Piece::WhitePawn | Piece::BlackPawn => Some(PieceType::Pawn),
            Piece::WhiteKnight | Piece::BlackKnight => Some(PieceType::Knight),
            Piece::WhiteBishop | Piece::BlackBishop => Some(PieceType::Bishop),
            Piece::WhiteRook | Piece::BlackRook => Some(PieceType::Rook),
            Piece::WhiteQueen | Piece::BlackQueen => Some(PieceType::Queen),
            Piece::WhiteKing | Piece::BlackKing => Some(PieceType::King),
        }
    }

    #[inline]
    pub fn is_empty(self) -> bool {
        self == Piece::Empty
    }

    pub fn from_color_type(color: Color, pt: PieceType) -> Piece {
        match (color, pt) {
            (Color::White, PieceType::Pawn) => Piece::WhitePawn,
            (Color::White, PieceType::Knight) => Piece::WhiteKnight,
            (Color::White, PieceType::Bishop) => Piece::WhiteBishop,
            (Color::White, PieceType::Rook) => Piece::WhiteRook,
            (Color::White, PieceType::Queen) => Piece::WhiteQueen,
            (Color::White, PieceType::King) => Piece::WhiteKing,
            (Color::Black, PieceType::Pawn) => Piece::BlackPawn,
            (Color::Black, PieceType::Knight) => Piece::BlackKnight,
            (Color::Black, PieceType::Bishop) => Piece::BlackBishop,
            (Color::Black, PieceType::Rook) => Piece::BlackRook,
            (Color::Black, PieceType::Queen) => Piece::BlackQueen,
            (Color::Black, PieceType::King) => Piece::BlackKing,
        }
    }

    /// Convert char like 'P','n','B',etc to Piece
    pub fn from_char(c: char) -> Piece {
        match c {
            'P' => Piece::WhitePawn,
            'N' => Piece::WhiteKnight,
            'B' => Piece::WhiteBishop,
            'R' => Piece::WhiteRook,
            'Q' => Piece::WhiteQueen,
            'K' => Piece::WhiteKing,
            'p' => Piece::BlackPawn,
            'n' => Piece::BlackKnight,
            'b' => Piece::BlackBishop,
            'r' => Piece::BlackRook,
            'q' => Piece::BlackQueen,
            'k' => Piece::BlackKing,
            _ => Piece::Empty,
        }
    }

    pub fn to_char(self) -> char {
        match self {
            Piece::Empty => '.',
            Piece::WhitePawn => 'P',
            Piece::WhiteKnight => 'N',
            Piece::WhiteBishop => 'B',
            Piece::WhiteRook => 'R',
            Piece::WhiteQueen => 'Q',
            Piece::WhiteKing => 'K',
            Piece::BlackPawn => 'p',
            Piece::BlackKnight => 'n',
            Piece::BlackBishop => 'b',
            Piece::BlackRook => 'r',
            Piece::BlackQueen => 'q',
            Piece::BlackKing => 'k',
        }
    }
}

/// Compact move representation
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
pub struct Move {
    pub data: u32,
}

// Encoding:
// Bit 0:     is_drop (1=drop, 0=normal)
// Normal move: bits 1-6: from_sq, bits 7-12: to_sq, bits 13-15: promotion (0=none, 1=R, 2=N, 3=B)
// Drop move:   bits 1-6: to_sq, bits 7-9: piece_type(0-4), bit 10: color(0=W,1=B)

impl Move {
    pub const NULL: Move = Move { data: u32::MAX };

    #[inline]
    pub fn new_normal(from: usize, to: usize, promotion: Option<PieceType>) -> Move {
        let promo = match promotion {
            None => 0u32,
            Some(PieceType::Rook) => 1,
            Some(PieceType::Knight) => 2,
            Some(PieceType::Bishop) => 3,
            _ => 0,
        };
        Move {
            data: 0 | ((from as u32) << 1) | ((to as u32) << 7) | (promo << 13),
        }
    }

    #[inline]
    pub fn new_drop(to: usize, pt: PieceType, color: Color) -> Move {
        let c = match color {
            Color::White => 0u32,
            Color::Black => 1,
        };
        Move {
            data: 1 | ((to as u32) << 1) | ((pt as u32) << 7) | (c << 10),
        }
    }

    #[inline]
    pub fn is_drop(self) -> bool {
        self.data & 1 == 1
    }

    #[inline]
    pub fn is_null(self) -> bool {
        self.data == u32::MAX
    }

    // Normal move accessors
    #[inline]
    pub fn from_sq(self) -> usize {
        ((self.data >> 1) & 0x3F) as usize
    }

    #[inline]
    pub fn to_sq(self) -> usize {
        if self.is_drop() {
            ((self.data >> 1) & 0x3F) as usize
        } else {
            ((self.data >> 7) & 0x3F) as usize
        }
    }

    #[inline]
    pub fn promotion(self) -> Option<PieceType> {
        if self.is_drop() {
            return None;
        }
        match (self.data >> 13) & 0x7 {
            1 => Some(PieceType::Rook),
            2 => Some(PieceType::Knight),
            3 => Some(PieceType::Bishop),
            _ => None,
        }
    }

    // Drop move accessors
    #[inline]
    pub fn drop_piece_type(self) -> PieceType {
        match (self.data >> 7) & 0x7 {
            0 => PieceType::Pawn,
            1 => PieceType::Knight,
            2 => PieceType::Bishop,
            3 => PieceType::Rook,
            4 => PieceType::Queen,
            _ => PieceType::Pawn,
        }
    }

    #[inline]
    pub fn drop_color(self) -> Color {
        if (self.data >> 10) & 1 == 0 {
            Color::White
        } else {
            Color::Black
        }
    }
}

impl fmt::Debug for Move {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if self.is_null() {
            write!(f, "NULL")
        } else if self.is_drop() {
            let pt = self.drop_piece_type();
            let color = self.drop_color();
            let to = self.to_sq();
            let (tr, tf) = (to / BOARD_SIZE, to % BOARD_SIZE);
            write!(
                f,
                "drop {:?}{:?}@{}{}",
                color,
                pt,
                (b'a' + tf as u8) as char,
                BOARD_SIZE - tr
            )
        } else {
            let from = self.from_sq();
            let to = self.to_sq();
            let (fr, ff) = (from / BOARD_SIZE, from % BOARD_SIZE);
            let (tr, tf) = (to / BOARD_SIZE, to % BOARD_SIZE);
            write!(
                f,
                "{}{}{}{}",
                (b'a' + ff as u8) as char,
                BOARD_SIZE - fr,
                (b'a' + tf as u8) as char,
                BOARD_SIZE - tr
            )?;
            if let Some(p) = self.promotion() {
                write!(f, "={:?}", p)?;
            }
            Ok(())
        }
    }
}

// Square helpers
#[inline]
pub fn sq(r: usize, f: usize) -> usize {
    r * BOARD_SIZE + f
}

#[inline]
pub fn sq_row(s: usize) -> usize {
    s / BOARD_SIZE
}

#[inline]
pub fn sq_file(s: usize) -> usize {
    s % BOARD_SIZE
}

#[inline]
pub fn is_on_board(r: i32, f: i32) -> bool {
    r >= 0 && r < BOARD_SIZE as i32 && f >= 0 && f < BOARD_SIZE as i32
}

pub const KNIGHT_OFFSETS: [(i32, i32); 8] = [
    (1, 2), (1, -2), (-1, 2), (-1, -2),
    (2, 1), (2, -1), (-2, 1), (-2, -1),
];

pub const DIAGONAL_OFFSETS: [(i32, i32); 4] = [(1, 1), (1, -1), (-1, 1), (-1, -1)];
pub const STRAIGHT_OFFSETS: [(i32, i32); 4] = [(1, 0), (-1, 0), (0, 1), (0, -1)];
pub const KING_OFFSETS: [(i32, i32); 8] = [
    (1, 1), (1, -1), (-1, 1), (-1, -1),
    (1, 0), (-1, 0), (0, 1), (0, -1),
];

/// Piece values in centipawns
pub const PIECE_VALUES: [i32; 6] = [100, 320, 330, 500, 900, 20000]; // P N B R Q K
// Hand pieces worth significantly more: instant deployment, surprise factor, tempo
pub const HAND_PIECE_VALUES: [i32; 5] = [200, 550, 530, 800, 1200]; // P N B R Q

pub const PROMOTION_PIECES: [PieceType; 3] = [PieceType::Rook, PieceType::Knight, PieceType::Bishop];
