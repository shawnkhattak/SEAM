#!/usr/bin/env python3
"""SEAM — Development Control Panel · python start.py"""

import curses
import os
import socket
import subprocess
import threading
import time
import urllib.request
import webbrowser
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT     = Path(__file__).resolve().parent
BACKEND  = ROOT / "backend"
FRONTEND = ROOT / "frontend"
UVICORN  = BACKEND / ".venv" / "bin" / "uvicorn"
ALEMBIC  = BACKEND / ".venv" / "bin" / "alembic"
VITE_BIN = FRONTEND / "node_modules" / ".bin" / "vite"

HOST          = "127.0.0.1"
BACKEND_URL   = "http://localhost:8000"
FRONTEND_URL  = "http://localhost:5173"
BACKEND_API   = f"{BACKEND_URL}/api"

# ── Status ────────────────────────────────────────────────────────────────────
class St(Enum):
    UNKNOWN  = "unknown"
    STARTING = "starting…"
    RUNNING  = "running"
    STOPPING = "stopping…"
    STOPPED  = "stopped"
    ERROR    = "error"

ICON: dict[St, str] = {
    St.UNKNOWN:  "?",
    St.STARTING: "●",
    St.RUNNING:  "✓",
    St.STOPPING: "◌",
    St.STOPPED:  "✗",
    St.ERROR:    "!",
}

CP_NORM, CP_GRN, CP_RED, CP_CYAN, CP_YEL, CP_SEL = 1, 2, 3, 4, 5, 6

ST_CP: dict[St, int] = {
    St.UNKNOWN:  CP_CYAN,
    St.STARTING: CP_YEL,
    St.RUNNING:  CP_GRN,
    St.STOPPING: CP_YEL,
    St.STOPPED:  CP_RED,
    St.ERROR:    CP_RED,
}

# ── Service state ─────────────────────────────────────────────────────────────
@dataclass
class Svc:
    key:    str
    label:  str
    port:   int
    status: St                         = St.UNKNOWN
    proc:   Optional[subprocess.Popen] = None
    logs:   deque                      = field(default_factory=lambda: deque(maxlen=500))

svcs: dict[str, Svc] = {
    "db":       Svc("db",       "PostgreSQL  :5432", 5432),
    "backend":  Svc("backend",  "FastAPI     :8000", 8000),
    "frontend": Svc("frontend", "Vite        :5173", 5173),
}

_lock  = threading.Lock()
_quit  = threading.Event()
_dirty = threading.Event()
activity: deque[str] = deque(maxlen=300)


def _log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    activity.appendleft(f"[{ts}] {msg}")
    _dirty.set()


def _read_backend_env(name: str) -> str:
    env_path = BACKEND / ".env"
    if not env_path.exists():
        return ""
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == name:
            return value.strip().strip('"').strip("'")
    return ""


def _frontend_env() -> dict[str, str]:
    admin_token = os.environ.get("VITE_ADMIN_TOKEN") or _read_backend_env("ADMIN_TOKEN")
    env: dict[str, str] = {"VITE_API_BASE_URL": os.environ.get("VITE_API_BASE_URL", "")}
    if admin_token:
        env["VITE_ADMIN_TOKEN"] = admin_token
    return env


# ── Health checks ─────────────────────────────────────────────────────────────
def _tcp(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.8):
            return True
    except OSError:
        return False


def _http(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1.5) as r:
            return r.status < 500
    except Exception:
        return False


HEALTH: dict[str, Callable[[], bool]] = {
    "db":       lambda: _tcp(5432),
    "backend":  lambda: _http(f"{BACKEND_API}/health"),
    "frontend": lambda: _http(FRONTEND_URL),
}


def _health_loop() -> None:
    while not _quit.is_set():
        for key, svc in svcs.items():
            proc_exited = svc.proc is not None and svc.proc.poll() is not None
            alive = HEALTH[key]()
            with _lock:
                old = svc.status
                if proc_exited and old in (St.STARTING, St.RUNNING):
                    code = svc.proc.returncode if svc.proc else "?"
                    svc.proc = None
                    svc.status = St.ERROR
                    _log(f"{key} exited unexpectedly (code {code})")
                elif alive and old in (St.STARTING, St.UNKNOWN):
                    svc.status = St.RUNNING
                    _log(f"{key} ready")
                elif alive and old == St.STOPPED:
                    svc.status = St.RUNNING
                elif not alive and old == St.RUNNING:
                    svc.status = St.STOPPED
                    _log(f"{key} went offline")
                elif not alive and old == St.UNKNOWN:
                    svc.status = St.STOPPED
        _dirty.set()
        _quit.wait(2)


def _reader(proc: subprocess.Popen, buf: deque) -> None:
    for raw in iter(proc.stdout.readline, b""):
        buf.append(raw.decode("utf-8", errors="replace").rstrip())
        _dirty.set()
    _dirty.set()


def _proc_alive(proc: Optional[subprocess.Popen]) -> bool:
    return proc is not None and proc.poll() is None


def _wait_for(key: str, seconds: int, label: str) -> bool:
    for _ in range(seconds):
        if HEALTH[key]():
            with _lock:
                svcs[key].status = St.RUNNING
            _log(f"{label} ready")
            return True
        time.sleep(1)
    with _lock:
        svcs[key].status = St.ERROR
    _log(f"ERROR: {label} did not become ready within {seconds}s")
    return False


def _preflight() -> bool:
    ok = True
    checks = [
        (BACKEND / ".env", "backend/.env missing — copy backend/.env.example"),
        (UVICORN, "backend venv missing — cd backend && python -m venv .venv && pip install -e ."),
        (ALEMBIC, "backend venv missing alembic — cd backend && pip install -e ."),
        (FRONTEND / "package.json", "frontend/package.json missing"),
        (FRONTEND / "node_modules", "frontend deps missing — cd frontend && npm install"),
        (VITE_BIN, "Vite missing — cd frontend && npm install"),
    ]
    for path, message in checks:
        if not path.exists():
            _log(f"ERROR: {message}")
            ok = False
    if not _read_backend_env("ADMIN_TOKEN") and not os.environ.get("VITE_ADMIN_TOKEN"):
        _log("WARNING: ADMIN_TOKEN not set; admin dashboard will return 401")
    return ok


def _has_docker() -> bool:
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=4).returncode == 0
    except Exception:
        return False


def _brew_pg_version() -> str | None:
    for ver in ("17", "16", "15", "14"):
        try:
            r = subprocess.run(["brew", "list", f"postgresql@{ver}"], capture_output=True, timeout=4)
            if r.returncode == 0:
                return ver
        except Exception:
            pass
    return None


def _bg(fn: Callable) -> None:
    threading.Thread(target=fn, daemon=True).start()


def _start_db() -> None:
    s = svcs["db"]
    with _lock:
        if s.status == St.RUNNING:
            _log("DB already running")
            return
        s.status = St.STARTING
    _log("Starting database…")
    if _has_docker():
        r = subprocess.run(["docker", "compose", "up", "-d", "db"], cwd=str(ROOT), capture_output=True)
        if r.returncode != 0:
            with _lock:
                s.status = St.ERROR
            _log("Docker failed: " + r.stderr.decode(errors="replace").strip()[-80:])
    elif (pg_ver := _brew_pg_version()):
        subprocess.run(["brew", "services", "start", f"postgresql@{pg_ver}"], capture_output=True)
    else:
        with _lock:
            s.status = St.ERROR
        _log("No DB backend found (install Docker or: brew install postgresql@16)")


def _stop_db() -> None:
    with _lock:
        svcs["db"].status = St.STOPPING
    _log("Stopping database…")
    if _has_docker():
        subprocess.run(["docker", "compose", "stop", "db"], cwd=str(ROOT), capture_output=True)
    elif (pg_ver := _brew_pg_version()):
        subprocess.run(["brew", "services", "stop", f"postgresql@{pg_ver}"], capture_output=True)
    with _lock:
        svcs["db"].status = St.STOPPED
    _log("Database stopped")


def _start_backend() -> None:
    s = svcs["backend"]
    with _lock:
        if s.status == St.RUNNING and _proc_alive(s.proc):
            _log("Backend already running")
            return
        if s.status == St.RUNNING and s.proc is None:
            _log("Backend already running outside this panel")
            return
        s.status = St.STARTING
    _log("Starting backend…")
    if not UVICORN.exists():
        with _lock:
            s.status = St.ERROR
        _log("ERROR: venv missing — cd backend && python -m venv .venv && pip install -e .")
        return
    proc = subprocess.Popen(
        [str(UVICORN), "app.main:app", "--reload", "--host", HOST, "--port", "8000"],
        cwd=str(BACKEND),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={**os.environ},
    )
    with _lock:
        s.proc = proc
    threading.Thread(target=_reader, args=(proc, s.logs), daemon=True).start()
    _log(f"Backend started PID={proc.pid}")


def _stop_backend() -> None:
    s = svcs["backend"]
    with _lock:
        proc = s.proc
        s.status = St.STOPPING
    if proc:
        _log(f"Stopping backend PID={proc.pid}…")
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
    elif HEALTH["backend"]():
        _log("Backend running outside this panel; leaving it online")
        with _lock:
            s.status = St.RUNNING
        return
    with _lock:
        s.proc = None
        s.status = St.STOPPED
    _log("Backend stopped")


def _start_frontend() -> None:
    s = svcs["frontend"]
    with _lock:
        if s.status == St.RUNNING and _proc_alive(s.proc):
            _log("Frontend already running")
            return
        if s.status == St.RUNNING and s.proc is None:
            _log("Frontend already running outside this panel")
            return
        s.status = St.STARTING
    _log("Starting frontend…")
    if not VITE_BIN.exists():
        with _lock:
            s.status = St.ERROR
        _log("ERROR: frontend deps missing — cd frontend && npm install")
        return
    proc = subprocess.Popen(
        ["npm", "run", "dev", "--", "--host", HOST, "--port", "5173"],
        cwd=str(FRONTEND),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={**os.environ, **_frontend_env()},
    )
    with _lock:
        s.proc = proc
    threading.Thread(target=_reader, args=(proc, s.logs), daemon=True).start()
    _log(f"Frontend started PID={proc.pid}")


def _stop_frontend() -> None:
    s = svcs["frontend"]
    with _lock:
        proc = s.proc
        s.status = St.STOPPING
    if proc:
        _log(f"Stopping frontend PID={proc.pid}…")
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
    elif HEALTH["frontend"]():
        _log("Frontend running outside this panel; leaving it online")
        with _lock:
            s.status = St.RUNNING
        return
    with _lock:
        s.proc = None
        s.status = St.STOPPED
    _log("Frontend stopped")


def _migrate() -> None:
    _log("Running Alembic migrations…")
    if not ALEMBIC.exists():
        _log("ERROR: alembic not in .venv")
        return
    if not HEALTH["db"]():
        _log("ERROR: database not reachable; migrations skipped")
        return
    proc = subprocess.Popen(
        [str(ALEMBIC), "upgrade", "head"],
        cwd=str(BACKEND),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    for raw in iter(proc.stdout.readline, b""):
        line = raw.decode("utf-8", errors="replace").rstrip()
        svcs["backend"].logs.append(line)
        activity.appendleft("  " + line)
    proc.wait()
    if proc.returncode == 0:
        _log("Migrations applied")
    else:
        _log(f"Migrations FAILED (exit {proc.returncode})")


def _start_all() -> None:
    _log("━━ Start All ━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if not _preflight():
        _log("Start All aborted by failed preflight")
        return
    _start_db()
    _log("Waiting for database…")
    if not _wait_for("db", 30, "database"):
        return
    _migrate()
    _start_backend()
    _log("Waiting for backend…")
    if not _wait_for("backend", 30, "backend"):
        return
    _start_frontend()
    _log("Waiting for frontend…")
    if not _wait_for("frontend", 30, "frontend"):
        return
    _log(f"━━ All services running → {FRONTEND_URL} ━━")


def _stop_all() -> None:
    _log("━━ Stop All ━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    _stop_frontend()
    _stop_backend()
    _stop_db()
    _log("━━ All services stopped ━━━━━━━━━━━━━━━━")


def _toggle(key: str) -> None:
    starts = {"db": _start_db, "backend": _start_backend, "frontend": _start_frontend}
    stops  = {"db": _stop_db,  "backend": _stop_backend,  "frontend": _stop_frontend}
    if svcs[key].status == St.RUNNING:
        _bg(stops[key])
    else:
        _bg(starts[key])


def _open_browser() -> None:
    webbrowser.open(FRONTEND_URL)
    _log(f"Opened → {FRONTEND_URL}")


MENU: list = [
    ("Start All Services", lambda: _bg(_start_all)),
    ("Stop All Services",  lambda: _bg(_stop_all)),
    None,
    ("Toggle Database",    lambda: _toggle("db")),
    ("Toggle Backend",     lambda: _toggle("backend")),
    ("Toggle Frontend",    lambda: _toggle("frontend")),
    None,
    ("Run Migrations",     lambda: _bg(_migrate)),
    ("View Logs",          "VIEW_LOGS"),
    ("Open in Browser",    _open_browser),
    None,
    ("Quit",               "QUIT"),
]
MENU_SEL = [i for i, m in enumerate(MENU) if m is not None]

LOG_MENU: list = [
    ("Activity Log",   "_activity"),
    ("Database Logs",  "db"),
    ("Backend Logs",   "backend"),
    ("Frontend Logs",  "frontend"),
    None,
    ("↩  Back",        "BACK"),
]
LOG_SEL = [i for i, m in enumerate(LOG_MENU) if m is not None]


def _puts(win, y: int, x: int, s: str, attr: int = 0) -> None:
    h, w = win.getmaxyx()
    if not (0 <= y < h):
        return
    if x < 0:
        s = s[-x:]
        x = 0
    avail = w - x - 1
    if avail <= 0:
        return
    try:
        win.addstr(y, x, s[:avail], attr)
    except (curses.error, UnicodeEncodeError, ValueError):
        pass


def _hline(win, y: int, ch: str, attr: int = 0) -> None:
    h, w = win.getmaxyx()
    if not (0 <= y < h):
        return
    try:
        win.addstr(y, 0, ch * (w - 1), attr)
    except curses.error:
        pass


BRAND = [
    " ┌──────────────────────────────────────────────────────────┐",
    " │   ≋  S E A M  ─  Singapore Entity Analytics Maritime  ≋  │",
    " └──────────────────────────────────────────────────────────┘",
]


def _draw_main(scr, sel: int) -> None:
    scr.erase()
    h, w = scr.getmaxyx()
    BOLD = curses.A_BOLD
    DIM  = curses.A_DIM
    cy   = curses.color_pair(CP_CYAN)
    y    = 0

    for line in BRAND:
        _puts(scr, y, max(0, (w - len(line)) // 2), line, cy | BOLD)
        y += 1
    y += 1

    _puts(scr, y, 1, "─── SERVICES " + "─" * max(0, w - 15), cy)
    y += 1
    for svc in svcs.values():
        cp    = curses.color_pair(ST_CP[svc.status])
        icon  = ICON[svc.status]
        label = f"  {icon}  {svc.label}"
        stat  = svc.status.value
        _puts(scr, y, 2, label, cp | BOLD)
        _puts(scr, y, max(len(label) + 4, 38), stat, cp)
        y += 1
    y += 1

    _puts(scr, y, 1, "─── ACTIONS " + "─" * max(0, w - 14), cy)
    y += 1
    menu_end_y = y
    for i, item in enumerate(MENU):
        if y >= h - 2:
            break
        if item is None:
            _puts(scr, y, 4, "─" * min(48, w - 6), cy | DIM)
        else:
            lbl, _ = item
            is_sel = i == sel
            prefix = "▶  " if is_sel else "   "
            attr   = (curses.color_pair(CP_SEL) | BOLD) if is_sel else curses.color_pair(CP_NORM)
            _puts(scr, y, 2, (prefix + lbl).ljust(min(54, w - 4)), attr)
        y += 1
        menu_end_y = y

    act_start = menu_end_y + 1
    if act_start < h - 3:
        _puts(scr, act_start - 1, 1, "─── ACTIVITY " + "─" * max(0, w - 15), cy)
        for j, line in enumerate(activity):
            row = act_start + j
            if row >= h - 2:
                break
            _puts(scr, row, 3, line[:w - 5], curses.color_pair(CP_NORM) | DIM)

    _hline(scr, h - 2, "─", cy)
    _puts(scr, h - 1, 2, "↑↓ navigate    Enter select    Q quit", cy)
    ts = time.strftime("%H:%M:%S")
    _puts(scr, h - 1, w - 11, ts, cy | DIM)


def _draw_log_menu(scr, sel: int) -> None:
    scr.erase()
    h, w = scr.getmaxyx()
    BOLD = curses.A_BOLD
    DIM  = curses.A_DIM
    cy   = curses.color_pair(CP_CYAN)
    y    = 0

    for line in BRAND:
        _puts(scr, y, max(0, (w - len(line)) // 2), line, cy | BOLD)
        y += 1
    y += 1

    _puts(scr, y, 1, "─── VIEW LOGS " + "─" * max(0, w - 16), cy)
    y += 1

    for i, item in enumerate(LOG_MENU):
        if y >= h - 2:
            break
        if item is None:
            _puts(scr, y, 4, "─" * 30, cy | DIM)
        else:
            lbl, _ = item
            is_sel = i == sel
            prefix = "▶  " if is_sel else "   "
            attr   = (curses.color_pair(CP_SEL) | BOLD) if is_sel else curses.color_pair(CP_NORM)
            _puts(scr, y, 2, (prefix + lbl).ljust(36), attr)
        y += 1

    _hline(scr, h - 2, "─", cy)
    _puts(scr, h - 1, 2, "↑↓ navigate    Enter select    q/ESC back", cy)


def _draw_log_view(scr, key: str, scroll: int, follow: bool) -> tuple[int, bool]:
    scr.erase()
    h, w = scr.getmaxyx()
    cy = curses.color_pair(CP_CYAN)

    if key == "_activity":
        title = "Activity Log"
        lines = list(activity)
    else:
        title = f"{key.capitalize()} Logs"
        lines = list(svcs[key].logs)

    visible = h - 3
    total   = len(lines)
    max_sc  = max(0, total - visible)

    if follow:
        scroll = max_sc
    scroll = max(0, min(scroll, max_sc))

    follow_hint = " [following]" if follow else " [f=follow]"
    title_str   = f"  {title}{follow_hint}"
    try:
        scr.addstr(0, 0, title_str[:w - 1].ljust(w - 1), curses.color_pair(CP_SEL) | curses.A_BOLD)
    except curses.error:
        pass

    for i, line in enumerate(lines[scroll: scroll + visible]):
        _puts(scr, i + 1, 0, line[:w - 1], curses.color_pair(CP_NORM))

    if not lines:
        _puts(scr, 2, 2, "No output yet…", curses.color_pair(CP_CYAN) | curses.A_DIM)

    _hline(scr, h - 2, "─", cy)
    info = f"  {scroll + 1}-{min(scroll + visible, max(total, 1))}/{max(total, 0)}    ↑↓ PgUp/PgDn    f follow    q/ESC back"
    _puts(scr, h - 1, 0, info, cy)

    return scroll, follow


def _main(scr) -> None:
    curses.start_color()
    _use_default = False
    try:
        curses.use_default_colors()
        _use_default = True
    except curses.error:
        pass

    bg = -1 if _use_default else curses.COLOR_BLACK
    curses.init_pair(CP_NORM, curses.COLOR_WHITE,  bg)
    curses.init_pair(CP_GRN,  curses.COLOR_GREEN,  bg)
    curses.init_pair(CP_RED,  curses.COLOR_RED,    bg)
    curses.init_pair(CP_CYAN, curses.COLOR_CYAN,   bg)
    curses.init_pair(CP_YEL,  curses.COLOR_YELLOW, bg)
    curses.init_pair(CP_SEL,  curses.COLOR_BLACK, curses.COLOR_CYAN)

    try:
        curses.curs_set(0)
    except curses.error:
        pass
    scr.timeout(250)

    threading.Thread(target=_health_loop, daemon=True).start()

    mode    = "main"
    sel     = MENU_SEL[0]
    log_sel = LOG_SEL[0]
    log_key = "_activity"
    log_sc  = 0
    log_fol = True

    while True:
        h, w = scr.getmaxyx()

        if h < 12 or w < 50:
            scr.erase()
            msg = "Terminal too small — resize to at least 50×12"
            _puts(scr, h // 2, max(0, (w - len(msg)) // 2), msg,
                  curses.color_pair(CP_RED) | curses.A_BOLD)
            scr.refresh()
            key = scr.getch()
            if key in (ord("q"), ord("Q")):
                break
            continue

        if mode == "main":
            _draw_main(scr, sel)
        elif mode == "log_menu":
            _draw_log_menu(scr, log_sel)
        elif mode == "log_view":
            log_sc, log_fol = _draw_log_view(scr, log_key, log_sc, log_fol)

        scr.refresh()
        key = scr.getch()
        if key == -1:
            continue

        if mode == "main":
            try:
                pos = MENU_SEL.index(sel)
            except ValueError:
                pos = 0
                sel = MENU_SEL[0]

            if key == curses.KEY_UP:
                if pos > 0:
                    sel = MENU_SEL[pos - 1]
            elif key == curses.KEY_DOWN:
                if pos < len(MENU_SEL) - 1:
                    sel = MENU_SEL[pos + 1]
            elif key in (curses.KEY_ENTER, 10, 13):
                item = MENU[sel]
                if item is None:
                    continue
                lbl, act = item
                if act == "QUIT":
                    break
                elif act == "VIEW_LOGS":
                    mode = "log_menu"
                    log_sel = LOG_SEL[0]
                elif callable(act):
                    act()
            elif key in (ord("q"), ord("Q")):
                break

        elif mode == "log_menu":
            try:
                pos = LOG_SEL.index(log_sel)
            except ValueError:
                pos = 0
                log_sel = LOG_SEL[0]

            if key == curses.KEY_UP:
                if pos > 0:
                    log_sel = LOG_SEL[pos - 1]
            elif key == curses.KEY_DOWN:
                if pos < len(LOG_SEL) - 1:
                    log_sel = LOG_SEL[pos + 1]
            elif key in (curses.KEY_ENTER, 10, 13):
                item = LOG_MENU[log_sel]
                if item is None:
                    continue
                lbl, val = item
                if val == "BACK":
                    mode = "main"
                else:
                    log_key = val
                    log_sc  = 0
                    log_fol = True
                    mode    = "log_view"
            elif key in (ord("q"), ord("Q"), 27):
                mode = "main"

        elif mode == "log_view":
            if key == curses.KEY_UP:
                log_sc  = max(0, log_sc - 1)
                log_fol = False
            elif key == curses.KEY_DOWN:
                log_sc += 1
                log_fol = False
            elif key == curses.KEY_PPAGE:
                log_sc  = max(0, log_sc - (h - 3))
                log_fol = False
            elif key == curses.KEY_NPAGE:
                log_sc += h - 3
                log_fol = False
            elif key in (ord("f"), ord("F")):
                log_fol = True
            elif key in (ord("q"), ord("Q"), 27):
                mode = "log_menu"

    _quit.set()
    for svc in svcs.values():
        if svc.proc:
            try:
                svc.proc.terminate()
                svc.proc.wait(timeout=5)
            except Exception:
                try:
                    svc.proc.kill()
                except Exception:
                    pass


if __name__ == "__main__":
    import locale
    import traceback
    locale.setlocale(locale.LC_ALL, "")

    try:
        curses.wrapper(_main)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        err_path = ROOT / "start_error.log"
        with open(err_path, "w") as f:
            traceback.print_exc(file=f)
        print(f"Crashed: {exc}")
        print(f"Full traceback written to {err_path}")
    finally:
        for s in svcs.values():
            if s.proc:
                try:
                    s.proc.terminate()
                except OSError:
                    pass
    print("SEAM Control Panel exited.")
