.pragma library

// Pure helpers of Super+Shift+Esc (services/ForceQuit.qml, modules/forcequit): which windows may be killed and the
// question. Tested with node (tests/shell_bridge/test_forcequit.py).

var PROTECTED = /^(quickshell|hyprland|xwaylandvideobridge|wysun-shell|wysun)$/i;

function canForceQuit(win) {
    return !!win && !!win.cls && !PROTECTED.test(String(win.cls)) && Number(win.pid) > 1;
}

function question(name) {
    return "¿Forzar el cierre de " + (name || "esta ventana") + "?";
}
