"""
meld-spotify - now playing overlay for Meld Studio.

Reads Windows SMTC (the same data the media flyout shows), so it works with
Spotify without a Spotify developer app, API key, or Premium account.
Serves a small HTML overlay + a live SSE feed on 127.0.0.1.

Point a Meld Studio Web layer at http://127.0.0.1:8752/
"""

import asyncio
import hashlib
import json
import os
import queue
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as MediaManager,
        GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
    )
    from winrt.windows.storage.streams import Buffer, DataReader, InputStreamOptions
except ImportError:
    sys.exit(
        "Missing dependencies.\n"
        "Run:  pip install winrt-Windows.Media.Control winrt-Windows.Storage.Streams\n"
        "(or just double-click start.bat, which does it for you)"
    )

# the project folder can live on a mount whose timestamps confuse
# Python's bytecode cache, which silently keeps stale imports alive
sys.dont_write_bytecode = True

from meld_link import MeldLink
from install_link import build as build_install_link

# Frozen with PyInstaller the pages travel inside the executable, while
# config and the output files belong next to it where people can see them.
if getattr(sys, "frozen", False):
    ASSETS = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    HERE = os.path.dirname(sys.executable)
else:
    ASSETS = HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULTS = {
    "port": 8752,
    "poll_interval": 0.5,
    "source_filter": "spotify",   # substring match on the app id; "" = any player
    "hide_when_paused": False,

    "layout": "bar",              # bar | card | text | vertical
    "popin_seconds": 6,           # expanded card on track change; 0 disables
    "blurred_art_background": True,

    "write_text_file": True,
    "text_file_format": "{title} - {artist}",

    "exit_with_meld": False,          # quit once Meld Studio closes
    "meld_process": "MeldStudio.exe",

    "meld": {},
}


def load_config():
    cfg = dict(DEFAULTS)
    path = os.path.join(HERE, "config.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                cfg.update(json.load(fh))
        except Exception as exc:
            print(f"[warn] config.json ignored: {exc}")
    return cfg


CONFIG = load_config()

# ---------------------------------------------------------------- shared state

_lock = threading.Lock()
_state = {"playing": False, "title": "", "artist": "", "album": "", "app": "",
          "position": 0.0, "duration": 0.0, "at": 0.0, "art": None}
_art_bytes = None
_link = None
_clients = []
_clients_lock = threading.Lock()


def broadcast(payload):
    line = f"data: {json.dumps(payload)}\n\n".encode("utf-8")
    with _clients_lock:
        dead = []
        for q in _clients:
            try:
                q.put_nowait(line)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _clients.remove(q)


def image_kind(data):
    """SMTC hands back PNG most of the time, JPEG occasionally."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png", "image/png"
    return "jpg", "image/jpeg"


def write_outputs(payload, art):
    """Plain files for Stream Deck / Streamer.bot / !song and anything else."""
    if not CONFIG.get("write_text_file"):
        return
    try:
        fmt = CONFIG.get("text_file_format") or "{title} - {artist}"
        text = fmt.format(title=payload.get("title") or "",
                          artist=payload.get("artist") or "",
                          album=payload.get("album") or "")
        if not (payload.get("title") or "").strip():
            text = ""
        with open(os.path.join(HERE, "nowplaying.txt"), "w", encoding="utf-8") as fh:
            fh.write(text)
        with open(os.path.join(HERE, "nowplaying.json"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        if art:
            ext, _ = image_kind(art)
            with open(os.path.join(HERE, f"art.{ext}"), "wb") as fh:
                fh.write(art)
            stale = os.path.join(HERE, "art.jpg" if ext == "png" else "art.png")
            if os.path.exists(stale):
                try:
                    os.remove(stale)
                except OSError:
                    pass
    except Exception as exc:
        print(f"[warn] could not write output files: {exc}")


# ---------------------------------------------------------------- SMTC reading

async def read_thumbnail(ref):
    """SMTC hands back a stream reference; turn it into raw image bytes."""
    if ref is None:
        return None
    try:
        stream = await ref.open_read_async()
        size = int(stream.size)
        if not size:
            return None
        buf = Buffer(size)
        await stream.read_async(buf, size, InputStreamOptions.READ_AHEAD)
        n = int(buf.length)
        if not n:
            return None
        try:
            return bytes(memoryview(buf))[:n]        # PyWinRT buffer protocol
        except Exception:
            pass
        reader = DataReader.from_buffer(buf)
        try:
            out = bytearray(n)
            reader.read_bytes(out)
            return bytes(out)
        except TypeError:
            return bytes(reader.read_bytes(n))
    except Exception as exc:
        print(f"[warn] thumbnail read failed: {exc}")
        return None


def pick_session(manager, wanted):
    sessions = list(manager.get_sessions())
    if wanted:
        wanted = wanted.lower()
        matches = [s for s in sessions
                   if wanted in (s.source_app_user_model_id or "").lower()]
        if not matches:
            return None
        for s in matches:                       # prefer one that is playing
            try:
                if s.get_playback_info().playback_status == PlaybackStatus.PLAYING:
                    return s
            except Exception:
                pass
        return matches[0]
    return manager.get_current_session()


def _secs(value):
    """Windows.Foundation.TimeSpan comes through as a timedelta."""
    try:
        return max(0.0, value.total_seconds())
    except AttributeError:
        try:
            return max(0.0, float(value) / 1e7)   # 100ns ticks, just in case
        except Exception:
            return 0.0


async def poll_loop(link=None):
    global _art_bytes
    manager = await MediaManager.request_async()
    last_key = None
    failures = 0

    while True:
        snapshot = {"playing": False, "title": "", "artist": "", "album": "",
                    "app": "", "position": 0.0, "duration": 0.0,
                    "at": time.time(), "art": None}
        try:
            session = pick_session(manager, CONFIG["source_filter"])
            if session is not None:
                props = await session.try_get_media_properties_async()
                info = session.get_playback_info()
                timeline = session.get_timeline_properties()

                snapshot["title"] = props.title or ""
                snapshot["artist"] = props.artist or ""
                snapshot["album"] = props.album_title or ""
                snapshot["app"] = session.source_app_user_model_id or ""
                snapshot["playing"] = info.playback_status == PlaybackStatus.PLAYING
                snapshot["position"] = _secs(timeline.position)
                snapshot["duration"] = _secs(timeline.end_time)

                key = f"{snapshot['title']}|{snapshot['artist']}|{snapshot['album']}"
                if key != last_key:
                    art = await read_thumbnail(props.thumbnail)
                    last_key = key
                    with _lock:
                        _art_bytes = art

                if CONFIG.get("hide_when_paused") and not snapshot["playing"]:
                    snapshot["title"] = ""

                with _lock:
                    have_art = _art_bytes is not None
                if snapshot["title"] and have_art:
                    snapshot["art"] = "/art?v=" + hashlib.md5(
                        key.encode("utf-8")).hexdigest()[:10]
            failures = 0
        except Exception as exc:
            failures += 1
            print(f"[warn] smtc read failed: {exc}")
            if failures >= 5:
                print("[info] reopening the Windows media session manager")
                try:
                    manager = await MediaManager.request_async()
                    failures = 0
                except Exception as exc2:
                    print(f"[warn] could not reopen session manager: {exc2}")
                    await asyncio.sleep(3)

        with _lock:
            changed = (
                snapshot["title"] != _state["title"]
                or snapshot["artist"] != _state["artist"]
                or snapshot["playing"] != _state["playing"]
                or abs(snapshot["position"] - _state["position"]) > 1.5
                or snapshot["duration"] != _state["duration"]
            )
            _state.update(snapshot)
            payload = dict(_state)

        if changed:
            broadcast(payload)
            with _lock:
                art_now = _art_bytes
            write_outputs(payload, art_now)
            if link is not None:
                link.update(payload)

        await asyncio.sleep(CONFIG["poll_interval"])


# ---------------------------------------------------------------- http serving

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"     # keeps SSE simple: stream until close

    def log_message(self, *args):
        pass

    def _send(self, code, ctype, body, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]

        if path in ("/", "/overlay", "/index.html"):
            try:
                with open(os.path.join(ASSETS, "overlay.html"), "rb") as fh:
                    body = fh.read()
            except OSError:
                self._send(404, "text/plain", b"overlay.html not found")
                return
            self._send(200, "text/html; charset=utf-8", body)

        elif path == "/state":
            with _lock:
                body = json.dumps(_state).encode("utf-8")
            self._send(200, "application/json", body)

        elif path == "/art":
            with _lock:
                data = _art_bytes
            if not data:
                self._send(404, "text/plain", b"no art")
            else:
                self._send(200, image_kind(data)[1], data,
                           {"Cache-Control": "public, max-age=3600"})

        elif path == "/diag":
            link = _link
            body = {
                "meld_enabled": bool((CONFIG.get("meld") or {}).get("enabled")),
                "meld_linked": bool(link and link.ws is not None),
                "meld_methods": len(link._methods) if link else 0,
                "meld_session_items": len(link._items()) if link else 0,
                "meld_layer": (CONFIG.get("meld") or {}).get("layer_name"),
                "meld_layer_found": bool(
                    link and link._find("layer",
                                        (CONFIG.get("meld") or {}).get("layer_name"))[0]),
            }
            wanted = None
            if "?" in self.path:
                from urllib.parse import parse_qs
                wanted = parse_qs(self.path.split("?", 1)[1]).get("layer", [None])[0]
            if wanted and link:
                item_id, item = link._find("layer", wanted)
                body["layer_id"] = item_id
                body["layer"] = item
            self._send(200, "application/json",
                       json.dumps(body, indent=2).encode("utf-8"))

        elif path == "/quit":
            self._send(200, "text/plain", b"stopping")
            threading.Thread(target=lambda: (time.sleep(0.3), os._exit(0)),
                             daemon=True).start()

        elif path == "/settings":
            try:
                with open(os.path.join(ASSETS, "settings.html"), "rb") as fh:
                    page = fh.read()
            except OSError:
                self._send(404, "text/plain", b"settings.html not found")
                return
            self._send(200, "text/html; charset=utf-8", page)

        elif path == "/api/install-link":
            from urllib.parse import parse_qs
            query = parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
            layout = (query.get("layout") or [CONFIG.get("layout", "bar")])[0]
            name = (query.get("name")
                    or [(CONFIG.get("meld") or {}).get("layer_name") or "Now Playing"])[0]
            link = build_install_link(int(CONFIG["port"]), layout, name)
            self._send(200, "application/json",
                       json.dumps({"link": link, "layout": layout,
                                   "name": name}).encode("utf-8"))

        elif path == "/api/config":
            with _lock:
                body = json.dumps(CONFIG, indent=2).encode("utf-8")
            self._send(200, "application/json", body)

        elif path == "/config":
            body = json.dumps({
                "layout": CONFIG.get("layout", "bar"),
                "popin_seconds": CONFIG.get("popin_seconds", 6),
                "blurred_art_background": CONFIG.get("blurred_art_background", True),
            }).encode("utf-8")
            self._send(200, "application/json", body)

        elif path == "/events":
            self.stream_events()

        else:
            self._send(404, "text/plain", b"not found")

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/api/config":
            self._send(404, "text/plain", b"not found")
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            incoming = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(incoming, dict):
                raise ValueError("expected an object")
        except Exception as exc:
            self._send(400, "application/json",
                       json.dumps({"error": str(exc)}).encode("utf-8"))
            return

        with _lock:
            merged = dict(CONFIG)
            for key, value in incoming.items():
                if key == "meld" and isinstance(value, dict):
                    meld = dict(merged.get("meld") or {})
                    meld.update(value)
                    merged["meld"] = meld
                else:
                    merged[key] = value
            CONFIG.clear()
            CONFIG.update(merged)
            snapshot = dict(CONFIG)

        try:
            path = os.path.join(HERE, "config.json")
            with open(path + ".tmp", "w", encoding="utf-8") as fh:
                json.dump(snapshot, fh, indent=2)
                fh.write("\n")
            os.replace(path + ".tmp", path)
        except OSError as exc:
            self._send(500, "application/json",
                       json.dumps({"error": str(exc)}).encode("utf-8"))
            return

        # push the new state so open overlays pick up display changes at once
        with _lock:
            payload = dict(_state)
        broadcast(payload)
        self._send(200, "application/json",
                   json.dumps({"ok": True}).encode("utf-8"))

    def stream_events(self):
        q = queue.Queue(maxsize=32)
        with _clients_lock:
            _clients.append(q)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            with _lock:
                first = dict(_state)
            self.wfile.write(f"data: {json.dumps(first)}\n\n".encode("utf-8"))
            self.wfile.flush()

            while True:
                try:
                    line = q.get(timeout=15)
                except queue.Empty:
                    line = b": keepalive\n\n"
                self.wfile.write(line)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with _clients_lock:
                if q in _clients:
                    _clients.remove(q)


def process_running(exe_name):
    """True/False if we could look, None if the check itself failed."""
    import ctypes
    import ctypes.wintypes as wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_wchar * 260),
        ]

    kernel32 = ctypes.windll.kernel32
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    if snapshot == -1:
        return None
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        wanted = exe_name.lower()
        found = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while found:
            if entry.szExeFile.lower() == wanted:
                return True
            found = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
        return False
    except Exception:
        return None
    finally:
        kernel32.CloseHandle(snapshot)


def watch_meld():
    """Shut down when Meld Studio does - for launchers that start the pair."""
    name = CONFIG.get("meld_process") or "MeldStudio.exe"
    seen = False
    misses = 0
    while True:
        time.sleep(3)
        running = process_running(name)
        if running is None:
            continue
        if running:
            seen, misses = True, 0
        elif seen:
            # two misses in a row, so a momentary hiccup does not kill us
            misses += 1
            if misses >= 2:
                print(f"[info] {name} closed - shutting down")
                os._exit(0)


def stop_previous_instance(port):
    """A second launch replaces the first instead of failing to bind."""
    import urllib.request
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/quit", timeout=1.5).read()
        print("[info] stopped the previous instance")
        time.sleep(1.2)
    except Exception:
        pass


def main():
    port = int(CONFIG["port"])
    stop_previous_instance(port)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()

    if CONFIG.get("exit_with_meld"):
        threading.Thread(target=watch_meld, daemon=True).start()

    print("meld-spotify running")
    print(f"  overlay : http://127.0.0.1:{port}/")
    print(f"  state   : http://127.0.0.1:{port}/state")
    print(f"  source  : {CONFIG['source_filter'] or '(any player)'}")
    if CONFIG.get("exit_with_meld"):
        print(f"  quits   : when {CONFIG.get('meld_process')} closes")
    print("Paste the overlay URL into a Meld Studio Web layer. Ctrl+C to stop.")

    global _link
    meld_cfg = CONFIG.get("meld") or {}
    link = MeldLink(meld_cfg, f"http://127.0.0.1:{port}/", print)
    _link = link
    if meld_cfg.get("enabled"):
        print(f"  meld    : {meld_cfg.get('url', 'ws://127.0.0.1:13376')} "
              f"-> layer {meld_cfg.get('layer_name')}")

    async def amain():
        await asyncio.gather(poll_loop(link), link.run())

    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
