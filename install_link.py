"""
Build a meld:// "add this layer to Meld" link.

Meld's own widget page uses these links for its drag-and-drop widgets:
    meld://action/paste?mime-type=application/json&data=<url-encoded layer json>
Opening one pastes the layer straight into the current scene.

Verified against Meld 0.10.6: this creates a Browser layer with the URL, size
and name already set, and no audio track attached.

Usage:
    python install_link.py [--port 8752] [--layout bar]
"""

import argparse
import json
import urllib.parse

LAYOUTS = {
    "bar": (380, 90),
    "card": (420, 140),
    "text": (480, 40),
    "vertical": (240, 320),
}

META = {
    "pluginName": "MeldStudio",
    "pluginPath": "qrc:/Meld/SceneEditor/Plugins/MeldStudio/plugin_MeldStudio.qml",
}


def build(port=8752, layout="bar", name="Now Playing", kind="browser", url=None):
    width, height = LAYOUTS.get(layout, LAYOUTS["bar"])
    url = url or f"http://127.0.0.1:{port}/"
    if layout != "bar":
        url += f"?layout={layout}"

    layer = {
        # the overlay is silent; keep it out of the mix by default
        "audioTrack": {
            "associatedAudioNodes": [], "delay": 0, "enabled": False,
            "excludedFromVOD": False, "gain": 1, "global": False,
            "monitoring": False, "muted": True, "type": 0, "version": 2,
        },
        "clip": True,
        "effects": [],
        "fitmentMode": 2,
        "forceHideViewportViews": False,
        "hasLoadedSourcePreviously": True,
        "height": height,
        "isLocked": False,
        "keepAspectRatio": False,
        "meta": dict(META),
        "name": name,
        "offsetX": 0, "offsetY": 0, "opacity": 1,
        "radii": {"bottomLeft": 0, "bottomRight": 0, "topLeft": 0, "topRight": 0},
        "rotation": 0, "scaleX": 1, "scaleY": 1, "visible": True,
        "width": width, "x": 0, "y": 0,
    }
    if kind == "widget":
        layer["meta"]["sceneObjectSourceName"] = "MeldStudio/Widget"
        layer["widgetSource"] = url
    else:
        layer["meta"]["sceneObjectSourceName"] = "MeldStudio/Browser"
        layer["url"] = url

    payload = {"app": "meld", "action": "paste-selection", "data": [layer]}
    data = urllib.parse.quote(json.dumps(payload, separators=(",", ":")), safe="")
    return f"meld://action/paste?mime-type=application%2Fjson&data={data}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8752)
    ap.add_argument("--layout", default="bar", choices=sorted(LAYOUTS))
    ap.add_argument("--name", default="Now Playing")
    ap.add_argument("--kind", default="browser", choices=["browser", "widget"])
    ap.add_argument("--url", default=None)
    args = ap.parse_args()
    print(build(args.port, args.layout, args.name, args.kind, args.url))
