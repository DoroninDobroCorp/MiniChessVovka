# Architecture

## Chess Engine

- Board representation: bitboards
- Move generation: pseudo-legal + validation
- Search: alpha-beta with iterative deepening
- Evaluation: material + positional tables

## Performance

- Written in Rust for maximum speed
- Zero-copy move generation