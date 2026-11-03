.pragma library

// Pure helpers of the window tools that Wysun Processes asks the shell for (services/WindowTools.qml): window
// thumbnails and locate-on-screen. Tested with node (tests/shell_bridge/test_window_tools.py).

var MAX_THUMBS = 24;

// "0xaa,0xBB,…" -> ["aa", "bb"]: valid hex addresses only, lower case, without 0x, no repeats, at most 24.
function parseAddresses(text) {
    var out = [];
    String(text || "").split(",").forEach(function (part) {
        var m = /^\s*(?:0x)?([0-9a-fA-F]+)\s*$/.exec(part);
        if (m && out.indexOf(m[1].toLowerCase()) < 0 && out.length < MAX_THUMBS)
            out.push(m[1].toLowerCase());
    });
    return out;
}

function sameAddress(a, b) {
    var strip = function (v) { return String(v || "").toLowerCase().replace(/^0x/, ""); };
    return strip(a) !== "" && strip(a) === strip(b);
}

// Where the halo goes on `screen` ({name, activeWs}) for a window ({at, size}) on `monitor`
// ({name, x, y, width, height}) and workspace `ws`: hidden unless that screen shows that workspace.
function placement(win, monitor, screen, ws) {
    if (!win || !monitor || !screen || monitor.name !== screen.name || screen.activeWs !== ws)
        return {visible: false, x: 0, y: 0, width: 0, height: 0};
    return {visible: true, x: win.at[0] - monitor.x, y: win.at[1] - monitor.y, width: win.size[0], height: win.size[1]};
}

function elsewhere(name, ws) {
    return (name || "La ventana") + " está en el espacio " + ws;
}

function thumbPath(runtimeDir, address) {
    return runtimeDir + "/wysun-processes/thumbs/" + String(address).toLowerCase().replace(/^0x/, "") + ".png";
}
