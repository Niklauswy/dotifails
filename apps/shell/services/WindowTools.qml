pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Hyprland
import Wysun
import "WindowToolsLogic.js" as Logic

// Window tools for Wysun Processes: locate a window on screen (a pulsing halo in the accent colour, the rest dimmed;
// on another workspace the compositor is asked to focus it first) and thumbnails of windows, captured by the shell
// (ScreencopyView) into $XDG_RUNTIME_DIR/wysun-processes/thumbs and never anywhere else. modules/windowtools draws
// and captures; `alive` keeps its windows only while something is showing or thumbnails were asked for recently.
Singleton {
    id: root

    readonly property string runtimeDir: Quickshell.env("XDG_RUNTIME_DIR") || "/tmp"
    property bool showing
    property bool alive: showing || capturing
    property bool capturing
    property var target: null                 // the HyprlandToplevel being located
    property var thumbs: ({})                 // "<address>@<width>" -> path, written this session
    property var stale: ({})                  // "<address>@<width>" -> the previous path, kept one capture
    property var pending: []                  // addresses (no 0x) to capture at `pendingWidth`
    property int pendingWidth: 480            // device pixels of the requested capture (Logic clamps it)
    property int generation: 0

    function toplevel(address) {
        const list = Hyprland.toplevels.values;
        for (let i = 0; i < list.length; i++)
            if (Logic.sameAddress(list[i].address, address))
                return list[i];
        return null;
    }

    function locate(address): bool {
        const t = toplevel(Logic.singleAddress(address));
        if (!t)
            return false;
        target = t;
        // On another workspace (or a monitor showing another one) the halo cannot be drawn until the window is
        // visible: focus it first with the session's dispatch syntax, then show the halo on it.
        const monitor = t.monitor;
        if (Logic.needsFocus(t.workspace?.id ?? -1,
                            monitor ? {activeWorkspace: monitor.activeWorkspace?.id ?? -1} : null))
            focusTarget();
        showing = true;
        hide.restart();
        return true;
    }

    function dismiss(): void {
        showing = false;
    }

    function focusTarget(): void {
        if (!target)
            return;
        const address = "0x" + String(target.address).replace(/^0x/, "");
        Hypr.dispatch(Hypr.usingLua ? `hl.dsp.focus({window="address:${address}"})` : `focuswindow address:${address}`);
    }

    // The ShellScreen of a Hyprland monitor, needed because popouts are per screen.
    function screenForMonitor(monitor): ShellScreen {
        if (!monitor)
            return null;
        return Quickshell.screens.find(s => Hypr.monitorFor(s)?.name === monitor.name) ?? null;
    }

    // The screen whose shell can host the window panel: the monitor of Wysun Processes, else the focused one, but
    // restricted to the screens Drawers is built for (Screens.widgetScreens). With widget mode «primary» the bar
    // and its popouts exist only on the primary screen, wherever the focus or the Processes window is. The
    // window's Wayland app id is `wysun-processes` (window.py sets it before mapping).
    function barScreen(): ShellScreen {
        const own = Hyprland.toplevels.values.find(t => t.lastIpcObject?.class === "wysun-processes");
        return Logic.screenWithDrawers(Screens.widgetScreens,
                                       screenForMonitor(own?.monitor) ?? screenForMonitor(Hypr.focusedMonitor));
    }

    // Opens the bar's detached «winfo» (live preview + details) for one window, on the screen that has the bar.
    function windowInfo(address): bool {
        const t = toplevel(Logic.singleAddress(address));
        if (!t)
            return false;
        const popouts = ShellState.componentsFor(barScreen())?.panels?.popouts ?? null;
        if (!popouts)
            return false;
        popouts.openWinfo(t);
        return true;
    }

    // Returns the thumbnails already written at `width` (JSON {"0x…": path}) and asks for fresh ones of `text`'s
    // windows. Width is optional: 480 px unless the caller asks for another size (clamped by Logic).
    function requestThumbs(text, width): string {
        const pixels = Logic.thumbWidth(width);
        const wanted = Logic.parseAddresses(text).filter(a => toplevel(a) !== null);
        const out = {};
        for (const a of wanted) {
            const path = thumbs[Logic.thumbKey(a, pixels)];
            if (path)
                out["0x" + a] = path;
        }
        pending = wanted;
        pendingWidth = pixels;
        generation++;
        capturing = wanted.length > 0;
        idle.restart();
        return JSON.stringify(out);
    }

    function captured(address, width, path): void {
        const key = Logic.thumbKey(address, width);
        const previous = thumbs[key];
        const older = stale[key];
        const next = Object.assign({}, thumbs);
        next[key] = path;
        thumbs = next;
        const aged = Object.assign({}, stale);
        aged[key] = previous;
        stale = aged;
        // Each capture is a new file (thumbPath's generation), so the previous one stays readable while the app
        // switches to the new URL. Keep one spare and remove the file from two captures ago.
        if (older && older !== previous && older !== path)
            CUtils.deleteFile(Qt.resolvedUrl(older));
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
