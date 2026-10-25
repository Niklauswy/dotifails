pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io

// Opens a file in Neovim, with the launcher turning into the editor. The terminal is an ordinary tiled window
// (class `wysun.edit`); a Hyprland rule maps it without animation and fully transparent, so it takes its place in
// the layout unseen. EditMorph.qml draws the choreography:
//   1. the launcher becomes the editor where it stands: its contents dissolve, its surface takes the terminal's
//      colour and corners, and the previewed code moves to where Neovim draws it, in the terminal's font;
//   2. once the window exists, that editor-looking panel flies in one motion onto the window's real tile;
//   3. the window is made visible under it and the panel dissolves into it.
Singleton {
    id: root

    readonly property string windowClass: "wysun.edit"
    readonly property int flight: 420
    // Phase 1 gets this long on screen before the flight may start, so the launcher visibly becomes the editor.
    readonly property int settle: 300
    property real openedAt

    property bool active
    // Phase 1 (the launcher becoming the editor) runs as soon as it opens.
    property bool morphed
    property bool flying
    property bool ready
    property string screenName
    property var screenRef: null
    property string address
    // `from`: the previewed code's rectangle; `panel*`: the whole launcher surface it lives in, and its snapshot.
    property rect from
    property rect panelRect
    property color panelColour
    property real panelRadius
    property string snapshot
    property var snapshotImage: null
    property rect tile
    property color bg
    property string title
    property var known: []
    property string codeHtml
    property string codeText
    property color codeFg
    property color codeLineNr
    property real textScale: 1

    // How the terminal looks, so the card lands looking like it (ghostty's config; foot falls back to these).
    property string termFont: "monospace"
    property real termPx: 22
    property color termBg: "#101012" // theme-exception: ghostty's own background, overwritten from its config
    property real termAlpha: 1
    property real termPad: 10

    function editors(): var {
        return Hyprland.toplevels.values.filter(t => (t.lastIpcObject?.class ?? "") === windowClass);
    }

    // The new window's tile: its global position minus the screen's origin. The screen's own geometry is used
    // (the monitor's IPC object can still be empty right after the shell starts). -> whether the tile is known.
    function followWindow(): bool {
        const win = editors().find(t => !known.includes(t.address));
        const o = win?.lastIpcObject;
        if (win)
            address = win.address;
        if (!o?.at || !o?.size || !screenRef)
            return false;
        tile = Qt.rect(o.at[0] - screenRef.x, o.at[1] - screenRef.y, o.size[0], o.size[1]);
        return true;
    }

    // A window that opened on another screen cannot be flown to from this one: the panel dissolves in place.
    function tileOnScreen(): bool {
        const cx = tile.x + tile.width / 2, cy = tile.y + tile.height / 2;
        return cx >= 0 && cy >= 0 && cx <= screenRef.width && cy <= screenRef.height;
    }

    // The rule hides the window in every state (focused, unfocused, fullscreen): all three come back, or the
    // editor would vanish again as soon as it lost focus.
    function show(addr: string): void {
        const a = addr.startsWith("0x") ? addr : "0x" + addr;
        for (const prop of ["opacity", "opacity_inactive", "opacity_fullscreen"])
            Hyprland.dispatch(`hl.dsp.window.set_prop({ window = "address:${a}", prop = "${prop}", value = "1 override" })`);
    }

    // `panelRect`: the rectangle the card starts from (the launcher's preview). `style` (optional) is that preview's
    // Neovim-coloured text {html, text, fg, lineNr, transparent, scale}; without it (IPC) it is fetched.
    // `panel` (optional): {rect, colour, radius, snapshot, image} of the launcher surface around the preview.
    function open(screen: var, codeRect: rect, background: color, path: string, style: var, panel: var): void {
        // A hand-over still running (a second file opened quickly) ends now: its window is shown as it is.
        if (active) {
            reveal();
            finish.stop();
            active = false;
        }
        screenName = screen.name;
        screenRef = screen;
        from = codeRect;
        panelRect = panel?.rect ?? codeRect;
        panelColour = panel?.colour ?? background;
        panelRadius = panel?.radius ?? 16;
        snapshot = panel?.snapshot ?? "";
        snapshotImage = panel?.image ?? null;
        tile = panelRect;
        address = "";
        bg = background;
        title = path.slice(path.lastIndexOf("/") + 1);
        codeHtml = style?.html ?? "";
        codeText = style?.text ?? "";
        codeFg = style?.fg ?? "white";
        codeLineNr = style?.lineNr ?? "gray";
        textScale = style?.scale ?? 1;
        styleProc.running = false;
        if (!style) {
            styleProc.command = LauncherData.codePreview(path);
            styleProc.running = true;
        }
        known = editors().map(t => t.address);
        flying = false;
        ready = false;
        morphed = false;
        openedAt = Date.now();
        active = true;
        Qt.callLater(() => morphed = true);
        Quickshell.execDetached(["sh", "-c", 'if command -v ghostty >/dev/null 2>&1; then exec ghostty --class=wysun.edit -e nvim "$1"; else exec foot --app-id=wysun.edit nvim "$1"; fi', "sh", path]);
        poll.restart();
        giveUp.restart();
    }

    // The window is in place (or never came): make it visible and let the card dissolve into it.
    function reveal(): void {
        poll.stop();
        giveUp.stop();
        follow.stop();
        if (address)
            show(address);
        ready = true;
        finish.restart();
    }

    // A shell restart in the middle of a hand-over must not leave an editor invisible.
    Component.onCompleted: Qt.callLater(() => editors().forEach(t => show(t.address)))

    FileView {
        path: `${Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME") + "/.config"}/ghostty/config`
        printErrors: false
        onLoaded: {
            const value = key => (text().match(new RegExp(`^\\s*${key}\\s*=\\s*"?([^"\\n]*?)"?\\s*$`, "m")) ?? [])[1];
            const font = value("font-family"), size = parseFloat(value("font-size")), back = value("background");
            const alpha = parseFloat(value("background-opacity")), pad = parseFloat(value("window-padding-x"));
            if (font)
                root.termFont = font;
            if (size > 0)
                root.termPx = size * 4 / 3;
            if (/^#?[0-9a-fA-F]{6}$/.test(back ?? ""))
                root.termBg = back.startsWith("#") ? back : "#" + back;
            if (alpha >= 0 && alpha <= 1)
                root.termAlpha = alpha;
            if (pad >= 0)
                root.termPad = pad;
        }
    }

    Process {
        id: styleProc

        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const d = JSON.parse(text);
                    if (!d.html || !root.active)
                        return;
                    root.codeFg = d.fg;
                    root.codeLineNr = d.lineNr;
                    root.codeText = d.text;
                    root.codeHtml = d.html;
                } catch (e) {}
            }
        }
    }

    // Waits for the terminal's window, then starts the flight towards it.
    Timer {
        id: poll

        interval: 30
        repeat: true
        onTriggered: {
            Hyprland.refreshToplevels();
            const win = root.editors().find(t => !root.known.includes(t.address));
            if (!win)
                return;
            // Its geometry arrives with the next refresh: fly only towards a known tile.
            if (!root.followWindow() || Date.now() - root.openedAt < root.settle)
                return;
            poll.stop();
            if (!root.tileOnScreen()) {
                root.reveal();
                return;
            }
            root.flying = true;
            follow.restart();
            land.restart();
        }
    }

    // Neighbouring windows make room while the card flies: keep aiming at where the tile really ends up.
    Timer {
        id: follow

        interval: 40
        repeat: true
        onTriggered: {
            Hyprland.refreshToplevels();
            root.followWindow();
        }
    }

    Timer {
        id: land

        interval: root.flight
        onTriggered: root.reveal()
    }

    Timer {
        id: giveUp

        interval: 5000
        onTriggered: root.reveal()
    }

    Timer {
        id: finish

        interval: 260
        onTriggered: {
            root.active = false;
            root.flying = false;
            root.morphed = false;
            root.snapshot = "";
            root.snapshotImage = null;
        }
    }
}
