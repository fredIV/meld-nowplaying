# meld-spotify

Now-playing overlay for [Meld Studio](https://meldstudio.co/).

Reads Windows' own media session data (SMTC) — the same info the media flyout
shows — so there is **no Spotify developer app, no client secret, no Premium
requirement, and no API quota**. Works with the Spotify desktop app out of the
box, and with any other player if you want it to.

## Setup

1. Double-click **`start.bat`**. First run creates a virtualenv and installs the
   packages it needs; after that it just starts.
2. Play something in Spotify.
3. In Meld Studio, add a **Web** layer and set its URL to:

   ```
   http://127.0.0.1:8752/
   ```

4. Size the layer (see below) and position it. Done.

To start it with Windows, run **`install-autostart.bat`** once
(`uninstall-autostart.bat` undoes it). `start-hidden.vbs` runs it with no
console window; `stop.bat` stops it.

## Layouts

Set `"layout"` in `config.json`. Suggested Meld layer sizes:

| layout | what it is | size |
|---|---|---|
| `bar` | album art + title/artist + thin progress bar | 380 × 90 |
| `card` | bigger art, album line, elapsed/total times | 420 × 140 |
| `text` | one line, `Title — Artist`, no art | 480 × 40 |
| `vertical` | stacked art over centred text, for vertical canvases | 240 × 320 |

On every track change the card briefly expands (album line + timestamps) and
then settles back — set `"popin_seconds": 0` to turn that off.

## Config

`config.json`:

| key | default | what it does |
|---|---|---|
| `port` | `8752` | HTTP port |
| `poll_interval` | `0.5` | seconds between SMTC reads |
| `source_filter` | `"spotify"` | substring match on the player's app id. `""` = whatever is playing (browser, VLC, Apple Music…) |
| `hide_when_paused` | `false` | fade out while paused |
| `layout` | `"bar"` | see the table above |
| `popin_seconds` | `6` | expanded card duration on track change; `0` disables |
| `blurred_art_background` | `true` | album art blurred behind the card |
| `write_text_file` | `true` | write `nowplaying.txt` / `.json` / `art.png` beside the script |
| `text_file_format` | `"{title} - {artist}"` | tokens: `{title}` `{artist}` `{album}` |

Restart the server after editing.

## Files for other tools

With `write_text_file` on, the folder always holds the current track:

- `nowplaying.txt` — one line, your format. Point **Streamer.bot** at it for a
  `!song` command, or read it from any tool that can watch a text file.
- `nowplaying.json` — the full state (title, artist, album, position, duration).
- `art.png` — current album art, replaced on every track change (`art.jpg` if
  Windows hands back a JPEG instead).

Empty file = nothing playing.

## Meld WebChannel link (optional)

Meld exposes a control API at `ws://127.0.0.1:13376`. **Two things have to be
true before anything can connect:**

1. In Meld: *Preferences → Advanced → WebSocket Server → Allow remote
   connections* must be **on**. Despite the name, nothing can reach the API
   locally until this is enabled.
2. **Restart Meld after enabling it.** The socket only starts listening on the
   next launch.

Then turn the link on in the `meld` block of `config.json` and the server will
drive Meld directly:

```json
"meld": {
  "enabled": true,
  "url": "ws://127.0.0.1:13376",
  "layer_name": "Now Playing",
  "auto_set_url": true,
  "hide_between_songs": true,
  "mute_aware_track": "Spotify",
  "stream_event_on_track_change": { "type": "confetti", "data": {} }
}
```

| key | what it does |
|---|---|
| `layer_name` | the Meld **Web layer** to control — name it exactly this in Meld |
| `auto_set_url` | points that layer at the overlay for you, so you never paste a URL |
| `hide_between_songs` | shows the layer when a track is playing, hides it when nothing is |
| `mute_aware_track` | name of a Meld audio track — while it is muted, the overlay hides |
| `stream_event_on_track_change` | fires a Meld stream event on every new track; `null` to disable |

If Meld isn't running the link just retries quietly in the background. The
overlay works fine without any of this.

## Styling

Everything visual lives in the `:root` block at the top of `overlay.html` —
width, art size, colors, fonts, radius, progress-bar color, blur strength, and
how strong the blurred-art background is. Per-layout overrides sit right below
it. Edit and refresh the Meld layer; no restart needed.

Long titles scroll automatically. The card fades out when nothing is playing.

## Endpoints

| path | purpose |
|---|---|
| `/` | the overlay |
| `/events` | server-sent events, pushed on change |
| `/state` | current state as JSON |
| `/config` | display settings the overlay reads at load |
| `/art` | album art bytes for the current track |
| `/diag` | Meld link status: connected, methods, session size, layer found |

## Troubleshooting

**Nothing shows up.** Open <http://127.0.0.1:8752/state>. If `title` is empty,
Windows isn't reporting a session — make sure Spotify is actually playing, not
just open. If the browser shows the track but Meld doesn't, re-check the layer
URL and that the layer is big enough.

**Wrong player picked up.** Check the `app` field in `/state` and put a matching
substring in `source_filter`. The Store build of Spotify reports something like
`SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify`; the desktop installer reports
`Spotify.exe`. `"spotify"` matches both.

**No album art.** Some players don't publish a thumbnail. The overlay drops the
art and shows text only.

**Meld link never connects.** Check the two prerequisites above first — the
"Allow remote connections" toggle *and* a Meld restart. Then open
<http://127.0.0.1:8752/diag>: it reports whether the link is up, how many
session items it can see, and whether your `layer_name` was found. The layer
name must match exactly.

**Port already in use.** Change `port` in `config.json` and update the layer URL.
