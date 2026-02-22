use crate::types::*;
use rand::rngs::StdRng;
use rand::{SeedableRng, RngCore};

pub struct ZobristTables {
    pub piece_square: [[u64; NUM_SQUARES]; 13], // indexed by Piece as u8
    pub turn_black: u64,
    pub hand: [[[u64; 8]; 5]; 2], // [color][piece_type][count]
    pub promoted: [u64; NUM_SQUARES],
}

impl ZobristTables {
    pub fn new() -> Self {
        let mut rng = StdRng::seed_from_u64(0xDEADBEEF);
        let mut tables = ZobristTables {
            piece_square: [[0u64; NUM_SQUARES]; 13],
            turn_black: rng.next_u64(),
            hand: [[[0u64; 8]; 5]; 2],
            promoted: [0u64; NUM_SQUARES],
        };
        for piece in 0..13u8 {
            for sq in 0..NUM_SQUARES {
                tables.piece_square[piece as usize][sq] = rng.next_u64();
            }
        }
        for color in 0..2 {
            for pt in 0..5 {
                for count in 0..8 {
                    tables.hand[color][pt][count] = rng.next_u64();
                }
            }
        }
        for sq in 0..NUM_SQUARES {
            tables.promoted[sq] = rng.next_u64();
        }
        tables
    }
}

lazy_static::lazy_static! {
    pub static ref ZOBRIST: ZobristTables = ZobristTables::new();
}

pub fn get_position_hash(
    board: &[Piece; NUM_SQUARES],
    current_turn: Color,
    hands: &[[u8; 5]; 2],
    promoted_pieces: u64,
) -> u64 {
    let mut h: u64 = 0;
    for sq in 0..NUM_SQUARES {
        let piece = board[sq];
        if piece != Piece::Empty {
            h ^= ZOBRIST.piece_square[piece as usize][sq];
        }
    }
    if current_turn == Color::Black {
        h ^= ZOBRIST.turn_black;
    }
    for color in 0..2usize {
        for pt in 0..5usize {
            let count = hands[color][pt] as usize;
            if count > 0 {
                h ^= ZOBRIST.hand[color][pt][count.min(7)];
            }
        }
    }
    for sq in 0..NUM_SQUARES {
        if promoted_pieces & (1u64 << sq) != 0 {
            h ^= ZOBRIST.promoted[sq];
        }
    }
    h
}
