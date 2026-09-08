Fixes the **Add to Meld** button. In v0.1.0 the layer it created came out blank.

### What was wrong

The generated layer never set the browser's page size, so Meld fell back to its
1280×720 default and squashed that whole viewport into a 380×90 box. The overlay was
rendering the whole time — at roughly 113×11 pixels in the corner of the layer, which
reads as blank. Adding the layer by hand and pasting the URL always worked.

v0.1.1 sets the page size to match the layout, so the layer fills correctly on the first
try. Nothing else about the overlay changed.

If you already added a blank layer from v0.1.0, delete it and click **Add to Meld**
again — or just set *Browser size* on that layer to match its dimensions.

### Also in this build

- The bundled `config.json` no longer ships with the Meld API link switched on. Running
  from source used to print `[meld] not linked` on first start even if you never wanted
  the link.

---

Now playing overlay for Meld Studio — Spotify, YouTube, anything.

Reads the Windows media session, so there is **no Spotify developer app, no client ID or
secret, no Premium requirement and no API quota**. Whatever is playing on the machine
shows up.

### Getting started

1. Download the zip below, unzip it and run the exe.
2. Play something.
3. Open <http://127.0.0.1:8752/settings> and click **Add to Meld** — the layer lands in
   your current scene, already named, sized and pointed at the overlay. Meld needs to be
   open when you click it.

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
