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
    // df -P prints one row per filesystem, but tolerate a wrapped device name:
    // the capacity is the last "NN%" followed by the mount point.
    var match = /\s(\d+)%\s+\/\S*\s*$/.exec(rows.slice(1).join(" "));
    return match ? percentage(Number(match[1])) : null;
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

// ---- Inicio: reloj y calendario -------------------------------------------

var MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
var WEEKDAYS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
var WEEKDAY_HEADERS = ["L", "M", "X", "J", "V", "S", "D"];

function pad2(n) { return ("0" + n).slice(-2); }

function validDate(date) {
    return date instanceof Date && isFinite(date.getTime());
}

function clockText(date) {
    return validDate(date) ? pad2(date.getHours()) + ":" + pad2(date.getMinutes()) : "--:--";
}

function dateText(date) {
    if (!validDate(date)) return "";
    return WEEKDAYS[date.getDay()] + " " + date.getDate() + " de " + MONTHS[date.getMonth()];
}

function monthTitle(year, month) {
    return MONTHS[((month % 12) + 12) % 12] + " " + year;
}

// Weeks start on Monday. Always six rows so the card does not change height
// from one month to another.
function monthGrid(year, month, today) {
    var first = new Date(year, month, 1);
    var offset = (first.getDay() + 6) % 7;
    var weeks = [];
    for (var w = 0; w < 6; w++) {
        var row = [];
        for (var d = 0; d < 7; d++) {
            var cell = new Date(year, month, 1 - offset + w * 7 + d);
            row.push({
                day: cell.getDate(),
                inMonth: cell.getMonth() === first.getMonth(),
                today: validDate(today) && cell.getFullYear() === today.getFullYear()
                    && cell.getMonth() === today.getMonth() && cell.getDate() === today.getDate()
            });
        }
        weeks.push(row);
    }
    return weeks;
}

function shiftMonth(year, month, delta) {
    var d = new Date(year, month + delta, 1);
    return { year: d.getFullYear(), month: d.getMonth() };
}

// ---- Rendimiento ---------------------------------------------------------

// "normal" | "warning" | "critical". The caller maps these to theme tokens, so
// no colour is chosen here.
function usageLevel(value) {
    var p = percentage(value);
    if (p === null) return "unknown";
    return p >= 90 ? "critical" : (p >= 75 ? "warning" : "normal");
}

function arcSweep(value, span) {
    var p = percentage(value);
    return p === null ? 0 : (span === undefined ? 270 : span) * p / 100;
}

// One line per reading, produced by Metrics.qml's read-only sysfs script:
//   T <hwmon name> <millidegrees>     G <percent busy>
// Absent sensors simply do not appear, and the result then holds nulls.
function parseSensors(text) {
    var result = { cpuTemperature: null, gpuTemperature: null, gpu: null };
    var cpuNames = ["coretemp", "k10temp", "zenpower", "cpu_thermal", "x86_pkg_temp"];
    var gpuNames = ["amdgpu", "nouveau", "radeon"];
    String(text || "").split("\n").forEach(function(line) {
        var f = line.trim().split(/\s+/);
        if (f[0] === "T" && f.length >= 3) {
            var milli = Number(f[2]);
            if (!isFinite(milli) || milli <= 0 || milli > 150000) return;
            var celsius = milli / 1000;
            if (cpuNames.indexOf(f[1]) >= 0 && result.cpuTemperature === null) result.cpuTemperature = celsius;
            else if (gpuNames.indexOf(f[1]) >= 0 && result.gpuTemperature === null) result.gpuTemperature = celsius;
        } else if (f[0] === "G" && f.length >= 2 && result.gpu === null) {
            result.gpu = percentage(Number(f[1]));
        }
    });
    return result;
}

// ---- Música --------------------------------------------------------------

function progressFraction(position, length) {
    if (typeof position !== "number" || typeof length !== "number" || !isFinite(position) || !isFinite(length) || length <= 0) return 0;
    return Math.max(0, Math.min(1, position / length));
}

function playerLabel(player) {
    return (player && (player.identity || player.desktopEntry)) || "Reproductor";
}

// ---- Escritorios ---------------------------------------------------------

function windowTitle(window) {
    return (window && (window.title || window.appId || window.class)) || "Ventana sin título";
}

// Windows of one desktop. Hyprland exposes the workspace on the toplevel's
// lastIpcObject as well, which is used when the object has no direct link.
function windowsOfDesktop(windows, workspace) {
    if (!workspace) return [];
    return (windows || []).filter(function(w) {
        if (!w) return false;
        var id = w.workspace ? w.workspace.id : (w.lastIpcObject && w.lastIpcObject.workspace ? w.lastIpcObject.workspace.id : undefined);
        return id === workspace.id;
    });
}

function clampTab(index, count) {
    var i = Math.round(Number(index));
    return isFinite(i) ? Math.max(0, Math.min(count - 1, i)) : 0;
}
