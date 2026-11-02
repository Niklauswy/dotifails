.pragma library

// Pure helpers of the LANShare bar popout (services/LanShare.qml); tested with node
// (tests/shell_bridge/test_lanshare_logic.py). A server is the JSON of
// $XDG_RUNTIME_DIR/wysun-lanshare/<pid>.json (apps/python/wysun_lanshare/status.py).

var STALE = 30;   // seconds without a heartbeat (the server writes every 10 s) = dead

function live(list, nowSec) {
    return (list || []).filter(function (s) {
        return s && typeof s.pid === "number" && typeof s.updated === "number" && nowSec - s.updated <= STALE;
    }).sort(function (a, b) {
        return (a.started || 0) - (b.started || 0);
    });
}

function remaining(server, nowSec) {
    var at = server ? server.shutdownAt : null;
    if (at === null || at === undefined)
        return "Sin apagado automático";
    var left = at - nowSec;
    if (left <= 0)
        return (server.transfers || []).length ? "Se apaga al terminar las transferencias" : "Se apaga en un momento";
    if (left < 60)
        return "Se apaga en menos de 1 min";
    var minutes = Math.ceil(left / 60);
    if (minutes < 60)
        return "Se apaga en " + minutes + " min";
    var h = Math.floor(minutes / 60), m = minutes % 60;
    return "Se apaga en " + h + " h" + (m ? " " + m + " min" : "");
}

function people(server) {
    var clients = (server && server.clients) || [];
    if (!clients.length)
        return "Nadie conectado";
    var devices = clients.map(function (c) { return c.device; }).join(" · ");
    return (clients.length === 1 ? "1 persona conectada" : clients.length + " personas conectadas") + " — " + devices;
}

function progress(transfer) {
    if (!transfer || !transfer.total)
        return 0;
    return Math.max(0, Math.min(1, transfer.done / transfer.total));
}

function transferText(transfer) {
    var verb = { up: "Sube", view: "Ve", down: "Descarga" }[transfer.direction] || "Descarga";
    return transfer.device + " · " + verb + " " + transfer.name;
}

function access(server) {
    return server.uploads ? "Subidas permitidas" : "Solo ver y descargar";
}
