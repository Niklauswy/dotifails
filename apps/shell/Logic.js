.pragma library

// Pure data transformations shared by the shell and its contract tests.

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

// ---- Theme: the same selection rules as apps/wysun/theme_core.py -------------
// `spec` is the parsed wysun_theme.json (the single token source).
function themeStyles(spec) { return spec && spec.styles && typeof spec.styles === "object" ? spec.styles : {}; }

function hasKey(map, key) { return typeof key === "string" && Object.prototype.hasOwnProperty.call(map, key); }

function themeDefault(spec) {
    var d = spec && spec.default || {}, styles = themeStyles(spec);
    if (hasKey(styles, d.style) && hasKey(styles[d.style].variants, d.variant)) return { style: d.style, variant: d.variant };
    var first = Object.keys(styles)[0];
    return first ? { style: first, variant: styles[first].default_variant } : { style: "", variant: "" };
}

function variantOwner(spec, variant) {
    var styles = themeStyles(spec), names = Object.keys(styles);
    for (var i = 0; i < names.length; i++) if (hasKey(styles[names[i]].variants, variant)) return names[i];
    return "";
}

function normalizeTheme(spec, style, variant) {
    var styles = themeStyles(spec);
    if (!hasKey(styles, style)) {
        var owner = variantOwner(spec, variant);
        if (!owner) return themeDefault(spec);
        style = owner;
    }
    if (!hasKey(styles[style].variants, variant)) variant = styles[style].default_variant;
    return { style: style, variant: variant };
}

function parseTheme(spec, value) {
    if (typeof value !== "string" || !value.trim()) return null;
    value = value.trim();
    var aliases = spec && spec.aliases || {};
    if (hasKey(aliases, value)) value = aliases[value];
    var styles = themeStyles(spec);
    var separators = [":", "/"];
    for (var i = 0; i < separators.length; i++) {
        var at = value.indexOf(separators[i]);
        if (at >= 0) {
            var style = value.slice(0, at);
            return hasKey(styles, style) ? normalizeTheme(spec, style, value.slice(at + 1)) : null;
        }
    }
    if (hasKey(styles, value)) return normalizeTheme(spec, value, "");
    var owner = variantOwner(spec, value);
    return owner ? { style: owner, variant: value } : null;
}

// Selection from the environment override (WYSUN_THEME, then ORBIT_THEME) or theme.json
// ({"style","variant"}, or the legacy {"id"}).
function selectTheme(spec, data, override) {
    var chosen = parseTheme(spec, override);
    if (chosen) return chosen;
    data = data && typeof data === "object" && !Array.isArray(data) ? data : {};
    var styles = themeStyles(spec);
    if (hasKey(styles, data.style)) return normalizeTheme(spec, data.style, data.variant);
    if (typeof data.style === "string" || typeof data.variant === "string")
        return parseTheme(spec, data.variant) || themeDefault(spec);
    return parseTheme(spec, data.id !== undefined ? data.id : data.name) || themeDefault(spec);
}

// Flat token map for one variant: style shape + variant colours, material and names.
function resolveTheme(spec, style, variant) {
    var chosen = normalizeTheme(spec, style, variant), styles = themeStyles(spec);
    if (!hasKey(styles, chosen.style)) return {};
    var entry = styles[chosen.style], found = entry.variants[chosen.variant] || {}, result = {};
    var shape = entry.shape || {}, colors = found.colors || {};
    Object.keys(shape).forEach(function(key) { result[key] = shape[key]; });
    Object.keys(colors).forEach(function(key) { result[key] = colors[key]; });
    if (found.material) result.material = found.material;
    result.wallpaper = found.wallpaper || "";
    result.style = chosen.style;
    result.variant = chosen.variant;
    result.name = found.name || chosen.variant;
    result.style_name = entry.name || chosen.style;
    return result;
}

// Token colours are CSS-ordered (#RRGGBB or #RRGGBBAA); QML wants #AARRGGBB.
function qmlColor(value, fallback) {
    var text = String(value === undefined ? "" : value);
    if (/^#[0-9a-fA-F]{6}$/.test(text)) return text;
    if (/^#[0-9a-fA-F]{8}$/.test(text)) return "#" + text.slice(7, 9) + text.slice(1, 7);
    return fallback || "#00000000";  // theme-exception: transparent when a token is missing
}

function tokenNumber(tokens, name, fallback) {
    var value = tokens && tokens[name];
    return typeof value === "number" && isFinite(value) ? value : fallback;
}

// First family of the token list that is installed (Qt takes one family per font).
function tokenFont(tokens, installed) {
    var family = tokens && tokens.font_family;
    if (!Array.isArray(family) || !family.length) return "Inter";
    var available = Array.isArray(installed) ? installed : [];
    for (var i = 0; i < family.length; i++) if (available.indexOf(family[i]) >= 0) return String(family[i]);
    return String(family[family.length - 1]);
}

// Window material opacity: the user's preference for glass, solid for Fluent.
function surfaceOpacity(tokens, opacity) { return tokens && tokens.translucent === false ? 1 : opacity; }

function object(text) {
    var data = JSON.parse(text);
    if (data === null || typeof data !== "object" || Array.isArray(data))
        throw new Error("Se esperaba un objeto JSON");
    return data;
}

function bounded(value, low, high, fallback) {
    return typeof value === "number" && isFinite(value) ? Math.max(low, Math.min(high, value)) : fallback;
}

// Low power (shell.json) implies reduced motion, so the shell stops animating without a second switch.
function appearance(data, shell) {
    var lowPower = !!shell && typeof shell === "object" && shell.low_power === true;
    return { opacity: Math.round(bounded(data.opacity, 65, 100, 80)) / 100, reducedMotion: data.reduced_motion === true || lowPower };
}

function shellValid(shell) {
    return !!shell && typeof shell === "object" && !Array.isArray(shell) && shell.schema_version === 1;
}

// shell.json is the single structure file. Until it exists (or when its version is unknown) the
// previous hypr-bar.json keeps answering for monitors and tray, so nothing is lost mid-migration.
function shellLayout(shell, legacy) {
    if (!shellValid(shell)) return legacy && typeof legacy === "object" && !Array.isArray(legacy) ? legacy : {};
    return {
        monitors: shell.monitors && typeof shell.monitors === "object" && !Array.isArray(shell.monitors) ? shell.monitors : {},
        tray_monitor: typeof shell.tray_monitor === "string" ? shell.tray_monitor : ""
    };
}

function shellSettings(shell) {
    var valid = shellValid(shell);
    return {
        railEnabled: !valid || shell.rail_enabled !== false,
        frameEnabled: !valid || shell.frame_enabled !== false,
        lowPower: valid && shell.low_power === true,
        primaryMonitor: valid && typeof shell.primary_monitor === "string" ? shell.primary_monitor : ""
    };
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
    // Colours are the user's own choice; an empty value follows the active theme.
    var background = color(data.background, "");
    var alpha = Math.round(bounded(data.opacity, 10, 100, 65) * 255 / 100);
    return {
        height: bounded(data.height, 24, 64, 36),
        offset: bounded(data.offset, 0, 60, 10),
        radius: bounded(data.radius, 0, 30, 12),
        background: background ? "#" + ("0" + alpha.toString(16)).slice(-2) + background.slice(1) : "",
        opacity: alpha / 255,
        foreground: color(data.foreground, ""),
        accent: color(data.accent, ""),
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

// Dynamic shell palette contract. Caelestia writes `colours` without a '#';
// Wysun also accepts `colors` and m3-prefixed roles for painless handoff.
var materialColourRoles = [
    "primary", "onPrimary", "primaryContainer", "onPrimaryContainer", "inversePrimary",
    "secondary", "onSecondary", "secondaryContainer", "onSecondaryContainer",
    "tertiary", "onTertiary", "tertiaryContainer", "onTertiaryContainer",
    "background", "onBackground", "surface", "surfaceDim", "surfaceBright",
    "surfaceContainerLowest", "surfaceContainerLow", "surfaceContainer",
    "surfaceContainerHigh", "surfaceContainerHighest", "onSurface", "surfaceVariant",
    "onSurfaceVariant", "inverseSurface", "inverseOnSurface", "outline", "outlineVariant",
    "shadow", "scrim", "surfaceTint", "error", "onError", "errorContainer", "onErrorContainer"
];

// theme-exception-begin: transparent fallbacks are only used when a theme token has not loaded
function fixedSchemeRoles(tokens) {
    tokens = tokens && typeof tokens === "object" ? tokens : {};
    function pick(name, fallback) { return qmlColor(tokens[name], fallback); }
    var primary = pick("accent", "#00000000");
    var surface = pick("surface", "#00000000");
    var raised = pick("surface_raised", surface);
    var well = pick("well", surface);
    var text = pick("text", "#00000000");
    var muted = pick("muted", text);
    var line = pick("line", muted);
    var error = pick("danger", primary);
    return {
        primary: primary, onPrimary: pick("on_accent", text),
        primaryContainer: pick("selection", raised), onPrimaryContainer: pick("selection_text", text),
        secondary: primary, onSecondary: pick("on_accent", text),
        secondaryContainer: raised, onSecondaryContainer: text,
        tertiary: primary, onTertiary: pick("on_accent", text),
        tertiaryContainer: raised, onTertiaryContainer: text,
        background: pick("canvas", surface), onBackground: text,
        surface: surface, surfaceDim: pick("canvas", surface), surfaceBright: raised,
        surfaceContainerLowest: pick("canvas", surface), surfaceContainerLow: well,
        surfaceContainer: surface, surfaceContainerHigh: raised, surfaceContainerHighest: raised,
        onSurface: text, surfaceVariant: well, onSurfaceVariant: muted,
        inverseSurface: text, inverseOnSurface: surface,
        outline: line, outlineVariant: line, shadow: pick("scrim", "#00000000"),
        scrim: pick("scrim", "#00000000"), surfaceTint: primary,
        error: error, onError: pick("on_danger", text),
        errorContainer: pick("danger", error), onErrorContainer: text
    };
}
// theme-exception-end

function schemePalette(data, fallbackTokens) {
    var fallback = fixedSchemeRoles(fallbackTokens);
    if (!data || typeof data !== "object" || Array.isArray(data))
        return { valid: false, roles: fallback, mode: "", name: "", variant: "" };
    var name = typeof data.name === "string" ? data.name.trim() : "";
    var variant = typeof data.variant === "string" ? data.variant.trim() : (typeof data.flavour === "string" ? data.flavour.trim() : "");
    var mode = data.mode === "light" || data.mode === "dark" ? data.mode : "";
    var source = data.colours && typeof data.colours === "object" ? data.colours : data.colors;
    if (!name || !variant || !mode || !source || typeof source !== "object" || Array.isArray(source))
        return { valid: false, roles: fallback, mode: "", name: "", variant: "" };
    var roles = {}, found = 0;
    materialColourRoles.forEach(function(role) {
        var value = source[role];
        if (value === undefined) value = source["m3" + role];
        if (typeof value !== "string" || !/^(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/.test(value)) return;
        roles[role] = qmlColor("#" + value);
        found++;
    });
    if (!roles.primary || !roles.onPrimary || !roles.surface || !roles.surfaceContainer || found < 4)
        return { valid: false, roles: fallback, mode: "", name: "", variant: "" };
    // Optional roles inherit the selected fixed theme; new producers can add
    // roles without making older schemes render with transparent defaults.
    materialColourRoles.forEach(function(role) {
        if (!roles[role]) roles[role] = fallback[role] || fallback.surface;
    });
    return { valid: true, roles: roles, mode: mode, name: name, variant: variant };
}
