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

function ini(text) {
    var result = {}, section = "";
    text.split(/\r?\n/).forEach(function(line) {
        var header = line.match(/^\s*\[([^\]]+)\]\s*$/);
        if (header) { section = header[1]; result[section] = {}; return; }
        var entry = line.match(/^\s*([^;#=][^=]*?)\s*=\s*(.*?)\s*$/);
        if (entry && result[section]) result[section][entry[1]] = entry[2];
    });
    return result;
}

function barSettings(text, native) {
    var data = ini(text), bar = data["bar/base"] || {};
    var colors = data.colors || {};
    function modules(section, key, fallback) {
        var raw = (data[section] || {})[key];
        var known = ["orbit", "title", "bspwm", "resources", "network", "volume", "battery", "date", "notifications", "power", "tray"];
        return raw === undefined ? fallback : raw.split(/\s+/).filter(function(name, index, list) { return known.indexOf(name) >= 0 && list.indexOf(name) === index; });
    }
    function color(value) { return /^#[\da-fA-F]{6}([\da-fA-F]{2})?$/.test(value || "") ? value : ""; }
    var result = {
        height: bounded(Number(bar.height), 24, 64, 36),
        offset: bounded(Number(bar["offset-y"]), 0, 60, 10),
        radius: bounded(Number(bar.radius), 0, 30, 12),
        background: color(colors.bg), foreground: color(colors.fg), accent: color(colors.accent),
        left: modules("bar/left", "modules-left", ["orbit", "title"]),
        center: modules("bar/center", "modules-center", ["bspwm"]),
        right: modules("bar/right", "modules-right", ["resources", "network", "volume", "battery", "date", "notifications", "power", "tray"])
    };
    if (!native || typeof native !== "object" || Array.isArray(native)) return result;
    result.height = bounded(native.height, 24, 64, result.height);
    result.offset = bounded(native.offset, 0, 60, result.offset);
    result.radius = bounded(native.radius, 0, 30, result.radius);
    ["foreground", "accent"].forEach(function(key) {
        if (/^#[\da-fA-F]{6}$/.test(native[key] || "")) result[key] = native[key];
    });
    var nativeBackground = /^#[\da-fA-F]{6}$/.test(native.background || "") ? native.background : "";
    if (nativeBackground || typeof native.opacity === "number") {
        var background = nativeBackground || (result.background ? "#" + result.background.slice(-6) : themes.severance.background);
        var fallbackOpacity = result.background ? (result.background.length === 9 ? parseInt(result.background.slice(1, 3), 16) * 100 / 255 : 100) : 80;
        var alpha = Math.round(bounded(native.opacity, 10, 100, fallbackOpacity) * 255 / 100);
        result.background = "#" + ("0" + alpha.toString(16)).slice(-2) + background.slice(1);
    }
    ["left", "center", "right"].forEach(function(side) {
        if (Array.isArray(native[side])) {
            var known = ["orbit", "title", "bspwm", "resources", "network", "volume", "battery", "date", "notifications", "power", "tray"];
            result[side] = native[side].filter(function(name, index, list) { return known.indexOf(name) >= 0 && list.indexOf(name) === index; });
        }
    });
    return result;
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
