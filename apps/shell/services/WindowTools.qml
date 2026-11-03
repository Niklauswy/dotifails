pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Hyprland
import "WindowToolsLogic.js" as Logic

// Window tools for Wysun Processes: locate a window on screen (a pulsing halo in the accent colour, the rest dimmed;
// a capsule when it is on another workspace) and thumbnails of windows, captured by the shell (ScreencopyView) into
// $XDG_RUNTIME_DIR/wysun-processes/thumbs and never anywhere else. modules/windowtools draws and captures; `alive`
// keeps its windows only while something is showing or thumbnails were asked for recently.
Singleton {
    id: root

    readonly property string runtimeDir: Quickshell.env("XDG_RUNTIME_DIR") || "/tmp"
    property bool showing
    property bool alive: showing || capturing
    property bool capturing
    property var target: null                 // the HyprlandToplevel being located
    property string targetLabel
    property var thumbs: ({})                 // address (no 0x) -> path, written this session
    property var pending: []                  // addresses (no 0x) to capture
    property int generation: 0

    function toplevel(address) {
        const list = Hyprland.toplevels.values;
        for (let i = 0; i < list.length; i++)
            if (Logic.sameAddress(list[i].address, address))
                return list[i];
        return null;
    }

    function locate(address): bool {
        const t = toplevel(address);
        if (!t)
            return false;
        target = t;
        targetLabel = t.lastIpcObject?.title ?? "";
        showing = true;
        hide.restart();
        return true;
    }

    function dismiss(): void {
        showing = false;
    }

    function focusTarget(): void {
        if (target)
            Hyprland.dispatch("focuswindow address:0x" + String(target.address).replace(/^0x/, ""));
        showing = false;
    }

    // Returns the thumbnails already written (JSON {"0x…": path}) and asks for fresh ones of `text`'s windows.
    function requestThumbs(text): string {
        const wanted = Logic.parseAddresses(text).filter(a => toplevel(a) !== null);
        const out = {};
        for (const a of wanted)
            if (thumbs[a])
                out["0x" + a] = thumbs[a];
        pending = wanted;
        generation++;
        capturing = wanted.length > 0;
        idle.restart();
        return JSON.stringify(out);
    }

    function captured(address, path): void {
        const next = Object.assign({}, thumbs);
        next[address] = path;
        thumbs = next;
    }

    Timer {
        id: hide

        interval: 2600
        onTriggered: root.showing = false
    }

    Timer {
        id: idle

        interval: 12000
        onTriggered: root.capturing = false
    }
}
