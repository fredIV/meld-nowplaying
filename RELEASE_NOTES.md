Now playing overlay for Meld Studio — Spotify, YouTube, anything.

Reads the Windows media session, so there is **no Spotify developer app, no client ID or
secret, no Premium requirement and no API quota**. Whatever is playing on the machine
shows up.

### Getting started

1. Download `meld-nowplaying.exe` below and run it.
2. Play something.
3. Open <http://127.0.0.1:8752/settings> and click **Add to Meld** — the layer lands in
   your current scene, already named, sized and pointed at the overlay.

Windows SmartScreen will warn about the download because the executable is unsigned:
*More info → Run anyway*. If you would rather not, run it from source with `start.bat`.

### What's in it

- Four layouts — `bar`, `card`, `text`, `vertical` — switchable per layer with
  `?layout=` on the URL, so several layers can share one server
- Track-change pop-in, blurred album art, marquee for long titles, live progress
- Settings in the browser; display changes apply as soon as you save
- `nowplaying.txt`, `nowplaying.json` and `art.png` for Streamer.bot, Stream Deck and
  anything else that watches a file
- Optional Meld WebChannel link: points the layer at the overlay for you, hides it
  between songs, hides it while a chosen mixer track is muted, fires a stream event on
  track change
- Runs at startup with `install-autostart.bat`

### Note on the Meld link

Meld's control API needs *Preferences → Advanced → WebSocket Server → Allow remote
connections* switched **on**, and Meld **restarted** afterwards. Despite the name,
nothing reaches the API locally until that is done. The overlay itself works without it.
