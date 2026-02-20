#!/usr/bin/env python3
"""
MiniChess Online Bot — plays minihouse on chess.com via Chrome + Playwright.

Uses the trained move_cache.db and AI engine from the MiniChess project.
Browser automation borrowed from research-automation patterns.

Usage:
    # From MiniChess directory, using research-automation's venv:
    ../research-automation/venv/bin/python play_online.py
"""

import json
import os
import random
import socket
import subprocess
import sys
import time
import sqlite3
import hashlib
import copy
from pathlib import Path

# ── Playwright import ───────────────────────────────────────
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("❌ Need playwright. Run: pip install playwright && python -m playwright install chromium")
    sys.exit(1)

# ── MiniChess engine imports ────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from gamestate import GameState
import ai as ai_module
from ai import get_position_hash, find_best_move, setup_db, load_move_cache_from_db, evaluate_position
from config import BOARD_SIZE
from pieces import EMPTY_SQUARE
from utils import coords_to_algebraic, format_move_for_print

# ── Config ──────────────────────────────────────────────────
CHESS_COM_URL = "https://www.chess.com"
PROFILE_DIR = Path(__file__).parent / ".chess_com_profile"
STATE_FILE = Path(__file__).parent / ".chess_com_chrome_state.json"
OUTPUT_DIR = Path(__file__).parent / ".bot_screenshots"

# Credentials (NOT committed — .gitignore should cover dotfiles)
EMAIL = "***REMOVED***"
PASSWORD = "***REMOVED***"

CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium-browser",
]

STEALTH_SCRIPT = """
(function() {
    const proto = Object.getPrototypeOf(navigator);
    try { delete proto.webdriver; } catch(e) {}
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined, configurable: true
    });
    window.chrome = {runtime: {}};
})();
"""

# ── Board mapping ───────────────────────────────────────────
# chess.com 6x6: square-XY where X=file(1-6), Y=rank(1-6)
# Our board: row 0 = rank 6 (top), row 5 = rank 1 (bottom)
# Our board: col 0 = file a (=1), col 5 = file f (=6)

# chess.com piece classes for minihouse:
# wp=white pawn, wn=white knight, wb=white bishop, wr=white rook, wq=white queen, wk=white king
# bp, bn, bb, br, bq, bk = black pieces
CHESSCOM_TO_PIECE = {
    'wp': 'P', 'wn': 'N', 'wb': 'B', 'wr': 'R', 'wq': 'Q', 'wk': 'K',
    'bp': 'p', 'bn': 'n', 'bb': 'b', 'br': 'r', 'bq': 'q', 'bk': 'k',
}

PIECE_TO_CHESSCOM = {v: k for k, v in CHESSCOM_TO_PIECE.items()}

# Variants site uses data-piece (uppercase letter) + data-color (5=white, 6=black)
VARIANTS_COLOR_MAP = {'5': 'w', '6': 'b'}
VARIANTS_PIECE_MAP = {
    ('P', '5'): 'P', ('N', '5'): 'N', ('B', '5'): 'B', ('R', '5'): 'R', ('Q', '5'): 'Q', ('K', '5'): 'K',
    ('P', '6'): 'p', ('N', '6'): 'n', ('B', '6'): 'b', ('R', '6'): 'r', ('Q', '6'): 'q', ('K', '6'): 'k',
}

# Grid constants: 8x8 grid with 6x6 playable area (grid 1-6), walls at 0 and 7
GRID_OFFSET = 1  # playable area starts at grid position 1


def square_xy_to_internal(x, y):
    """chess.com square-XY (1-indexed file, rank) → internal (row, col)."""
    col = x - 1  # file 1 → col 0
    row = BOARD_SIZE - y  # rank 6 → row 0, rank 1 → row 5
    return row, col


def internal_to_square_xy(row, col):
    """Internal (row, col) → chess.com square-XY (1-indexed)."""
    x = col + 1
    y = BOARD_SIZE - row
    return x, y


def grid_to_internal(grid_col, grid_row, flipped=False):
    """Variants 8x8 grid position → internal (row, col) for 6x6 board.
    
    Grid (1,1) = top-left of playable area, (6,6) = bottom-right.
    When not flipped (white bottom): grid_row 1 = top = internal row 0, grid_row 6 = bottom = row 5.
    When flipped (black bottom): reversed.
    """
    if flipped:
        internal_col = BOARD_SIZE - (grid_col - GRID_OFFSET)  - 1
        internal_row = BOARD_SIZE - (grid_row - GRID_OFFSET) - 1
    else:
        internal_col = grid_col - GRID_OFFSET
        internal_row = grid_row - GRID_OFFSET
    return internal_row, internal_col


def internal_to_grid(row, col, flipped=False):
    """Internal (row, col) → variants 8x8 grid position."""
    if flipped:
        grid_col = BOARD_SIZE - col - 1 + GRID_OFFSET
        grid_row = BOARD_SIZE - row - 1 + GRID_OFFSET
    else:
        grid_col = col + GRID_OFFSET
        grid_row = row + GRID_OFFSET
    return grid_col, grid_row


# ── Chrome helpers (from research-automation) ───────────────

def _find_chrome():
    for p in CHROME_PATHS:
        if os.path.exists(p):
            return p
    return None


def _free_port():
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _screenshot(page, name):
    out = OUTPUT_DIR / f"{name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        page.screenshot(path=str(out))
        print(f"   📸 {out}")
    except Exception:
        pass


def launch_chrome(profile_dir):
    chrome = _find_chrome()
    if not chrome:
        print("❌ Chrome not found!")
        sys.exit(1)
    
    port = _free_port()
    profile_dir.mkdir(parents=True, exist_ok=True)
    
    args = [
        chrome,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-blink-features=AutomationControlled",
        "--disable-automation",
        "--disable-infobars",
        "--disable-component-update",
        "--password-store=basic",
        "--use-mock-keychain",
        "--enable-features=NetworkService,NetworkServiceInProcess",
        "--window-size=1440,900",
    ]
    
    # Headless mode for servers without display
    if not os.environ.get("DISPLAY"):
        args += ["--headless=new", "--no-sandbox", "--disable-gpu"]
    
    args.append("about:blank")
    
    # Kill any lingering Chrome with our profile before launching
    try:
        result = subprocess.run(["pgrep", "-f", str(profile_dir)], capture_output=True, text=True)
        for pid_str in result.stdout.strip().split('\n'):
            if pid_str.strip():
                try:
                    os.kill(int(pid_str.strip()), 9)
                except Exception:
                    pass
        if result.stdout.strip():
            time.sleep(2)
    except Exception:
        pass
    
    proc = subprocess.Popen(
        args, start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(3)
    
    if proc.poll() is not None:
        print("❌ Chrome exited immediately, retrying in 5s...")
        time.sleep(5)
        proc = subprocess.Popen(
            args, start_new_session=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(3)
        if proc.poll() is not None:
            print("❌ Chrome failed to start twice")
            sys.exit(1)
    
    print(f"   🌐 Chrome PID: {proc.pid}, CDP port: {port}")
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"pid": proc.pid, "port": port, "profile": str(profile_dir)}))
    return proc, port


def _chrome_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _cdp_alive(port):
    try:
        s = socket.socket()
        s.settimeout(2)
        s.connect(("127.0.0.1", port))
        s.close()
        return True
    except Exception:
        return False


def get_or_launch_chrome(profile_dir):
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
            pid, port = state["pid"], state["port"]
            if _chrome_alive(pid) and _cdp_alive(port):
                print(f"   ♻️  Reconnecting to Chrome (PID: {pid}, CDP: {port})")
                return None, port
        except Exception:
            pass
    return launch_chrome(profile_dir)


def connect_cdp(pw, port):
    for attempt in range(10):
        try:
            browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            print("   ✅ CDP connected")
            return browser
        except Exception:
            if attempt == 9:
                return None
            time.sleep(1)


def setup_stealth(context, page):
    try:
        client = context.new_cdp_session(page)
        client.send("Page.addScriptToEvaluateOnNewDocument", {"source": STEALTH_SCRIPT})
        client.send("Page.setBypassCSP", {"enabled": True})
    except Exception:
        pass


# ── Login ───────────────────────────────────────────────────

def dismiss_popups(page):
    """Dismiss cookie consent, GDPR banners, and other popups."""
    # First try: common cookie consent selectors
    for selector in [
        '#onetrust-accept-btn-handler',
        'button#onetrust-accept-btn-handler',
        '[id*="onetrust"] button[id*="accept"]',
        'button:has-text("Accept All")',
        'button:has-text("Accept")',
        'button:has-text("Agree")',
        'button:has-text("I Agree")',
        'button:has-text("Got it")',
        'button:has-text("OK")',
        'button:has-text("Принять")',
        '[class*="cookie"] button',
        '[id*="cookie"] button',
        '[class*="consent"] button',
        '.modal-close-icon',
        '[class*="banner"] button',
        '[class*="gdpr"] button',
        # chess.com specific
        'button.cookie-banner-accept',
        '[data-test-element="cookie-banner-accept"]',
    ]:
        try:
            btn = page.locator(selector)
            if btn.count() > 0:
                btn.first.click(force=True, timeout=3000)
                print(f"   🍪 Dismissed popup: {selector[:40]}")
                time.sleep(1)
                return True
        except Exception:
            pass

    # Second try: use JS to find and click any accept/agree button
    clicked = page.evaluate("""() => {
        const buttons = document.querySelectorAll('button, a, div[role="button"]');
        for (const btn of buttons) {
            const text = (btn.textContent || '').trim().toLowerCase();
            if (text === 'accept' || text === 'accept all' || text === 'agree' || 
                text === 'i agree' || text === 'ok' || text === 'got it' ||
                text === 'accept all cookies') {
                btn.click();
                return text;
            }
        }
        // Try removing overlay elements directly
        const overlays = document.querySelectorAll('[id*="onetrust"], [class*="cookie-banner"], [class*="consent"], [id*="cookie"]');
        overlays.forEach(el => el.remove());
        return overlays.length > 0 ? 'removed-overlays' : null;
    }""")
    if clicked:
        print(f"   🍪 Dismissed via JS: {clicked}")
        time.sleep(1)
        return True

    return False


def login_chess_com(page):
    """Login to chess.com via Google OAuth."""
    print("\n🔐 Logging into chess.com via Google...")

    # Check if already logged in WITHOUT navigating away (preserve current page/game)
    current_url = page.url or ''
    in_game = '/game/' in current_url
    
    # Try to detect login state from current page (sidebar has username if logged in)
    try:
        logged_in = page.evaluate("""() => {
            // Check for username in sidebar or header
            const el = document.querySelector('.sidebar-link .cc-user-username, .user-tagline-username, .header-user-avatar');
            return !!el;
        }""")
        if logged_in:
            print("   ✅ Already logged in!")
            return True
    except Exception:
        pass
    
    # Also check for ClaudeOpus5 text anywhere in sidebar
    try:
        opus = page.locator('text=ClaudeOpus5')
        if opus.count() > 0:
            print("   ✅ Already logged in!")
            return True
    except Exception:
        pass

    # Not logged in — navigate to home to verify (only if NOT in a game)
    if in_game:
        print("   ⚠️  In a game, skipping login check")
        return True
        
    page.goto(f"{CHESS_COM_URL}/home", timeout=60000)
    time.sleep(4)
    dismiss_popups(page)

    # If we're on /home and NOT redirected to /login, we're logged in
    if 'chess.com' in page.url and '/login' not in page.url.lower():
        # Double-check: look for "Sign Up" button (present when NOT logged in)
        signup = page.locator('a#menu-cta:has-text("Sign Up")')
        if signup.count() == 0:
            print("   ✅ Already logged in!")
            return True

    # Go to login page
    page.goto(f"{CHESS_COM_URL}/login", timeout=60000)
    time.sleep(4)
    dismiss_popups(page)
    _screenshot(page, "login_page_clean")

    # Click "Log in with Google" button
    google_clicked = False
    for selector in [
        'a:has-text("Log in with Google")',
        'a:has-text("Google")',
        'button:has-text("Google")',
        '[data-provider="google"]',
        'button:has-text("Войти через Google")',
    ]:
        try:
            el = page.locator(selector)
            if el.count() > 0:
                el.first.click(force=True, timeout=5000)
                google_clicked = True
                print(f"   ✅ Clicked Google login: {selector}")
                break
        except Exception:
            pass

    if not google_clicked:
        print("   ❌ Could not find Google login button")
        _screenshot(page, "no_google_btn")
        return False

    time.sleep(5)
    _screenshot(page, "google_oauth_page")

    # Google OAuth page — handle account chooser or email input
    try:
        # Check if account chooser is shown (Google already has session)
        account_item = page.locator(f'li:has-text("{EMAIL}")')
        if account_item.count() > 0:
            print(f"   📧 Account chooser found — selecting {EMAIL}")
            account_item.first.click(timeout=10000)
            time.sleep(5)
        else:
            # No account chooser — need to enter email
            print("   📧 Entering Google email...")
            email_input = page.locator('input[type="email"], #identifierId')
            email_input.wait_for(state='visible', timeout=15000)
            email_input.first.click()
            time.sleep(0.3)
            page.keyboard.type(EMAIL, delay=30)
            time.sleep(0.5)

            # Click Next
            for sel in ['#identifierNext', 'button:has-text("Next")', 'button:has-text("Далее")']:
                try:
                    btn = page.locator(sel)
                    if btn.count() > 0:
                        btn.first.click(timeout=5000)
                        print("   → Clicked Next")
                        break
                except Exception:
                    pass

            time.sleep(5)

            # Enter password if needed
            pw_input = page.locator('input[type="password"], input[name="Passwd"]')
            if pw_input.count() > 0:
                print("   🔑 Entering Google password...")
                pw_input.first.click()
                time.sleep(0.3)
                page.keyboard.type(PASSWORD, delay=30)
                time.sleep(0.5)

                for sel in ['#passwordNext', 'button:has-text("Next")', 'button:has-text("Далее")']:
                    try:
                        btn = page.locator(sel)
                        if btn.count() > 0:
                            btn.first.click(timeout=5000)
                            break
                    except Exception:
                        pass
                time.sleep(8)

    except Exception as e:
        print(f"   ⚠️  Google OAuth flow issue: {e}")
        _screenshot(page, "google_oauth_error")
        time.sleep(3)

    # Wait for redirect back to chess.com
    print("   ⏳ Waiting for redirect back to chess.com...")
    for _ in range(30):
        if 'chess.com' in page.url and '/login' not in page.url.lower():
            print("   ✅ Logged in via Google!")
            _screenshot(page, "after_google_login")
            return True
        time.sleep(2)

    _screenshot(page, "login_failed")
    print("   ❌ Login failed — check screenshot")
    return False


# ── Game Setup ──────────────────────────────────────────────

def navigate_to_minihouse(page):
    """Navigate directly to chess.com/variants/minihouse."""
    print("\n🎮 Navigating to minihouse variant...")

    page.goto(f"{CHESS_COM_URL}/variants/minihouse", timeout=60000)
    time.sleep(5)
    dismiss_popups(page)
    _screenshot(page, "variants_page")

    # Dump UI to understand the page
    print("   📋 Scanning page elements...")
    dump_ui(page)

    return True


def dump_ui(page):
    """Dump all visible interactive elements for debugging."""
    elements = page.evaluate("""() => {
        const els = document.querySelectorAll('button, a, input, textarea, select, [role="button"], [role="tab"], [role="option"], [role="listbox"]');
        return Array.from(els).slice(0, 150).map(el => ({
            tag: el.tagName,
            text: (el.textContent || '').trim().slice(0, 100),
            ariaLabel: el.getAttribute('aria-label') || '',
            placeholder: el.getAttribute('placeholder') || '',
            role: el.getAttribute('role') || '',
            type: el.getAttribute('type') || '',
            href: el.getAttribute('href') || '',
            className: (el.className || '').toString().slice(0, 80),
            id: el.id || '',
            visible: el.offsetParent !== null,
        }));
    }""")
    for el in elements:
        if el.get("visible") and (el.get("text") or el.get("ariaLabel")):
            txt = el['text'][:60]
            aria = el['ariaLabel'][:30]
            cls = el.get('className', '')[:40]
            print(f"     {el['tag']:10} id='{el.get('id','')}' '{txt}' aria='{aria}' class='{cls}'")
    return elements


def setup_game(page):
    """Set up a minihouse game: Casual, 30+30."""
    print("\n⚙️  Setting up minihouse game (Casual 30+30)...")
    
    # Look for the search/filter for variants
    search = page.locator('input[placeholder*="search" i], input[placeholder*="Search" i], input[type="search"]')
    if search.count() > 0:
        search.first.click()
        time.sleep(0.5)
        search.first.fill("minihouse")
        time.sleep(2)
        _screenshot(page, "search_minihouse")
    
    # Try to find and click minihouse option
    minihouse = page.locator('text=minihouse, text=Minihouse, text=Mini House')
    if minihouse.count() > 0:
        print(f"   Found minihouse option ({minihouse.count()} matches)")
        minihouse.first.click()
        time.sleep(2)
        _screenshot(page, "minihouse_selected")
    else:
        print("   ⚠️  'minihouse' not found directly, scanning page...")
        _screenshot(page, "no_minihouse")
    
    # Look for Customize button (NOT Play!)
    customize = page.locator('button:has-text("Customize"), button:has-text("Custom"), a:has-text("Customize")')
    if customize.count() > 0:
        print("   Clicking 'Customize'...")
        customize.first.click()
        time.sleep(2)
        _screenshot(page, "customize_page")
    
    # Set to Casual (unrated)
    rated_toggle = page.locator('[class*="rated" i], input[name*="rated" i], [data-cy*="rated" i]')
    casual_btn = page.locator('button:has-text("Casual"), label:has-text("Casual"), [data-cy*="casual" i]')
    
    if casual_btn.count() > 0:
        casual_btn.first.click()
        time.sleep(1)
        print("   ✅ Set to Casual")
    
    # Set time: 30 min + 30 sec
    # This depends on the UI - might be dropdowns or input fields
    time_input = page.locator('input[name*="time" i], input[aria-label*="time" i], select[name*="time" i]')
    increment_input = page.locator('input[name*="increment" i], input[aria-label*="increment" i]')
    
    _screenshot(page, "game_setup")
    
    # Try to create the game
    create_btn = page.locator('button:has-text("Create"), button:has-text("Play"), button[type="submit"]')
    if create_btn.count() > 0:
        print("   Found create/play button")
    
    return True


# ── Board Reading ───────────────────────────────────────────

def read_board_from_dom(page):
    """Read the current board position from chess.com variants DOM.
    
    Variants site uses:
    - .TheBoard-pieces > .piece with data-piece=K/R/N/B/P/Q, data-color=5/6/7
    - Position via CSS transform: translate(col*70px, row*70px) on 8x8 grid
    - Playable 6x6 area at grid positions (1,1)-(6,6), walls (x/7) at 0 and 7
    
    Returns a GameState populated with the current position, or None on failure.
    """
    board_data = page.evaluate("""() => {
        const piecesContainer = document.querySelector('.TheBoard-pieces');
        if (!piecesContainer) return null;
        
        const pieces = piecesContainer.querySelectorAll('.piece');
        const result = { boardPieces: [], bankPieces: [], squarePx: 70 };
        
        pieces.forEach(p => {
            const pieceType = p.dataset.piece;
            const color = p.dataset.color;
            const invisible = p.dataset.invisible !== undefined;
            
            // Skip wall pieces and invisible
            if (pieceType === 'x' || color === '7' || invisible) return;
            // Skip promotion selector pieces
            if (p.parentElement && p.parentElement.className.includes('promotion')) return;
            // Skip non-game colors
            if (color !== '5' && color !== '6') return;
            
            // Parse transform: translate(Xpx, Ypx) with optional scale
            const style = p.getAttribute('style') || '';
            const m = style.match(/translate\\((-?[\\d.]+)px,\\s*(-?[\\d.]+)px\\)/);
            if (!m) return;
            
            const px = parseFloat(m[1]);
            const py = parseFloat(m[2]);
            const hasScale = style.includes('scale(');
            
            // Bank pieces have negative X coordinates and scale
            if (px < 0 || hasScale) {
                result.bankPieces.push({piece: pieceType, color: color, py: py});
            } else {
                result.boardPieces.push({piece: pieceType, color: color, px: Math.round(px), py: Math.round(py)});
            }
        });
        
        // Get square size from first square element
        const sq = document.querySelector('.TheBoard-squares .square');
        if (sq) {
            const r = sq.getBoundingClientRect();
            result.squarePx = Math.round(r.width);
        }
        
        return result;
    }""")
    
    if not board_data:
        print("   ❌ Could not read board from DOM")
        return None
    
    sq_px = board_data.get('squarePx', 70)
    flipped = is_board_flipped(page)
    board_mid_y = sq_px * 4  # midpoint of 8x8 grid = 280px
    
    # Build a GameState from the board data
    gs = GameState()
    gs.board = [[EMPTY_SQUARE for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    gs.hands = {'w': {}, 'b': {}}
    for p_upper in "PNBRQ":
        gs.hands['w'][p_upper] = 0
        gs.hands['b'][p_upper] = 0
    gs.king_pos = {'w': None, 'b': None}
    
    # Place board pieces
    for p_info in board_data['boardPieces']:
        grid_col = p_info['px'] // sq_px
        grid_row = p_info['py'] // sq_px
        
        # Skip if outside playable area
        if grid_col < GRID_OFFSET or grid_col > BOARD_SIZE or grid_row < GRID_OFFSET or grid_row > BOARD_SIZE:
            continue
        
        internal_row, internal_col = grid_to_internal(grid_col, grid_row, flipped)
        
        if not (0 <= internal_row < BOARD_SIZE and 0 <= internal_col < BOARD_SIZE):
            continue
        
        piece_key = (p_info['piece'], p_info['color'])
        piece_char = VARIANTS_PIECE_MAP.get(piece_key)
        if not piece_char:
            continue
        
        gs.board[internal_row][internal_col] = piece_char
        if piece_char == 'K':
            gs.king_pos['w'] = (internal_row, internal_col)
        elif piece_char == 'k':
            gs.king_pos['b'] = (internal_row, internal_col)
    
    # Parse bank/pocket pieces (negative X, scaled down)
    for bp in board_data['bankPieces']:
        piece_upper = bp['piece'].upper()
        if piece_upper not in "PNBRQ":
            continue
        # Determine color: Y > midpoint = bottom bank, Y < midpoint = top bank
        # If not flipped: bottom = white (5), top = black (6) — confirmed by data-color
        if bp['color'] == '5':
            hand_color = 'w'
        else:
            hand_color = 'b'
        gs.hands[hand_color][piece_upper] = gs.hands[hand_color].get(piece_upper, 0) + 1
    
    piece_count = sum(1 for row in gs.board for cell in row if cell != EMPTY_SQUARE)
    w_hand = {k: v for k, v in gs.hands['w'].items() if v > 0}
    b_hand = {k: v for k, v in gs.hands['b'].items() if v > 0}
    hand_str = ""
    if w_hand:
        hand_str += f" W-hand:{w_hand}"
    if b_hand:
        hand_str += f" B-hand:{b_hand}"
    print(f"   📋 Board: {piece_count} pieces, flipped={flipped}{hand_str}")
    
    return gs


def is_board_flipped(page):
    """Check if we're playing black (board flipped).
    
    Uses clock brightness to determine whose turn it is, combined with
    move count parity. If our (bottom) clock is active and plies is even
    (white's turn), we're white (not flipped). If our clock is active and
    plies is odd (black's turn), we're black (flipped).
    """
    result = page.evaluate("""() => {
        const bottomClock = document.querySelector('.playerbox-bottom .clock-component');
        const topClock = document.querySelector('.playerbox-top .clock-component');
        if (!bottomClock || !topClock) return null;
        
        const bottomStyle = bottomClock.getAttribute('style') || '';
        const topStyle = topClock.getAttribute('style') || '';
        
        // brightness(100%) = active clock, brightness(70%) = inactive
        const bottomActive = bottomStyle.includes('100%');
        const topActive = topStyle.includes('100%');
        
        // Count plies
        const moves = document.querySelectorAll('.moves-table-cell.moves-move .moves-pointer');
        const plies = Array.from(moves).map(m => m.innerText.trim()).filter(t => t.length > 0).length;
        
        // Even plies = white's turn, odd = black's turn
        const whitesTurn = (plies % 2 === 0);
        
        return { bottomActive, topActive, plies, whitesTurn };
    }""")
    
    if not result:
        return False
    
    # If bottom clock active and it's white's turn → we are white (not flipped)
    # If bottom clock active and it's black's turn → we are black (flipped)
    if result['bottomActive']:
        return not result['whitesTurn']  # flipped if it's black's turn
    elif result['topActive']:
        return result['whitesTurn']  # flipped if it's white's turn (opponent is white)
    
    # Fallback: both same brightness — assume not flipped
    return False


def detect_our_color(page):
    """Detect which color we are playing."""
    if is_board_flipped(page):
        print("   ♟️ We are playing BLACK")
        return 'b'
    else:
        print("   ♙ We are playing WHITE")
        return 'w'


def get_dom_move_count(page):
    """Get the number of half-moves (plies) from the move list DOM."""
    return page.evaluate("""() => {
        const moves = document.querySelectorAll('.moves-table-cell.moves-move .moves-pointer');
        const texts = Array.from(moves).map(m => m.innerText.trim()).filter(t => t.length > 0);
        return texts.length;
    }""")


def detect_turn(page):
    """Detect whose turn it is from move count."""
    mc = get_dom_move_count(page)
    # Even move count = white's turn, odd = black's turn
    return 'w' if (mc % 2 == 0) else 'b'


def is_game_active(page):
    """Check if a game is currently in progress on the variants site."""
    return page.evaluate("""() => {
        // Check for game-over buttons (Play, Rematch, Exit, New Game)
        const btns = document.querySelectorAll('button');
        for (const b of btns) {
            const t = (b.innerText || '').trim().toLowerCase();
            if ((t === 'rematch' || t === 'exit' || t === 'new game' || t === 'play again') && b.offsetParent !== null) return false;
        }
        
        // Check for game-result overlay or banner (e.g. "You Won", "Draw", etc.)
        const resultEls = document.querySelectorAll('.game-result, .game-over-header, [class*=gameResult], [class*=game-result], [class*=GameOver]');
        if (resultEls.length > 0) {
            for (const el of resultEls) {
                if (el.offsetParent !== null || el.offsetHeight > 0) return false;
            }
        }
        
        // Check for result text in common containers
        const allText = document.body.innerText || '';
        const resultPatterns = ['wins by checkmate', 'wins by resignation', 'drawn by', 'game over', 'won the game'];
        for (const pat of resultPatterns) {
            // Only match if it's in a visible overlay/modal, not in move history
            const modals = document.querySelectorAll('.modal-content, .game-over, [class*=modal], [class*=overlay]');
            for (const m of modals) {
                if (m.offsetParent !== null && (m.innerText || '').toLowerCase().includes(pat)) return false;
            }
        }
        
        // Must have pieces on the board (non-wall)
        const pieces = document.querySelectorAll('.TheBoard-pieces > .piece');
        let realPieces = 0;
        pieces.forEach(p => {
            if (p.dataset.piece !== 'x' && p.dataset.color !== '7' && p.dataset.invisible === undefined) {
                realPieces++;
            }
        });
        if (realPieces === 0) return false;
        
        // Check for clocks (means game in progress)
        const clocks = document.querySelectorAll('.clock-component');
        if (clocks.length < 2) return false;
        
        // URL can be /game/ or /variants/ with active board — just need pieces + clocks
        return true;
    }""")


def is_our_turn(page, our_color):
    """Check if it's our turn to move."""
    current_turn = detect_turn(page)
    return current_turn == our_color


# ── Move Making ─────────────────────────────────────────────

def make_move_on_board(page, move, our_color):
    """Make a move on the chess.com variants board by clicking pixel coordinates.
    
    The variants board uses .TheBoard-layers as the click target.
    Each square is dynamically sized. We translate internal coords → grid coords → pixel coords.
    """
    if move[0] == 'drop':
        return make_drop_on_board(page, move, our_color)
    
    (from_row, from_col), (to_row, to_col), promotion = move
    flipped = is_board_flipped(page)
    
    from_grid_col, from_grid_row = internal_to_grid(from_row, from_col, flipped)
    to_grid_col, to_grid_row = internal_to_grid(to_row, to_col, flipped)
    
    from_alg = coords_to_algebraic(from_row, from_col)
    to_alg = coords_to_algebraic(to_row, to_col)
    print(f"   🎯 Moving {from_alg} → {to_alg} (grid {from_grid_col},{from_grid_row} → {to_grid_col},{to_grid_row})")
    
    # Click source square (center of the grid cell)
    click_grid_square(page, from_grid_col, from_grid_row)
    time.sleep(0.4)
    
    # Click destination square
    click_grid_square(page, to_grid_col, to_grid_row)
    time.sleep(0.5)
    
    # Handle promotion if needed
    if promotion:
        handle_promotion(page, promotion, to_grid_col, to_grid_row)
    
    _screenshot(page, "after_move")
    print(f"   ✅ Move made: {format_move_for_print(move)}")
    return True


def make_drop_on_board(page, move, our_color):
    """Make a drop move (crazyhouse) by mouse-clicking a bank piece then the target square.
    
    Bank pieces are .piece elements with scale() transform. We find their bounding rect
    and click with page.mouse.click() — JS events don't work for chess.com's board.
    """
    _, piece_code, (to_row, to_col) = move
    flipped = is_board_flipped(page)
    to_grid_col, to_grid_row = internal_to_grid(to_row, to_col, flipped)
    
    to_alg = coords_to_algebraic(to_row, to_col)
    print(f"   🎯 Dropping {piece_code} → {to_alg} (grid {to_grid_col},{to_grid_row})")
    
    our_color_code = '5' if our_color == 'w' else '6'
    piece_type_upper = piece_code[-1].upper()  # 'wR' -> 'R', 'bN' -> 'N'
    
    # Find bank piece bounding rect via JS
    bank_rect = page.evaluate("""(args) => {
        const [pieceType, colorCode] = args;
        const pieces = document.querySelectorAll('.TheBoard-pieces > .piece');
        for (const p of pieces) {
            if (p.dataset.piece === pieceType && p.dataset.color === colorCode) {
                const style = p.getAttribute('style') || '';
                if (style.includes('scale(')) {
                    const r = p.getBoundingClientRect();
                    return {x: r.x, y: r.y, w: r.width, h: r.height};
                }
            }
        }
        return null;
    }""", [piece_type_upper, our_color_code])
    
    if not bank_rect:
        print(f"   ❌ Could not find bank piece {piece_type_upper} (color {our_color_code})")
        return False
    
    # Click center of bank piece with real mouse
    bx = bank_rect['x'] + bank_rect['w'] / 2
    by = bank_rect['y'] + bank_rect['h'] / 2
    print(f"   🖱️  Clicking bank piece at ({bx:.0f}, {by:.0f})")
    page.mouse.click(bx, by)
    time.sleep(0.5)
    
    # Now click the target square on the board
    click_grid_square(page, to_grid_col, to_grid_row)
    time.sleep(0.5)
    
    _screenshot(page, "after_drop")
    print(f"   ✅ Drop made: {piece_code}@{to_alg}")
    return True


def click_grid_square(page, grid_col, grid_row):
    """Click the center of a grid square on the variants board.
    
    The board is .TheBoard-layers (8x8 grid). Square size is computed
    dynamically from actual board dimensions to handle any window size.
    """
    board_rect = page.evaluate("""() => {
        const board = document.querySelector('.TheBoard-layers');
        if (!board) return null;
        const r = board.getBoundingClientRect();
        return {left: r.left, top: r.top, width: r.width, height: r.height};
    }""")
    
    if not board_rect:
        print("   ❌ Could not find .TheBoard-layers")
        return
    
    # Dynamic square size from actual board dimensions
    sq = board_rect['width'] / 8.0
    
    # Calculate pixel position relative to viewport
    px_x = board_rect['left'] + grid_col * sq + sq / 2
    px_y = board_rect['top'] + grid_row * sq + sq / 2
    
    page.mouse.click(px_x, px_y)


def handle_promotion(page, promotion_piece, to_grid_col, to_grid_row):
    """Handle pawn promotion dialog by clicking the correct piece in the selector.
    
    Chess.com variants minihouse promotion layout (observed):
    When promoting at TOP of visual board (grid_row near 1):
      [B] [R]    ← B on destination square, R one square to the right
      [N]        ← N one square below
    When promoting at BOTTOM of visual board (grid_row near 6):
      [N]        ← N one square above
      [B] [R]    ← B on destination square, R one square to the right
    """
    time.sleep(0.8)
    piece_letter = promotion_piece.upper()
    
    if piece_letter == 'R':
        click_col = to_grid_col + 1
        click_row = to_grid_row
    elif piece_letter == 'N':
        click_col = to_grid_col
        # N is toward center from destination
        if to_grid_row <= 3:
            click_row = to_grid_row + 1
        else:
            click_row = to_grid_row - 1
    else:
        # B (bishop) or anything else: click on the destination square itself
        click_col = to_grid_col
        click_row = to_grid_row
    
    print(f"   👑 Promotion: selecting {piece_letter} at grid ({click_col},{click_row}) [dest was ({to_grid_col},{to_grid_row})]")
    click_grid_square(page, click_col, click_row)
    time.sleep(0.5)
    print(f"   ✅ Promoted to {piece_letter}")


# ── AI Decision ─────────────────────────────────────────────


def _would_create_move_cycle(our_move_history, candidate_move):
    """Check if playing candidate_move would create a repeated cycle of OUR moves.
    
    Detects repeating sequences of length 1-5, e.g.:
      - length 1: A, A  (same move twice in a row)
      - length 2: A, B, A, B
      - length 3: A, B, C, A, B, C
    Returns (True, cycle_len) if a cycle would form, else (False, 0).
    """
    if not our_move_history:
        return False, 0
    extended = [repr(m) for m in our_move_history] + [repr(candidate_move)]
    for k in range(1, 6):
        if len(extended) < 2 * k:
            continue
        if extended[-k:] == extended[-2 * k:-k]:
            return True, k
    return False, 0


def get_ai_move(gamestate, our_color, our_move_history=None):
    """Get the best move from cache or AI engine, avoiding move cycles."""
    gamestate.current_turn = our_color
    gamestate._all_legal_moves_cache = None
    
    legal_moves = gamestate.get_all_legal_moves()
    if not legal_moves:
        print("   ❌ No legal moves!")
        return None
    
    print(f"   🧠 {len(legal_moves)} legal moves available")
    
    pos_hash = get_position_hash(gamestate)
    print(f"   🔑 Position hash: {pos_hash[:16]}...")
    
    if our_move_history is None:
        our_move_history = []
    
    def _would_cycle(move):
        """Check if this move would create a cycle in our recent move sequence."""
        would, k = _would_create_move_cycle(our_move_history, move)
        if would:
            print(f"   🔄 Move {format_move_for_print(move)} would create cycle of length {k} — avoiding")
        return would
    
    # Try cache first
    for depth in [6, 5, 4, 3]:
        cache_key = (pos_hash, depth)
        cached = ai_module.move_cache.get(cache_key)
        if cached:
            try:
                best_move = eval(cached)
                if best_move in legal_moves:
                    if _would_cycle(best_move):
                        print(f"   🔄 CACHE HIT depth {depth}: {format_move_for_print(best_move)} — SKIPPED (cycle)")
                        continue
                    print(f"   ✅ CACHE HIT at depth {depth}: {format_move_for_print(best_move)}")
                    return best_move
            except Exception:
                pass
    
    print("   📊 No cache hit, running AI search...")
    try:
        best_move = find_best_move(gamestate, depth=6, time_limit=45)
        if best_move:
            if _would_cycle(best_move):
                print(f"   🔄 AI move {format_move_for_print(best_move)} creates cycle, finding alternative...")
                try:
                    top_moves = find_best_move(gamestate, depth=4, return_top_n=5, time_limit=15)
                    if isinstance(top_moves, list):
                        for alt_move, alt_score in top_moves:
                            if not _would_create_move_cycle(our_move_history, alt_move)[0]:
                                print(f"   🤖 AI alternative: {format_move_for_print(alt_move)} (score: {alt_score:.0f})")
                                return alt_move
                except Exception:
                    pass
                # Pick any legal move that doesn't create a cycle
                for m in legal_moves:
                    if not _would_create_move_cycle(our_move_history, m)[0]:
                        print(f"   🎯 Fallback non-cycling: {format_move_for_print(m)}")
                        return m
                print(f"   ⚠️  All moves create cycles, playing AI choice anyway")
            print(f"   🤖 AI move: {format_move_for_print(best_move)}")
            return best_move
    except Exception as e:
        print(f"   ⚠️  AI error: {e}")
    
    # Fallback: random legal move
    move = random.choice(legal_moves)
    print(f"   🎲 Random fallback: {format_move_for_print(move)}")
    return move


# ── Game Loop ───────────────────────────────────────────────

def wait_for_game_start(page, timeout=600):
    """Wait until a game starts on the board."""
    print("\n⏳ Waiting for game to start...")
    start = time.time()
    
    while time.time() - start < timeout:
        # Check if game is active by pieces + clocks (no URL dependency)
        if is_game_active(page):
            print("   ✅ Game detected!")
            time.sleep(2)
            return True
        time.sleep(3)
        elapsed = int(time.time() - start)
        if elapsed % 30 == 0:
            print(f"   ⏳ Waiting... ({elapsed}s)")
    
    print("   ❌ Timeout waiting for game")
    return False


def dismiss_game_over(page):
    """Close the game-over screen and navigate to minihouse lobby."""
    print("   🔄 Dismissing game-over...")
    time.sleep(2)
    
    # Navigate directly to minihouse lobby — cleanest approach
    try:
        navigate_to_minihouse(page)
        print("   ✅ Back to minihouse lobby")
        return True
    except Exception as e:
        print(f"   ⚠️  Navigation failed: {e}")
    
    # Fallback: click Exit button
    for selector in [
        'button:has-text("Exit")',
        'button:has-text("Play")',
    ]:
        try:
            el = page.locator(selector)
            if el.count() > 0:
                el.first.click(force=True, timeout=3000)
                print(f"   ✅ Clicked: {selector}")
                time.sleep(2)
                return True
        except Exception:
            pass
    
    return False


def play_game(page):
    """Main game loop — read board, decide move, play it."""
    our_color = detect_our_color(page)
    moves_made = 0
    our_move_history = []   # list of our moves in order, for cycle detection
    
    print(f"\n{'═' * 50}")
    print(f"♟️  GAME STARTED! We are {'WHITE ♙' if our_color == 'w' else 'BLACK ♟'}")
    print(f"{'═' * 50}")
    _screenshot(page, "game_start")
    
    while True:
        # Check if game is still active
        if not is_game_active(page):
            break
        
        # Get move count from DOM and determine whose turn
        dom_moves = get_dom_move_count(page)
        current_turn = 'w' if (dom_moves % 2 == 0) else 'b'
        
        if current_turn != our_color:
            time.sleep(0.5)
            continue
        
        # Read the board
        gs = read_board_from_dom(page)
        if not gs:
            time.sleep(2)
            continue
        
        gs.current_turn = our_color
        
        print(f"\n{'─' * 40}")
        print(f"📍 Move #{moves_made + 1} ({'WHITE' if our_color == 'w' else 'BLACK'}) [DOM plies: {dom_moves}]")
        print_board(gs)
        
        # Get AI move
        best_move = get_ai_move(gs, our_color, our_move_history=our_move_history)
        if not best_move:
            print("   ❌ No move found!")
            time.sleep(2)
            continue
        
        # Re-check game state after AI computation (game may have ended while thinking)
        if not is_game_active(page):
            print("   ⚠️  Game ended while computing, breaking...")
            break
        
        # Add human-like delay before making the move
        think_delay = random.uniform(1.0, 2.5)
        print(f"   ⏱️  Waiting {think_delay:.1f}s...")
        time.sleep(think_delay)
        
        # Make the move
        success = make_move_on_board(page, best_move, our_color)
        if not success:
            print("   ❌ Move click failed, retrying...")
            time.sleep(1)
            continue
        
        # Wait for our move to register in DOM (move count should increase)
        move_registered = False
        for _ in range(20):  # up to 10 seconds
            time.sleep(0.5)
            new_dom_moves = get_dom_move_count(page)
            if new_dom_moves > dom_moves:
                move_registered = True
                print(f"   ✅ Move registered (plies: {dom_moves} → {new_dom_moves})")
                break
            # Also check if game ended
            if not is_game_active(page):
                move_registered = True
                break
        
        if not move_registered:
            print(f"   ⚠️  Move may not have registered (plies still {dom_moves}), retrying...")
            # Click an empty area to deselect, then retry
            try:
                click_grid_square(page, 4, 4)
                time.sleep(0.3)
            except Exception:
                pass
            continue
        
        moves_made += 1
        
        # Record played move for cycle detection
        our_move_history.append(best_move)
        
        # Wait for opponent's move (or game end)
        print(f"   ⏳ Waiting for opponent...")
        for _ in range(3600):  # up to 30 min
            time.sleep(1)
            if not is_game_active(page):
                break
            opp_moves = get_dom_move_count(page)
            opp_turn = 'w' if (opp_moves % 2 == 0) else 'b'
            if opp_turn == our_color:
                print(f"   ♟️  Opponent moved (plies: {opp_moves})")
                break
    
    # Detect game result from DOM
    result_text = "unknown"
    try:
        result_text = page.evaluate("""() => {
            // Look for result text in common chess.com elements
            const selectors = [
                '.game-result', '.game-over-header-component',
                '[class*=gameResult]', '[class*=game-result]',
                '[class*=GameOver]', '.modal-game-over-header-component',
                '.game-over-header-title-component'
            ];
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (el && el.textContent.trim()) return el.textContent.trim();
            }
            // Broader search for result patterns
            const all = document.body.innerText;
            const patterns = ['won', 'lost', 'draw', 'checkmate', 'resign', 'timeout', 'stalemate', 'aborted'];
            for (const p of patterns) {
                const idx = all.toLowerCase().indexOf(p);
                if (idx >= 0) return all.substring(Math.max(0, idx - 30), idx + 40).trim();
            }
            return 'unknown';
        }""")
    except Exception:
        pass
    
    print(f"\n{'═' * 50}")
    print(f"🏁 Game over after {moves_made} moves! Result: {result_text}")
    print(f"{'═' * 50}")
    _screenshot(page, "game_over")
    
    # Save accumulated cache to local DB
    try:
        cache = ai_module.move_cache
        before = len(cache)
        ai_module.save_move_cache_to_db(cache)
        print(f"   💾 Saved {before} cache entries to move_cache.db")
    except Exception as e:
        print(f"   ⚠️  Cache save failed: {e}")
    
    # Dismiss game-over modal if present
    time.sleep(2)
    dismiss_game_over(page)


def print_board(gs):
    """Print the board state to console."""
    print("     a b c d e f")
    for row in range(BOARD_SIZE):
        rank = BOARD_SIZE - row
        pieces = ' '.join(gs.board[row])
        print(f"  {rank}  {pieces}")
    
    w_hand = {k: v for k, v in gs.hands['w'].items() if v > 0}
    b_hand = {k: v for k, v in gs.hands['b'].items() if v > 0}
    if w_hand:
        print(f"  White hand: {w_hand}")
    if b_hand:
        print(f"  Black hand: {b_hand}")


# ── Main ────────────────────────────────────────────────────

def create_minihouse_game(page, rated=False):
    """Navigate to minihouse page → set time 30+30 → Casual/Rated → Play!
    
    The 4P&Variants site at chess.com/variants/minihouse has these elements
    (all with class ui_v5-*):
    - Time button showing current time (e.g. "3 min" or "30 | 30")
    - Click it → dropdown with presets + "More" button
    - Click "More" → SELECT for Initial Time + SELECT for Increment
    - input#isRatedToggle checkbox (label[for="isRatedToggle"])
    - "Play!" button to start seeking
    
    DO NOT click "Custom Challenge" — that opens a different UI (main chess.com).
    """
    mode_str = "Rated" if rated else "Casual"
    print(f"\n🎮 Creating minihouse game ({mode_str} 30+30)...")

    # Step 1: Navigate to minihouse page
    page.goto(f"{CHESS_COM_URL}/variants/minihouse", timeout=60000)
    time.sleep(5)
    dismiss_popups(page)
    _screenshot(page, "01_minihouse_page")

    # Step 2: Set Rated/Casual toggle
    want_rated = rated
    print(f"   🏷️  Setting to {'Rated' if want_rated else 'Casual (unrated)'}...")
    try:
        is_rated = page.evaluate("() => { const el = document.getElementById('isRatedToggle'); return el ? el.checked : null; }")
        print(f"   📋 isRatedToggle checked = {is_rated}")

        if is_rated != want_rated and is_rated is not None:
            label = page.locator('label[for="isRatedToggle"]')
            if label.count() > 0:
                label.first.click()
                time.sleep(1)
                is_rated_after = page.evaluate("() => document.getElementById('isRatedToggle').checked")
                if is_rated_after == want_rated:
                    print(f"   ✅ Toggled to {'Rated' if want_rated else 'Casual'}")
                else:
                    page.evaluate(f"""() => {{ 
                        const el = document.getElementById('isRatedToggle'); 
                        el.checked = {'true' if want_rated else 'false'}; 
                        el.dispatchEvent(new Event('change', {{bubbles: true}}));
                    }}""")
                    time.sleep(0.5)
                    print(f"   ✅ Force-set to {'Rated' if want_rated else 'Casual'} via JS")
            else:
                page.evaluate(f"""() => {{ 
                    const el = document.getElementById('isRatedToggle'); 
                    el.checked = {'true' if want_rated else 'false'}; 
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                }}""")
                time.sleep(0.5)
                print(f"   ✅ Force-set via JS (no label)")
        elif is_rated == want_rated:
            print(f"   ✅ Already set to {'Rated' if want_rated else 'Casual'}")
        else:
            print("   ⚠️  isRatedToggle not found on page")
    except Exception as e:
        print(f"   ⚠️  Rated toggle: {e}")

    _screenshot(page, "02_casual")

    # Step 3: Check if time is already 30|30
    current_time_btn = page.locator('button.ui_v5-button-component:has-text("|"), button.ui_v5-button-component:has-text("min"), button.ui_v5-button-component:has-text("sec")')
    current_time_text = ""
    if current_time_btn.count() > 0:
        current_time_text = current_time_btn.first.inner_text().strip()
    print(f"   ⏱️  Current time control: '{current_time_text}'")

    if current_time_text == "30 | 30":
        print("   ✅ Time already set to 30+30")
    else:
        # Step 4: Click time button to open dropdown
        print("   ⏱️  Setting time control to 30+30...")
        if current_time_btn.count() > 0:
            current_time_btn.first.click()
            time.sleep(1)

            # Step 5: Click "More" button for custom time
            more_btn = page.locator('button.ui_v5-button-component:has-text("More")')
            if more_btn.count() > 0:
                more_btn.first.click()
                time.sleep(1)
                print("   ✅ Expanded 'More' time options")

            # Step 6: Set Initial Time via JS (most reliable)
            page.evaluate("""() => {
                const selects = document.querySelectorAll('select.ui_v5-select-component');
                for (const sel of selects) {
                    const opts = Array.from(sel.options);
                    const opt30min = opts.find(o => o.text.trim() === '30 min');
                    if (opt30min) {
                        sel.value = opt30min.value;
                        sel.dispatchEvent(new Event('change', {bubbles: true}));
                        return true;
                    }
                }
                return false;
            }""")
            time.sleep(0.5)
            print("   ✅ Set Initial Time to 30 min via JS")

            # Step 7: Set Increment via JS
            page.evaluate("""() => {
                const selects = document.querySelectorAll('select.ui_v5-select-component');
                for (const sel of selects) {
                    const opts = Array.from(sel.options);
                    const opt30sec = opts.find(o => o.text.trim() === '30 sec');
                    if (opt30sec) {
                        sel.value = opt30sec.value;
                        sel.dispatchEvent(new Event('change', {bubbles: true}));
                        return true;
                    }
                }
                return false;
            }""")
            time.sleep(0.5)
            print("   ✅ Set Increment to 30 sec via JS")
        else:
            print("   ⚠️  Time button not found")

    _screenshot(page, "03_time_set")

    # Step 8: Verify rated/casual is correct (setting time may have reset it)
    is_rated_final = page.evaluate("() => { const el = document.getElementById('isRatedToggle'); return el ? el.checked : null; }")
    if is_rated_final != want_rated and is_rated_final is not None:
        print(f"   ⚠️  Toggle got reset! Fixing to {'Rated' if want_rated else 'Casual'}...")
        label = page.locator('label[for="isRatedToggle"]')
        if label.count() > 0:
            label.first.click()
            time.sleep(1)
        is_rated_check = page.evaluate("() => document.getElementById('isRatedToggle').checked")
        if is_rated_check != want_rated:
            page.evaluate(f"""() => {{ 
                const el = document.getElementById('isRatedToggle'); 
                el.checked = {'true' if want_rated else 'false'}; 
                el.dispatchEvent(new Event('change', {{bubbles: true}}));
            }}""")
        print(f"   📋 Final rated state: {page.evaluate('() => document.getElementById(\"isRatedToggle\").checked')}")

    _screenshot(page, "04_final_check")

    # Step 9: Click "Play!" to start seeking
    print("   🚀 Starting game search...")
    try:
        play_btn = page.locator('button.ui_v5-button-component:has-text("Play!")')
        if play_btn.count() > 0:
            play_btn.first.click()
            time.sleep(3)
            print("   ✅ Clicked Play! — waiting for opponent...")
        else:
            for sel in ['button:has-text("Play!")', 'button.ui_v5-button-primary']:
                el = page.locator(sel)
                if el.count() > 0:
                    el.first.click()
                    time.sleep(3)
                    print(f"   ✅ Clicked via: {sel}")
                    break
    except Exception as e:
        print(f"   ⚠️  Play button click: {e}")

    _screenshot(page, "05_seeking")
    print("   ✅ Game creation flow complete")
    return True


def auto_loop(page):
    """Infinite loop: create game → wait → play → repeat."""
    game_num = 0

    while True:
        game_num += 1
        print(f"\n{'╔' + '═' * 48 + '╗'}")
        print(f"║  GAME #{game_num:03d}                                        ║")
        print(f"{'╚' + '═' * 48 + '╝'}")

        # If we're still on a game page, navigate to minihouse lobby
        current_url = page.url or ''
        if '/game/' in current_url:
            print("   📍 Still on game page, navigating to lobby...")
            try:
                navigate_to_minihouse(page)
            except Exception as e:
                print(f"   ⚠️  Navigation error: {e}")
                time.sleep(5)
                continue

        # Create game
        if not create_minihouse_game(page, rated=False):
            print("   ❌ Failed to create game. Retrying in 30s...")
            time.sleep(30)
            continue

        # Wait for opponent
        if not wait_for_game_start(page, timeout=600):
            print("   ❌ No opponent found. Retrying...")
            continue

        # Play the game
        play_game(page)

        # Check for stop flag
        stop_flag = Path(__file__).parent / ".stop_after_game"
        if stop_flag.exists():
            print("\n🛑 Stop flag detected! Stopping auto-loop.")
            stop_flag.unlink()
            return

        # Small pause before next game
        print("\n   ⏳ Waiting 5s before next game...")
        time.sleep(5)


def run_auto_session():
    """Single auto-session: connect → detect state → play. Returns on crash."""
    print("\n📦 Loading move cache...")
    setup_db()
    load_move_cache_from_db()
    print(f"   Cache size: {len(ai_module.move_cache)} entries")

    print("\n🌐 Launching Chrome...")
    chrome_proc, cdp_port = get_or_launch_chrome(PROFILE_DIR)

    with sync_playwright() as pw:
        browser = connect_cdp(pw, cdp_port)
        if not browser:
            raise RuntimeError("CDP connection failed")

        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        setup_stealth(ctx, page)

        # Ensure page is on chess.com (not about:blank)
        if not page.url or 'chess.com' not in page.url:
            page.goto("https://www.chess.com/variants/minihouse", wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)

        # Login (without navigating away from game)
        if not login_chess_com(page):
            print("⚠️  Login check inconclusive, continuing anyway...")

        # Detect current state
        current_url = page.url or ''
        in_game = '/game/' in current_url
        if not in_game:
            try:
                in_game = is_game_active(page)
            except Exception:
                pass

        if in_game:
            print(f"\n🔄 RESUMING game: {current_url}")
            play_game(page)
            print("\n   ⏳ Game finished, waiting 5s before next...")
            time.sleep(5)
        else:
            print(f"\n🆕 No active game. URL: {current_url}")

        # After game (or no game) → auto-loop
        auto_loop(page)


def main():
    """Entry point — supports --auto for fully autonomous mode."""
    import sys
    auto_mode = '--auto' in sys.argv

    print("╔══════════════════════════════════════════════╗")
    print("║   MiniChess Bot — chess.com/minihouse        ║")
    if auto_mode:
        print("║   Mode: FULL AUTO (with auto-restart)        ║")
    else:
        print("║   Mode: Interactive CLI                       ║")
    print("╚══════════════════════════════════════════════╝")

    if auto_mode:
        # Fully autonomous with auto-restart
        restart_count = 0
        while True:
            restart_count += 1
            try:
                print(f"\n{'🔄' if restart_count > 1 else '🚀'} Session #{restart_count}")
                run_auto_session()
            except KeyboardInterrupt:
                print("\n⏹️  Stopped by user")
                break
            except Exception as e:
                print(f"\n💥 CRASH: {e}")
                import traceback
                traceback.print_exc()
                wait = min(10 * restart_count, 60)
                print(f"   🔄 Auto-restart in {wait}s...")
                try:
                    time.sleep(wait)
                except KeyboardInterrupt:
                    print("\n⏹️  Stopped by user")
                    break
        return

    # --- Interactive CLI mode (original) ---
    print("\n📦 Loading move cache...")
    setup_db()
    load_move_cache_from_db()
    print(f"   Cache size: {len(ai_module.move_cache)} entries")

    print("\n🌐 Launching Chrome...")
    chrome_proc, cdp_port = get_or_launch_chrome(PROFILE_DIR)

    try:
        with sync_playwright() as pw:
            browser = connect_cdp(pw, cdp_port)
            if not browser:
                print("❌ CDP connection failed")
                return

            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            setup_stealth(ctx, page)

            if not login_chess_com(page):
                print("⚠️  Auto-login failed. Browser is open — log in manually.")
                input("   Press Enter when you've logged in manually...")

            print("\n🚀 Starting...")
            print("   Press Ctrl+C to stop.\n")

            current_url = page.url
            in_game = '/game/' in current_url
            if not in_game:
                try:
                    in_game = is_game_active(page)
                except Exception:
                    pass
            
            if in_game:
                print(f"   🎮 Already in a game: {current_url}")
                print("   Use 'play' to start auto-play, or 'read' to check board\n")
            else:
                try:
                    navigate_to_minihouse(page)
                except Exception as e:
                    print(f"   ⚠️  Navigation failed: {e}")

            print()
            print("Commands:")
            print("  'go'       - Start full auto-loop")
            print("  'play'     - Wait for game then auto-play")
            print("  'read'     - Read board state")
            print("  'screen'   - Take screenshot")
            print("  'dump'     - Dump page UI elements")
            print("  'url'      - Show current URL")
            print("  'nav'      - Navigate to minihouse")
            print("  'create'   - Create a game")
            print("  'quit'     - Exit")
            print()

            while True:
                try:
                    raw_cmd = input("🤖 > ").strip()
                    cmd = raw_cmd.lower()
                except (EOFError, KeyboardInterrupt):
                    break

                if cmd in ('quit', 'q'):
                    break
                elif cmd == 'go':
                    auto_loop(page)
                elif cmd == 'play':
                    if wait_for_game_start(page, timeout=600):
                        play_game(page)
                elif cmd == 'read':
                    gs = read_board_from_dom(page)
                    if gs:
                        print_board(gs)
                    else:
                        print("   No board detected")
                elif cmd == 'dump':
                    dump_ui(page)
                elif cmd == 'screen':
                    _screenshot(page, f"manual_{int(time.time())}")
                elif cmd == 'url':
                    print(f"   {page.url}")
                elif cmd == 'nav':
                    navigate_to_minihouse(page)
                elif cmd == 'create':
                    create_minihouse_game(page)
                elif cmd.startswith('goto '):
                    url = raw_cmd[5:].strip()
                    if not url.startswith('http'):
                        url = f"{CHESS_COM_URL}/{url}"
                    page.goto(url, timeout=60000)
                    time.sleep(3)
                    _screenshot(page, f"goto_{int(time.time())}")
                    print(f"   → {page.url}")
                elif cmd.startswith('click '):
                    sel = raw_cmd[6:].strip()
                    el = page.locator(sel)
                    print(f"   Found {el.count()} matches")
                    if el.count() > 0:
                        el.first.click(timeout=5000)
                        time.sleep(2)
                        _screenshot(page, f"click_{int(time.time())}")
                elif cmd == 'alldump':
                    text = page.evaluate("() => document.body.innerText")
                    for line in text.split('\n'):
                        l = line.strip()
                        if l:
                            print(f"   {l[:120]}")
                elif cmd.startswith('js '):
                    js_code = raw_cmd[3:].strip()
                    try:
                        result = page.evaluate(f"() => {js_code}")
                        print(f"   → {result}")
                    except Exception as e:
                        print(f"   ❌ JS error: {e}")
                else:
                    print(f"   Unknown: {cmd}")

        pid_info = 'reconnected' if not chrome_proc else chrome_proc.pid
        print(f"\n✅ Done. Chrome stays open (PID: {pid_info}).")

    except KeyboardInterrupt:
        print("\n⏹️  Interrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
