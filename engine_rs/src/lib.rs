mod types;
mod zobrist;
mod gamestate;
mod eval;
mod search;
mod cache;

use pyo3::prelude::*;
use pyo3::types::{PyList, PyTuple, PyDict};
use pyo3::exceptions::PyValueError;

use std::collections::HashMap;
use std::sync::Mutex;

use types::*;
use gamestate::GameState as RustGameState;

// Global move cache (thread-safe)
lazy_static::lazy_static! {
    static ref MOVE_CACHE: Mutex<HashMap<(String, i32), String>> = Mutex::new(HashMap::new());
}

/// Convert a Python move tuple to our internal Move
fn py_move_to_rust(py: Python<'_>, obj: &Bound<'_, PyAny>) -> PyResult<Move> {
    // Check if it's a drop: ('drop', 'wN', (r, f))
    if let Ok(tup) = obj.downcast::<PyTuple>() {
        if tup.len() >= 1 {
            if let Ok(first) = tup.get_item(0)?.extract::<String>() {
                if first == "drop" {
                    let code: String = tup.get_item(1)?.extract()?;
                    let target = tup.get_item(2)?;
                    let target = target.downcast::<PyTuple>()?;
                    let r: usize = target.get_item(0)?.extract()?;
                    let f: usize = target.get_item(1)?.extract()?;
                    
                    let color = match code.chars().next() {
                        Some('w') => Color::White,
                        Some('b') => Color::Black,
                        _ => return Err(PyValueError::new_err("Invalid drop color")),
                    };
                    let pt = match code.chars().nth(1) {
                        Some('P') => PieceType::Pawn,
                        Some('N') => PieceType::Knight,
                        Some('B') => PieceType::Bishop,
                        Some('R') => PieceType::Rook,
                        Some('Q') => PieceType::Queen,
                        _ => return Err(PyValueError::new_err("Invalid drop piece")),
                    };
                    return Ok(Move::new_drop(sq(r, f), pt, color));
                }
            }
            // Normal move: ((r1,f1), (r2,f2), promotion)
            if tup.len() >= 3 {
                let from = tup.get_item(0)?;
                let from = from.downcast::<PyTuple>()?;
                let r1: usize = from.get_item(0)?.extract()?;
                let f1: usize = from.get_item(1)?.extract()?;
                
                let to = tup.get_item(1)?;
                let to = to.downcast::<PyTuple>()?;
                let r2: usize = to.get_item(0)?.extract()?;
                let f2: usize = to.get_item(1)?.extract()?;
                
                let promo_obj = tup.get_item(2)?;
                let promotion = if promo_obj.is_none() {
                    None
                } else {
                    let promo_str: String = promo_obj.extract()?;
                    match promo_str.to_uppercase().as_str() {
                        "R" => Some(PieceType::Rook),
                        "N" => Some(PieceType::Knight),
                        "B" => Some(PieceType::Bishop),
                        _ => None,
                    }
                };
                
                return Ok(Move::new_normal(sq(r1, f1), sq(r2, f2), promotion));
            }
        }
    }
    Err(PyValueError::new_err("Cannot parse move"))
}

/// Convert our internal Move to a Python tuple
fn rust_move_to_py(py: Python<'_>, m: Move) -> PyObject {
    if m.is_null() {
        return py.None();
    }
    if m.is_drop() {
        let to = m.to_sq();
        let r = sq_row(to);
        let f = sq_file(to);
        let color_c = match m.drop_color() {
            Color::White => 'w',
            Color::Black => 'b',
        };
        let pt_c = match m.drop_piece_type() {
            PieceType::Pawn => 'P',
            PieceType::Knight => 'N',
            PieceType::Bishop => 'B',
            PieceType::Rook => 'R',
            PieceType::Queen => 'Q',
            _ => '?',
        };
        let code = format!("{}{}", color_c, pt_c);
        let target = PyTuple::new(py, &[r, f]).unwrap();
        PyTuple::new(py, &[
            "drop".into_pyobject(py).unwrap().into_any(),
            code.into_pyobject(py).unwrap().into_any(),
            target.into_any(),
        ]).unwrap().into()
    } else {
        let from = m.from_sq();
        let to = m.to_sq();
        let from_tup = PyTuple::new(py, &[sq_row(from), sq_file(from)]).unwrap();
        let to_tup = PyTuple::new(py, &[sq_row(to), sq_file(to)]).unwrap();
        let promo: PyObject = match m.promotion() {
            Some(pt) => {
                // Determine case from context: white promotes with uppercase
                let c = match pt {
                    PieceType::Rook => "R",
                    PieceType::Knight => "N",
                    PieceType::Bishop => "B",
                    _ => "?",
                };
                c.into_pyobject(py).unwrap().into_any().unbind()
            }
            None => py.None(),
        };
        PyTuple::new(py, &[
            from_tup.into_any().unbind(),
            to_tup.into_any().unbind(),
            promo,
        ]).unwrap().into()
    }
}

#[pyclass(name = "GameState")]
pub struct PyGameState {
    inner: RustGameState,
    // Store extra Python-compatible fields
    #[pyo3(get, set)]
    white_ai_enabled: bool,
    #[pyo3(get, set)]
    black_ai_enabled: bool,
    #[pyo3(get, set)]
    ai_depth: i32,
    #[pyo3(get, set)]
    show_hint: bool,
    #[pyo3(get, set)]
    selected_square: Option<(usize, usize)>,
    #[pyo3(get, set)]
    selected_drop_piece: Option<String>,
    #[pyo3(get, set)]
    highlighted_moves: PyObject,
    // For undo (simplified: just track states)
    saved_states_count: usize,
}

#[pymethods]
impl PyGameState {
    #[new]
    fn new(py: Python<'_>) -> Self {
        PyGameState {
            inner: RustGameState::new(),
            white_ai_enabled: false,
            black_ai_enabled: false,
            ai_depth: 6,
            show_hint: false,
            selected_square: None,
            selected_drop_piece: None,
            highlighted_moves: PyList::empty(py).into(),
            saved_states_count: 0,
        }
    }

    fn setup_initial_board(&mut self) {
        self.inner.setup_initial_board();
        self.saved_states_count = 1;
    }

    fn save_state(&mut self) {
        self.saved_states_count += 1;
    }

    #[pyo3(signature = (m, is_check_game_over=None))]
    fn make_move(&mut self, py: Python<'_>, m: &Bound<'_, PyAny>, is_check_game_over: Option<bool>) -> PyResult<bool> {
        let check = is_check_game_over.unwrap_or(true);
        let rm = py_move_to_rust(py, m)?;
        Ok(self.inner.make_move(rm, check))
    }

    fn undo_move(&mut self) -> bool {
        // Simple: undo last AI move if available
        if self.inner.ai_history.is_empty() {
            return false;
        }
        self.inner.undo_ai_move();
        true
    }

    fn make_ai_move(&mut self, py: Python<'_>, m: &Bound<'_, PyAny>) -> PyResult<bool> {
        let rm = py_move_to_rust(py, m)?;
        self.inner.make_ai_move(rm);
        Ok(true)
    }

    fn undo_ai_move(&mut self) -> bool {
        self.inner.undo_ai_move();
        true
    }

    fn get_all_legal_moves<'py>(&mut self, py: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        let moves = self.inner.get_legal_moves_vec();
        let py_moves: Vec<PyObject> = moves.iter().map(|&m| rust_move_to_py(py, m)).collect();
        Ok(PyList::new(py, &py_moves)?)
    }

    fn is_in_check(&self, color: &str) -> bool {
        let c = match color {
            "w" => Color::White,
            "b" => Color::Black,
            _ => return false,
        };
        self.inner.is_in_check(c)
    }

    fn check_game_over(&mut self) -> bool {
        self.inner.check_game_over()
    }

    fn complete_promotion(&mut self, piece_char: &str) -> bool {
        let pt = match piece_char.to_uppercase().as_str() {
            "R" => PieceType::Rook,
            "N" => PieceType::Knight,
            "B" => PieceType::Bishop,
            _ => return false,
        };
        self.inner.complete_promotion(pt)
    }

    fn copy(&self, py: Python<'_>) -> PyGameState {
        PyGameState {
            inner: self.inner.clone(),
            white_ai_enabled: self.white_ai_enabled,
            black_ai_enabled: self.black_ai_enabled,
            ai_depth: self.ai_depth,
            show_hint: self.show_hint,
            selected_square: None,
            selected_drop_piece: None,
            highlighted_moves: PyList::empty(py).into(),
            saved_states_count: self.saved_states_count,
        }
    }

    fn fast_copy_for_simulation(&self, py: Python<'_>) -> PyGameState {
        PyGameState {
            inner: self.inner.fast_copy(),
            white_ai_enabled: false,
            black_ai_enabled: false,
            ai_depth: self.ai_depth,
            show_hint: false,
            selected_square: None,
            selected_drop_piece: None,
            highlighted_moves: PyList::empty(py).into(),
            saved_states_count: 0,
        }
    }

    fn find_kings(&mut self) {
        self.inner.find_kings();
    }

    fn generate_all_pseudo_legal_moves<'py>(&self, py: Python<'py>, color: &str) -> PyResult<Bound<'py, PyList>> {
        let c = match color {
            "w" => Color::White,
            "b" => Color::Black,
            _ => return Err(PyValueError::new_err("Invalid color")),
        };
        let moves = self.inner.generate_pseudo_legal_moves(c);
        let py_moves: Vec<PyObject> = moves.iter().map(|&m| rust_move_to_py(py, m)).collect();
        Ok(PyList::new(py, &py_moves)?)
    }

    fn is_move_legal(&mut self, py: Python<'_>, m: &Bound<'_, PyAny>) -> PyResult<bool> {
        let rm = py_move_to_rust(py, m)?;
        let legal = self.inner.get_legal_moves_vec();
        Ok(legal.contains(&rm))
    }

    fn reset_board(&mut self) {
        self.inner = RustGameState::new();
        self.saved_states_count = 0;
    }

    // Properties
    #[getter]
    fn board<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        let mut rows = Vec::with_capacity(BOARD_SIZE);
        for r in 0..BOARD_SIZE {
            let mut row = Vec::with_capacity(BOARD_SIZE);
            for f in 0..BOARD_SIZE {
                row.push(self.inner.board[sq(r, f)].to_char().to_string());
            }
            rows.push(PyList::new(py, &row)?);
        }
        Ok(PyList::new(py, &rows)?)
    }

    #[setter]
    fn set_board(&mut self, _py: Python<'_>, value: &Bound<'_, PyList>) -> PyResult<()> {
        for r in 0..BOARD_SIZE {
            let row = value.get_item(r)?;
            let row = row.downcast::<PyList>()?;
            for f in 0..BOARD_SIZE {
                let cell: String = row.get_item(f)?.extract()?;
                self.inner.board[sq(r, f)] = Piece::from_char(cell.chars().next().unwrap_or('.'));
            }
        }
        self.inner.find_kings();
        self.inner.hash = self.inner.compute_hash();
        self.inner.invalidate_cache();
        Ok(())
    }

    #[getter]
    fn current_turn(&self) -> &str {
        match self.inner.current_turn {
            Color::White => "w",
            Color::Black => "b",
        }
    }

    #[setter]
    fn set_current_turn(&mut self, value: &str) {
        self.inner.current_turn = match value {
            "b" => Color::Black,
            _ => Color::White,
        };
        self.inner.hash = self.inner.compute_hash();
        self.inner.invalidate_cache();
    }

    #[getter]
    fn hands<'py>(&self, py: Python<'py>) -> PyResult<PyObject> {
        let d = PyDict::new(py);
        for (ci, color_str) in [(0usize, "w"), (1, "b")] {
            let hand = PyDict::new(py);
            for (pi, piece_str) in [(0, "P"), (1, "N"), (2, "B"), (3, "R"), (4, "Q")] {
                hand.set_item(piece_str, self.inner.hands[ci][pi] as i32)?;
            }
            d.set_item(color_str, hand)?;
        }
        Ok(d.into())
    }

    #[setter]
    fn set_hands(&mut self, _py: Python<'_>, value: &Bound<'_, PyDict>) -> PyResult<()> {
        for (ci, color_str) in [(0usize, "w"), (1usize, "b")] {
            if let Some(hand_obj) = value.get_item(color_str)? {
                let hand = hand_obj.downcast::<PyDict>()?;
                for (pi, piece_str) in [(0usize, "P"), (1, "N"), (2, "B"), (3, "R"), (4, "Q")] {
                    if let Some(count) = hand.get_item(piece_str)? {
                        self.inner.hands[ci][pi] = count.extract::<i32>()? as u8;
                    }
                }
            }
        }
        self.inner.hash = self.inner.compute_hash();
        Ok(())
    }

    #[getter]
    fn king_pos<'py>(&self, py: Python<'py>) -> PyResult<PyObject> {
        let d = PyDict::new(py);
        for (ci, color_str) in [(0usize, "w"), (1, "b")] {
            let s = self.inner.king_pos[ci];
            let tup = PyTuple::new(py, &[sq_row(s), sq_file(s)])?;
            d.set_item(color_str, tup)?;
        }
        Ok(d.into())
    }

    #[setter]
    fn set_king_pos(&mut self, _py: Python<'_>, value: &Bound<'_, PyDict>) -> PyResult<()> {
        for (ci, color_str) in [(0usize, "w"), (1, "b")] {
            if let Some(pos_obj) = value.get_item(color_str)? {
                if !pos_obj.is_none() {
                    let tup = pos_obj.downcast::<PyTuple>()?;
                    let r: usize = tup.get_item(0)?.extract()?;
                    let f: usize = tup.get_item(1)?.extract()?;
                    self.inner.king_pos[ci] = sq(r, f);
                }
            }
        }
        Ok(())
    }

    #[getter]
    fn checkmate(&self) -> bool { self.inner.checkmate }

    #[setter]
    fn set_checkmate(&mut self, v: bool) { self.inner.checkmate = v; }

    #[getter]
    fn stalemate(&self) -> bool { self.inner.stalemate }

    #[setter]
    fn set_stalemate(&mut self, v: bool) { self.inner.stalemate = v; }

    #[getter]
    fn last_move<'py>(&self, py: Python<'py>) -> PyObject {
        rust_move_to_py(py, self.inner.last_move)
    }

    #[setter]
    fn set_last_move(&mut self, py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<()> {
        if value.is_none() {
            self.inner.last_move = Move::NULL;
        } else {
            self.inner.last_move = py_move_to_rust(py, value)?;
        }
        Ok(())
    }

    #[getter]
    fn game_over_message(&self) -> &str { &self.inner.game_over_message }

    #[getter]
    fn needs_promotion_choice(&self) -> bool { self.inner.needs_promotion_choice }

    #[setter]
    fn set_needs_promotion_choice(&mut self, v: bool) { self.inner.needs_promotion_choice = v; }

    #[getter]
    fn promotion_square<'py>(&self, py: Python<'py>) -> PyObject {
        match self.inner.promotion_square {
            Some(s) => PyTuple::new(py, &[sq_row(s), sq_file(s)]).unwrap().into(),
            None => py.None(),
        }
    }

    #[getter]
    fn promoted_pieces<'py>(&self, py: Python<'py>) -> PyResult<PyObject> {
        let pyset = pyo3::types::PySet::empty(py)?;
        for s in 0..NUM_SQUARES {
            if self.inner.promoted_pieces & (1u64 << s) != 0 {
                let tup = PyTuple::new(py, &[sq_row(s), sq_file(s)])?;
                pyset.add(tup)?;
            }
        }
        Ok(pyset.into())
    }

    #[setter]
    fn set_promoted_pieces(&mut self, _py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<()> {
        self.inner.promoted_pieces = 0;
        let iter = value.try_iter()?;
        for item in iter {
            let item = item?;
            let tup = item.downcast::<PyTuple>()?;
            let r: usize = tup.get_item(0)?.extract()?;
            let f: usize = tup.get_item(1)?.extract()?;
            self.inner.promoted_pieces |= 1u64 << sq(r, f);
        }
        Ok(())
    }

    #[getter]
    fn move_log<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        // Return empty list (move_log is tracked in Python frontends)
        Ok(PyList::empty(py))
    }

    #[getter]
    fn last_move_for_promotion<'py>(&self, py: Python<'py>) -> PyObject {
        py.None()
    }

    #[getter]
    fn saved_states<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        // Return dummy list with correct length for undo logic
        let items: Vec<i32> = (0..self.saved_states_count as i32).collect();
        Ok(PyList::new(py, &items)?)
    }

    #[getter]
    fn ai_history<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        let items: Vec<i32> = (0..self.inner.ai_history.len() as i32).collect();
        Ok(PyList::new(py, &items)?)
    }

    // Extra getters that Python code accesses
    #[getter]
    fn _all_legal_moves_cache(&self) -> Option<bool> {
        None  // Always return None to match Python behavior
    }

    #[setter]
    fn set__all_legal_moves_cache(&mut self, _v: Option<bool>) {
        self.inner.invalidate_cache();
    }

    #[getter]
    fn _hash_cache(&self) -> Option<bool> { None }

    #[setter]
    fn set__hash_cache(&mut self, _v: Option<bool>) {}

    #[getter]
    fn _is_check_cache(&self) -> Option<bool> { None }

    #[setter]
    fn set__is_check_cache(&mut self, _v: Option<bool>) {}
}

// Module-level AI functions
#[pyfunction]
#[pyo3(signature = (gs, depth=None, return_top_n=None, time_limit=None))]
fn find_best_move(py: Python<'_>, gs: &mut PyGameState, depth: Option<i32>, return_top_n: Option<i32>, time_limit: Option<f64>) -> PyResult<PyObject> {
    let d = depth.unwrap_or(6);
    let top_n = return_top_n.unwrap_or(1);
    
    let mut cache = MOVE_CACHE.lock().unwrap();
    let (best, score) = search::find_best_move(&mut gs.inner, d, &mut cache, time_limit);
    
    if top_n == 1 {
        Ok(rust_move_to_py(py, best))
    } else {
        // Return list of (move, score)
        let list = PyList::empty(py);
        if !best.is_null() {
            let tup = PyTuple::new(py, &[
                rust_move_to_py(py, best),
                score.into_pyobject(py)?.into_any().unbind(),
            ])?;
            list.append(tup)?;
        }
        Ok(list.into())
    }
}

#[pyfunction]
fn evaluate_position(_py: Python<'_>, gs: &PyGameState) -> f64 {
    eval::evaluate_position(&gs.inner) as f64
}

#[pyfunction]
fn get_position_hash(gs: &PyGameState) -> String {
    gs.inner.hash.to_string()
}

#[pyfunction]
fn load_move_cache_from_db() {
    let loaded = cache::load_move_cache();
    let mut cache = MOVE_CACHE.lock().unwrap();
    *cache = loaded;
}

#[pyfunction]
#[pyo3(signature = (_cache_arg=None))]
fn save_move_cache_to_db(_py: Python<'_>, _cache_arg: Option<&Bound<'_, PyAny>>) {
    let cache = MOVE_CACHE.lock().unwrap();
    cache::save_move_cache(&cache);
}

#[pyfunction]
fn setup_db() {
    let _ = cache::setup_db();
}

#[pyfunction]
fn is_move_still_legal(py: Python<'_>, gs: &mut PyGameState, m: &Bound<'_, PyAny>) -> PyResult<bool> {
    let rm = py_move_to_rust(py, m)?;
    let legal = gs.inner.get_legal_moves_vec();
    Ok(legal.contains(&rm))
}

#[pyfunction]
fn parse_move_string(py: Python<'_>, s: &str) -> PyResult<PyObject> {
    match search::parse_move_repr(s) {
        Some(m) => Ok(rust_move_to_py(py, m)),
        None => Ok(py.None()),
    }
}

#[pymodule]
fn minichess_engine(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyGameState>()?;
    m.add_function(wrap_pyfunction!(find_best_move, m)?)?;
    m.add_function(wrap_pyfunction!(evaluate_position, m)?)?;
    m.add_function(wrap_pyfunction!(get_position_hash, m)?)?;
    m.add_function(wrap_pyfunction!(load_move_cache_from_db, m)?)?;
    m.add_function(wrap_pyfunction!(save_move_cache_to_db, m)?)?;
    m.add_function(wrap_pyfunction!(setup_db, m)?)?;
    m.add_function(wrap_pyfunction!(is_move_still_legal, m)?)?;
    m.add_function(wrap_pyfunction!(parse_move_string, m)?)?;
    
    // Re-export constants needed by Python
    m.add("CHECKMATE_SCORE", eval::CHECKMATE_SCORE)?;
    m.add("STALEMATE_SCORE", eval::STALEMATE_SCORE)?;
    m.add("BOARD_SIZE", BOARD_SIZE)?;
    
    Ok(())
}
