.pragma library

// Pure helpers of the Wysun update notice (services/WysunUpdate.qml); tested with node
// (tests/test_shell_update_notice.py). The state is the JSON of
// $XDG_STATE_HOME/wysun/update.json, written (and printed) by `wysun update --check`:
// {checked, source, branch, local, remote, behind, available, error}.

function empty() {
    return { available: false, behind: 0, checked: "", branch: "main", error: "" };
}

// Never trusts the file: available is true only with new commits and no error.
function parse(text) {
    var state = empty();
    if (text === null || text === undefined)
        return state;
    var body = String(text).trim();
    if (!body)
        return state;
    var raw;
    try {
        raw = JSON.parse(body);
    } catch (error) {
        state.error = "No se pudo leer el estado de actualización";
        return state;
    }
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
        state.error = "No se pudo leer el estado de actualización";
        return state;
    }
    var behind = Math.floor(Number(raw.behind));
    state.behind = isFinite(behind) && behind > 0 ? behind : 0;
    state.checked = typeof raw.checked === "string" ? raw.checked : "";
    state.branch = typeof raw.branch === "string" && raw.branch ? raw.branch : "main";
    state.error = typeof raw.error === "string" ? raw.error : "";
    state.available = raw.available === true && state.behind > 0 && !state.error;
    return state;
}

function changes(behind, branch) {
    var count = Math.floor(Number(behind));
    if (!isFinite(count) || count <= 0)
        return "No hay cambios nuevos en " + (branch || "main");
    var name = count === 1 ? "cambio nuevo" : "cambios nuevos";
    return count + " " + name + " en " + (branch || "main");
}

// "Comprobado hace …" for the last `wysun update --check`.
function ago(checked, nowMs) {
    if (!checked || isNaN(Date.parse(checked)))
        return "Sin comprobar";
    var now = nowMs === undefined || nowMs === null ? Date.now() : nowMs;
    var seconds = Math.max(0, Math.floor((now - Date.parse(checked)) / 1000));
    if (seconds < 60)
        return "Comprobado hace un momento";
    var minutes = Math.floor(seconds / 60);
    if (minutes < 60)
        return "Comprobado hace " + minutes + " min";
    var hours = Math.floor(minutes / 60);
    if (hours < 24) {
        var rest = minutes % 60;
        return "Comprobado hace " + hours + " h" + (rest ? " " + rest + " min" : "");
    }
    var days = Math.floor(hours / 24);
    return "Comprobado hace " + days + (days === 1 ? " día" : " días");
}
