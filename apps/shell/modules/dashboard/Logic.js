// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/Content.qml; services/Players.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
.pragma library

// Pure helpers shared by the dashboard QML and its Node contract tests. Every
// provider is optional: a missing sample is null and the UI says
// "No disponible" instead of drawing an invented zero.

function percentage(value) {
    return typeof value === "number" && isFinite(value) && value >= 0 ? Math.min(100, value) : null;
}

function percentText(value) {
    var p = percentage(value);
    return p === null ? "No disponible" : Math.round(p) + "%";
}

function storagePercent(text) {
    var rows = String(text || "").trim().split(/\n/);
    if (rows.length < 2) return null;
    // df -Pk may wrap a long device name; the last line is always the data row.
    var fields = rows[rows.length - 1].trim().split(/\s+/);
    if (fields.length < 6 || !/^\d+%$/.test(fields[4])) return null;
    return percentage(Number(fields[4].slice(0, -1)));
}

function activePlayer(players, manual, previous) {
    var list = players || [];
    if (list.indexOf(manual) >= 0) return manual;
    var playing = list.filter(function(p) { return p && p.isPlaying; });
    if (playing.indexOf(previous) >= 0) return previous;
    return playing[0] || (list.indexOf(previous) >= 0 ? previous : list[0]) || null;
}

function localArtwork(url) {
    // Offline only. No YouTube thumbnails, remote artwork or metadata lookup.
    return typeof url === "string" && /^file:\/\//.test(url) ? url : "";
}

function timestamp(seconds) {
    if (typeof seconds !== "number" || !isFinite(seconds) || seconds < 0) return "—";
    return Math.floor(seconds / 60) + ":" + ("0" + Math.floor(seconds % 60)).slice(-2);
}

function temperatureText(value) {
    return typeof value === "number" && isFinite(value) ? Math.round(value) + " °C" : "Temperatura: no disponible";
}

function monitorNameOf(workspace) {
    var monitor = workspace ? workspace.monitor : null;
    if (!monitor) return "";
    return typeof monitor === "string" ? monitor : (monitor.name || "");
}

function desktops(workspaces, monitorName) {
    return (workspaces || []).filter(function(w) {
        return w && !String(w.name || "").startsWith("special:") && (!monitorName || monitorNameOf(w) === monitorName);
    }).slice().sort(function(a, b) {
        var na = Number(a.id), nb = Number(b.id);
        if (isFinite(na) && isFinite(nb) && na !== nb) return na - nb;
        return String(a.name || "").localeCompare(String(b.name || ""));
    });
}

function windowsIn(windows, workspace) {
    if (!workspace) return [];
    return (windows || []).filter(function(w) { return w && w.workspace && w.workspace.id === workspace.id; });
}
