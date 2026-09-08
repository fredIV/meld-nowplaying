# meld-nowplaying

Now playing overlay for [Meld Studio](https://meldstudio.co/) — Spotify, YouTube, anything.

It reads Windows' own media session (the same data behind the media flyout), so there is
**no Spotify developer app, no client ID or secret, no Premium requirement and no API
quota**. Whatever is playing on the machine shows up: the Spotify app, a YouTube tab,
Apple Music, VLC.

Four layouts, live track progress, album art, and an optional link that drives Meld
directly so you never paste a URL.

---

## Quick start

1. Download `meld-nowplaying.exe` from [Releases](../../releases) and put it anywhere.
2. Run it. A console window opens and stays open while the overlay is running.
3. Play something.
4. Click **Add to Meld** on the settings page it prints
   (<http://127.0.0.1:8752/settings>) — that drops a correctly sized layer straight into
   your current scene.

That's it. No URL to copy, no layer to size by hand.

<details>
<summary>Running from source instead</summary>

Needs Python 3.10+. Double-click `start.bat` — first run makes a virtualenv and installs
the packages it needs, after that it just starts.

</details>

## Settings

Everything is configurable at <http://127.0.0.1:8752/settings> — layout, pop-in,
album-art background, which player to follow, the output files and the Meld link.
Display settings apply as soon as you save.

If you would rather edit a file, it is all in `config.json` next to the executable.

## Layouts

| layout | what it is | layer size |
|---|---|---|
| `bar` | album art, title, artist, thin progress bar | 380 × 120 |
| `card` | bigger art, album line, elapsed / total | 420 × 140 |
| `text` | one line, `Title — Artist`, no art | 480 × 44 |
| `vertical` | stacked art over centred text | 240 × 344 |

On every track change the card briefly expands and then settles back — the sizes above
leave room for that, so nothing gets clipped. Set pop-in to `0` to turn it off.

You can also override the layout per layer with a query string, so several Meld layers
can share one server:

```
http://127.0.0.1:8752/?layout=card
http://127.0.0.1:8752/?layout=text&popin=0
http://127.0.0.1:8752/?layout=vertical&artbg=0
```

## Files for other tools

While it runs, the folder always holds the current track:

- `nowplaying.txt` — one line in your format. Point **Streamer.bot** at it for a `!song`
  command, or read it from anything that can watch a text file.
- `nowplaying.json` — full state: title, artist, album, position, duration.
- `art.png` — current album art, replaced on every track change.

Empty file means nothing is playing.

## Driving Meld directly (optional)

Meld exposes a control API on `ws://127.0.0.1:13376`. With the link switched on, the
overlay can point its own layer at itself, hide the layer between songs, hide it while a
chosen audio track is muted, and fire a Meld stream event when the track changes.

**Two things have to be true before anything can connect:**

1. In Meld: *Preferences → Advanced → WebSocket Server → **Allow remote connections*** must
   be on. Despite the name, nothing reaches the API locally until this is enabled.
2. **Restart Meld.** The socket only starts listening on the next launch.

Then turn the link on in the settings page, or in `config.json`:

```json
"meld": {
  "enabled": true,
  "url": "ws://127.0.0.1:13376",
  "layer_name": "Now Playing",
  "auto_set_url": true,
  "hide_between_songs": true,
  "mute_aware_track": "Spotify",
  "stream_event_on_track_change": null
}
```

| key | what it does |
|---|---|
| `layer_name` | the Meld layer this controls — must match the layer name exactly |
| `auto_set_url` | points that layer at the overlay for you |
| `hide_between_songs` | shows the layer while something is playing, hides it when nothing is |
| `mute_aware_track` | name of a Meld mixer track; while it is muted, the overlay hides |
| `stream_event_on_track_change` | e.g. `{"type": "confetti", "data": {}}`; `null` to disable |

If Meld isn't running the link retries quietly in the background. Everything else works
without it.

## Styling

All of it lives in the `:root` block at the top of `overlay.html` — width, art size,
colours, fonts, corner radius, progress bar colour, blur strength, how strong the blurred
album art behind the card is. Per-layout overrides sit right below. Edit, refresh the
layer, done.

Long titles scroll. The card fades out when nothing is playing.

## Start with Windows

Run `install-autostart.bat` once. `uninstall-autostart.bat` undoes it.
`start-hidden.vbs` runs the server with no console window; `stop.bat` stops it.

## Endpoints

| path | purpose |
|---|---|
| `/` | the overlay |
| `/settings` | settings page |
| `/events` | server-sent events, pushed on change |
| `/state` | current track as JSON |
| `/diag` | Meld link status; `?layer=NAME` dumps that layer |
| `/art` | album art bytes |

The server binds `127.0.0.1` only — nothing is exposed to your network.

## Troubleshooting

**Nothing shows up.** Open <http://127.0.0.1:8752/state>. If `title` is empty, Windows
isn't reporting a session — make sure the player is actually playing, not just open.

**Wrong player.** Check the `app` field in `/state` and put a matching substring in
*Only follow this player*. The Store build of Spotify reports
`SpotifyAB.SpotifyMusic_…!Spotify`, the desktop installer reports `Spotify.exe`, and
`spotify` matches both. Leave it empty to follow whatever is playing.

**No album art.** Some players don't publish a thumbnail; the overlay drops the art and
shows text only.

**Meld link won't connect.** Check the two prerequisites above first — the toggle *and* a
Meld restart. Then open <http://127.0.0.1:8752/diag>.

**Port already in use.** Change the port in settings and re-add the layer.

## Building the executable

```
build-exe.bat
```

PyInstaller one-file build; the result lands in `dist\meld-nowplaying.exe`.

## Licence

MIT — see [LICENSE](LICENSE).
