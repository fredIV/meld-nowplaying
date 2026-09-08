"""
Minimal Qt WebChannel client for Meld Studio.

Meld exposes a QWebChannel on ws://127.0.0.1:13376. This speaks just enough of
that protocol to:

  * point a named Web layer at the overlay URL (no manual copy/paste)
  * show/hide that layer as tracks start and stop
  * hide it while a named audio track is muted in Meld
  * fire a Meld stream event (confetti, timer, ...) on track change

Everything here is optional and off by default; if Meld isn't running the link
just retries quietly in the background.
"""

import asyncio
import json

try:
    import websockets
except ImportError:      # optional dependency
    websockets = None

# Qt WebChannel message types
SIGNAL = 1
RESPONSE = 2
INIT = 3
IDLE = 4
INVOKE_METHOD = 6
CONNECT_TO_SIGNAL = 7
PROPERTY_UPDATE = 10

OBJECT = "meld"


class MeldLink:
    def __init__(self, cfg, overlay_url, log=print):
        self.cfg = cfg or {}
        self.overlay_url = overlay_url
        self.log = log

        self.ws = None
        self._id = 0
        self._pending = {}
        self._methods = {}      # name -> index
        self._signals = {}      # name -> index
        self._props = {}        # index -> name
        self._session = {}

        self._has_track = None      # last state pushed from the poller
        self._track_key = None
        self._muted = False
        self._layer_url_set = False
        self._connected_note = False
        self._warned = False

    # ------------------------------------------------------------ public API

    def update(self, state):
        """Called by the SMTC poller on every state change."""
        self._has_track = bool(state.get("title"))
        key = f"{state.get('title')}|{state.get('artist')}"
        changed = key != self._track_key and self._has_track
        self._track_key = key
        if self.ws is not None:
            asyncio.ensure_future(self._apply(track_changed=changed))

    async def run(self):
        if not self.cfg.get("enabled"):
            return
        if websockets is None:
            self.log("[meld] 'websockets' package not installed - link disabled")
            return

        url = self.cfg.get("url", "ws://127.0.0.1:13376")
        backoff = 2
        while True:
            try:
                self._dbg(f"connecting to {url}")
                async with websockets.connect(url, max_size=None) as ws:
                    self._dbg("socket open")
                    self.ws = ws
                    self._connected_note = False
                    self._layer_url_set = False
                    # the reader must be running before the handshake, or the
                    # init response has nobody to resolve its future
                    reader = asyncio.ensure_future(self._read_loop())
                    try:
                        await self._handshake()
                        backoff = 2
                        await reader
                    finally:
                        if reader.done() and not reader.cancelled():
                            exc = reader.exception()
                            if exc is not None and not self._warned:
                                self._warned = True
                                self.log(f"[meld] reader error: {exc!r}")
                        reader.cancel()
            except Exception as exc:
                if self._connected_note or not self._warned:
                    self._warned = True
                    self.log(f"[meld] not linked ({type(exc).__name__}: {exc}) "
                             f"- retrying in the background")
            finally:
                self.ws = None
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)

    # ------------------------------------------------------------- protocol

    def _dbg(self, msg):
        if self.cfg.get("debug"):
            self.log(f"[meld:debug] {msg}")

    async def _send(self, msg):
        await self.ws.send(json.dumps(msg))

    async def _call(self, method, args):
        idx = self._methods.get(method)
        if idx is None:
            return None
        self._id += 1
        mid = self._id
        fut = asyncio.get_event_loop().create_future()
        self._pending[mid] = fut
        await self._send({"type": INVOKE_METHOD, "object": OBJECT,
                          "method": idx, "args": args, "id": mid})
        try:
            return await asyncio.wait_for(fut, timeout=5)
        except asyncio.TimeoutError:
            self._pending.pop(mid, None)
            return None

    async def _handshake(self):
        self._id += 1
        mid = self._id
        fut = asyncio.get_event_loop().create_future()
        self._pending[mid] = fut
        await self._send({"type": INIT, "id": mid})
        self._dbg(f"init sent (id={mid}), waiting for reply")
        data = await asyncio.wait_for(fut, timeout=10)
        self._dbg(f"init reply keys: {sorted((data or {}).keys())}")
        self._ingest_objects(data or {})
        await self._send({"type": IDLE})

        for name in ("sessionChanged", "gainUpdated"):
            idx = self._signals.get(name)
            if idx is not None:
                await self._send({"type": CONNECT_TO_SIGNAL,
                                  "object": OBJECT, "signal": idx})

        if "setClientName" in self._methods:
            await self._call("setClientName", ["meld-spotify"])

        self._connected_note = True
        self.log(f"[meld] linked ({len(self._methods)} methods)")
        await self._apply()

    def _ingest_objects(self, data):
        if not isinstance(data, dict):
            self._dbg(f"unexpected init payload: {type(data).__name__}")
            return
        obj = data.get(OBJECT) or {}
        if not isinstance(obj, dict):
            return
        for entry in obj.get("methods", []):
            try:
                self._methods[entry[0]] = entry[1]
            except (TypeError, IndexError):
                pass
        for entry in obj.get("signals", []):
            try:
                self._signals[entry[0]] = entry[1]
            except (TypeError, IndexError):
                pass
        for entry in obj.get("properties", []):
            try:
                self._props[entry[0]] = entry[1]
                if entry[1] == "session":
                    self._session = entry[3] or {}
            except (TypeError, IndexError):
                pass

    async def _read_loop(self):
        while True:
            try:
                raw = await self.ws.recv()
            except Exception as exc:
                if self._connected_note:
                    self.log(f"[meld] reader stopped: {type(exc).__name__}")
                return
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(msg, dict):
                # Meld sends the odd bare JSON string; not for us
                continue
            mtype = msg.get("type")
            self._dbg(f"recv type={mtype} keys={sorted(msg.keys())} "
                      f"id={msg.get('id')}")
            try:
                await self._dispatch(mtype, msg)
            except Exception as exc:
                self._dbg(f"message handling failed: {exc!r}")
            continue

    async def _dispatch(self, mtype, msg):
        # Meld answers a request with the request's id but not always with
        # the message type Qt documents, so the id is what we trust first.
        mid = msg.get("id")
        if mid is not None and mid in self._pending:
            fut = self._pending.pop(mid)
            if not fut.done():
                fut.set_result(msg.get("data"))
            return

        if mtype == RESPONSE or (mtype is None and "data" in msg):
            if self._pending:
                fut = self._pending.pop(sorted(self._pending)[0])
                if not fut.done():
                    fut.set_result(msg.get("data"))

        elif mtype == PROPERTY_UPDATE:
            entries = msg.get("data")
            if isinstance(entries, dict):
                entries = [entries]
            for entry in entries or []:
                if not isinstance(entry, dict):
                    continue
                props = entry.get("properties")
                if not isinstance(props, dict):
                    continue
                for idx, value in props.items():
                    try:
                        name = self._props.get(int(idx))
                    except (TypeError, ValueError):
                        name = idx if isinstance(idx, str) else None
                    if name == "session":
                        self._session = value or {}
                        self._layer_url_set = False
                        await self._apply()

        elif mtype == SIGNAL:
            sig = msg.get("signal")
            args = msg.get("args") or []
            try:
                if sig == self._signals.get("gainUpdated"):
                    await self._on_gain(args)
                elif sig == self._signals.get("sessionChanged"):
                    await self._refresh_session()
            except Exception as exc:
                self._dbg(f"signal handling failed: {exc!r}")

    async def _refresh_session(self):
        self._id += 1
        mid = self._id
        fut = asyncio.get_event_loop().create_future()
        self._pending[mid] = fut
        await self._send({"type": INIT, "id": mid})
        try:
            data = await asyncio.wait_for(fut, timeout=5)
        except asyncio.TimeoutError:
            return
        self._ingest_objects(data or {})
        self._layer_url_set = False
        await self._apply()

    # -------------------------------------------------------------- session

    def _items(self):
        return (self._session or {}).get("items") or {}

    def _find(self, kind, name):
        if not name:
            return None, None
        wanted = name.strip().lower()
        for item_id, item in self._items().items():
            if not isinstance(item, dict):
                continue
            if item.get("type") != kind:
                continue
            if (item.get("name") or "").strip().lower() == wanted:
                return item_id, item
        return None, None

    async def _on_gain(self, args):
        track_name = self.cfg.get("mute_aware_track") or ""
        if not track_name or len(args) < 3:
            return
        track_id, _gain, muted = args[0], args[1], args[2]
        wanted_id, _ = self._find("track", track_name)
        if wanted_id and track_id == wanted_id:
            if bool(muted) != self._muted:
                self._muted = bool(muted)
                await self._apply()

    # --------------------------------------------------------------- actions

    async def _apply(self, track_changed=False):
        if self.ws is None:
            return
        layer_id, layer = self._find("layer", self.cfg.get("layer_name"))
        if not layer_id:
            return

        if self.cfg.get("auto_set_url", True) and not self._layer_url_set:
            if layer.get("url") != self.overlay_url:
                await self._call("setProperty", [layer_id, "url", self.overlay_url])
            self._layer_url_set = True

        if self.cfg.get("hide_between_songs") and self._has_track is not None:
            want = bool(self._has_track) and not self._muted
            have = bool(layer.get("visible", True))
            if want != have:
                scene_id = layer.get("parent")
                if scene_id:
                    await self._call("toggleLayer", [scene_id, layer_id])
                    layer["visible"] = want

        evt = self.cfg.get("stream_event_on_track_change")
        if track_changed and evt:
            await self._call("sendStreamEvent",
                             [evt.get("type"), evt.get("data") or {}])
