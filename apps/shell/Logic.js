.pragma library

// Pure data transformations shared by the shell and its contract tests.
var themes = {
    "severance": { background: "#0c171c", surface: "#15272e", foreground: "#d2e4e8", accent: "#79c9dc", muted: "#7c9aa4", radius: 16, wallpaper: "azul.jpg" },
    "tokyo": { background: "#17131f", surface: "#211b2e", foreground: "#e5dcfa", accent: "#bb9af7", muted: "#9c8fb7", radius: 24, wallpaper: "tokyo.png" },
    "space-black": { background: "#101012", surface: "#202023", foreground: "#e6e6e8", accent: "#ceced4", muted: "#919198", radius: 20, wallpaper: "space-black.png" }
};

var applications = [
    { command: "launcher", title: "Abrir lanzador", detail: "Aplicaciones, cálculo y búsqueda", icon: "search" },
    { command: "clipboard", title: "Portapapeles", detail: "Historial y búsqueda", icon: "clipboard" },
    { command: "music", title: "Música", detail: "Biblioteca y reproducción", icon: "music" },
    { command: "files", title: "Archivos", detail: "Explorar y buscar", icon: "folder-open" },
    { command: "notes", title: "Notas", detail: "Tus notas locales", icon: "file-text" },
    { command: "colors", title: "Colores", detail: "Paletas guardadas", icon: "palette" },
    { command: "screenshot", title: "Captura de pantalla", detail: "Elegir una fuente para capturar", icon: "camera" },
    { command: "recorder", title: "Grabadora", detail: "Controles de grabación", icon: "circle-play" },
    { command: "processes", title: "Procesos", detail: "Actividad del sistema", icon: "cpu" },
    { command: "tools", title: "Herramientas", detail: "Utilidades de escritorio", icon: "terminal" },
    { command: "connections", title: "Conexiones", detail: "Red y dispositivos", icon: "wifi" },
    { command: "notifications", title: "Notificaciones", detail: "Historial, acciones y concentración", icon: "bell" },
    { command: "settings", title: "Preferencias", detail: "Personalizar Wysun", icon: "settings-2" },
    { command: "power", title: "Energía y sesión", detail: "Controles de sesión", icon: "power" }
];

function themeKey(value) {
    var aliases = { azul: "severance", morado: "tokyo", Tokyo: "tokyo", Severance: "severance" };
    var key = aliases[value] || value;
    return Object.prototype.hasOwnProperty.call(themes, key) ? key : "severance";
}

function object(text) {
    var data = JSON.parse(text);
    if (data === null || typeof data !== "object" || Array.isArray(data))
        throw new Error("Se esperaba un objeto JSON");
    return data;
}

function bounded(value, low, high, fallback) {
    return typeof value === "number" && isFinite(value) ? Math.max(low, Math.min(high, value)) : fallback;
}

function appearance(data) {
    return { opacity: Math.round(bounded(data.opacity, 65, 100, 80)) / 100, reducedMotion: data.reduced_motion === true };
}

var barModules = ["orbit", "title", "workspaces", "resources", "network", "volume", "battery", "date", "notifications", "power", "tray"];

function barModulesValid(list, fallback) {
    if (!Array.isArray(list)) return fallback;
    return list.filter(function(name, index, all) {
        return barModules.indexOf(name) >= 0 && all.indexOf(name) === index;
    });
}

function barSettings(native) {
    var data = native && typeof native === "object" && !Array.isArray(native) ? native : {};
    function color(value, fallback) { return /^#[\da-fA-F]{6}$/.test(value || "") ? value : fallback; }
    var background = color(data.background, "#101118");
    var alpha = Math.round(bounded(data.opacity, 10, 100, 65) * 255 / 100);
    return {
        height: bounded(data.height, 24, 64, 36),
        offset: bounded(data.offset, 0, 60, 10),
        radius: bounded(data.radius, 0, 30, 12),
        background: "#" + ("0" + alpha.toString(16)).slice(-2) + background.slice(1),
        foreground: color(data.foreground, "#EBECF3"),
        accent: color(data.accent, "#B8C8FA"),
        left: barModulesValid(data.left, ["orbit", "workspaces"]),
        center: barModulesValid(data.center, ["title"]),
        right: barModulesValid(data.right, ["resources", "network", "volume", "battery", "date", "notifications", "power", "tray"])
    };
}

function monitorEnabled(environment, name, native) {
    var monitors = native && native.monitors && typeof native.monitors === "object" && !Array.isArray(native.monitors)
        ? native.monitors : ((environment.bar || {}).monitors || {});
    return monitors[name] !== false;
}

function trayMonitor(environment, screens, native) {
    var configured = native && typeof native.tray_monitor === "string" ? native.tray_monitor : (environment.bar || {}).tray_monitor;
    var enabled = screens.filter(function(s) { return monitorEnabled(environment, s.name, native); });
    return enabled.some(function(s) { return s.name === configured; }) ? configured : (enabled.length ? enabled[0].name : "");
}

function wallpaper(environment, name, home, fallback) {
    var values = environment.wallpaper || {}, selected = (values.monitors || {})[name] || {};
    var path = selected.path || values.default || (home + "/.local/share/backgrounds/" + fallback);
    if (typeof path !== "string") path = "";
    if (path.indexOf("~/") === 0) path = home + path.slice(1);
    // Only local files; preferences never become a remote request or a command.
    if (path[0] !== "/") path = "";
    var mode = selected.mode || values.mode || "fill";
    if (["fill", "fit", "stretch", "center"].indexOf(mode) < 0) mode = "fill";
    return { path: path, mode: mode };
}

function filteredApplications(query) {
    var needle = query.toLocaleLowerCase().trim();
    return applications.filter(function(item) {
        return (item.title + " " + item.detail + " " + item.command).toLocaleLowerCase().indexOf(needle) >= 0;
    });
}

function allowedCommand(command) {
    return ["lock", "audio", "calendar"].indexOf(command) >= 0 || applications.some(function(item) { return item.command === command; });
}

function barPresentation(width) {
    // Secondary information yields before primary controls. The configured
    // module lists stay intact; all actions remain available in the Center.
    return { showTitle: width >= 1100, showResources: width >= 1200,
        iconControls: width < 900, dateFormat: width < 1100 ? "hh:mm" : "d MMM · hh:mm" };
}

function resourceLabel(cpu, memory) {
    return "CPU " + (cpu === null || cpu === undefined ? "—" : cpu + "%")
        + " · RAM " + (memory === null || memory === undefined ? "—" : memory + "%");
}

function workspaceValue(workspace) {
    if (workspace === null || workspace === undefined) return "";
    if (typeof workspace === "object") return workspace.id !== undefined ? workspace.id : workspace.name;
    return workspace;
}

function workspaceNumber(workspace) {
    var value = workspaceValue(workspace);
    var number = parseInt(value, 10);
    return isFinite(number) && String(number) === String(value).trim() ? number : null;
}

function workspaceLabel(workspace) {
    var number = workspaceNumber(workspace);
    if (number === null) return String(workspaceValue(workspace));
    // Workspace 10 matches the SUPER+0 shortcut in the bar.
    return number === 10 ? "0" : String(number);
}

function sortWorkspaces(list) {
    var copy = (list || []).slice();
    copy.sort(function (a, b) {
        var an = workspaceNumber(a), bn = workspaceNumber(b);
        if (an !== null && bn !== null) return an - bn;
        if (an !== null) return -1;
        if (bn !== null) return 1;
        return String(workspaceValue(a)).localeCompare(String(workspaceValue(b)));
    });
    return copy;
}

function cpuSample(text, previous) {
    var fields = text.split(/\r?\n/)[0].trim().split(/\s+/).slice(1, 9).map(Number);
    if (fields.length !== 8 || fields.some(function(n) { return !isFinite(n) || n < 0; })) return null;
    var total = fields.reduce(function(a, b) { return a + b; }, 0), idle = fields[3] + fields[4];
    var delta = previous ? total - previous.total : 0;
    return { total: total, idle: idle, percent: delta > 0 && idle >= previous.idle ? Math.round(bounded(100 * (1 - (idle - previous.idle) / delta), 0, 100, 0)) : null };
}

function memoryPercent(text) {
    var total = text.match(/^MemTotal:\s+(\d+)/m), available = text.match(/^MemAvailable:\s+(\d+)/m);
    return total && available && Number(total[1]) > 0 ? Math.round(bounded(100 * (1 - Number(available[1]) / Number(total[1])), 0, 100, 0)) : null;
}

function popupScreen(screens, focusedName) {
    return screens.find(function(s) { return s.name === focusedName; }) || screens[0] || null;
}
