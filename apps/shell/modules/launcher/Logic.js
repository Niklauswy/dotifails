// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/launcher/{Content,AppList}.qml, services/{Apps,Actions,Schemes,M3Variants}.qml
// y utils/Searcher.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
//
// Flujo de búsqueda propio: se reescribió sin copiar utils/scripts/fzf.js
// (licencia BSD) ni utils/scripts/fuzzysort.js (licencia MIT). No se ejecuta
// texto del usuario: la calculadora es un analizador acotado y las acciones
// salen de una lista cerrada.

function fold(value) {
    return String(value || "").normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase();
}

function search(list, query, fields) {
    var source = Array.isArray(list) ? list : [];
    var words = fold(query).trim().split(/\s+/).filter(Boolean);
    return source.map(function(item, index) {
        var label = fold(item && item.name);
        var text = fields.map(function(key) { return fold(item && item[key]); }).join(" ");
        var score = 0;
        for (var i = 0; i < words.length; i++) {
            var position = text.indexOf(words[i]);
            if (position < 0) return null;
            score += label === words[i] ? 100 : label.indexOf(words[i]) === 0 ? 50 : 10;
        }
        return { item: item, score: score, index: index };
    }).filter(Boolean).sort(function(a, b) { return b.score - a.score || a.index - b.index; }).map(function(row) { return row.item; });
}

// Prefixes:
//   >            actions and launcher modes
//   >calc / >scheme / >variant / >wallpaper
//   =            calculator
//   @i @c @d @e @w @g @k @t  DesktopEntry filters
function route(text) {
    text = String(text || "").replace(/^\s+/, "");
    var match = /^>\s*(calc|scheme|variant|wallpaper)(?:\s+|$)(.*)$/i.exec(text);
    if (match) return { mode: match[1].toLowerCase(), query: match[2] };
    if (text[0] === ">") return { mode: "actions", query: text.slice(1).trim() };
    if (text[0] === "=") return { mode: "calc", query: text.slice(1).trim() };
    if (/^[\d.(+-][\d\s.eE()+*/%^−-]*[+*/%^−-][\d\s.eE()+*/%^−-]*$/.test(text))
        return { mode: "calc", query: text };
    return { mode: "apps", query: text };
}

function appSearch(entries, query) {
    var fields = ["name", "genericName", "keywords", "comment"];
    var prefixes = { i: "id", c: "categories", d: "comment", e: "execString", w: "startupClass", g: "genericName", k: "keywords" };
    var match = /^@([icdewgkt])(?:\s+|$)(.*)$/i.exec(query);
    var terminalOnly = false;
    if (match) {
        terminalOnly = match[1].toLowerCase() === "t";
        fields = terminalOnly ? ["name"] : [prefixes[match[1].toLowerCase()], "name"];
        query = match[2];
    } else if (query[0] === "@") query = query.slice(1).replace(/^\s+/, "");
    return search((entries || []).filter(function(entry) {
        return entry && !entry.noDisplay && (!terminalOnly || entry.runInTerminal);
    }), query, fields);
}

function nextIndex(index, delta, count) {
    return count > 0 ? (Math.max(0, index) + delta % count + count) % count : -1;
}

// Analizador aritmético acotado. No usa eval, Function, shell, acceso a
// propiedades, asignaciones ni llamadas definidas por el usuario. Máximo 128
// tokens y 16 niveles de anidamiento.
function calculate(source) {
    try {
        if (!source || !String(source).trim()) throw Error("Escribe una expresión; por ejemplo, (12 + 3) / 5.");
        source = String(source);
        if (source.length > 256) throw Error("La expresión es demasiado larga.");
        var tokens = [], re = /\s*(?:(\d+(?:\.\d*)?|\.\d+)(?:[eE]([+-]?\d+))?|([()+*/%^−-])|(pi|e))\s*/gy;
        var offset = 0, match;
        while (offset < source.length) {
            re.lastIndex = offset;
            match = re.exec(source);
            if (!match) throw Error("Solo se admiten números, pi, e y + − * / % ^ ( ).");
            tokens.push(match[1] ? Number(match[1] + (match[2] ? "e" + match[2] : "")) : match[3] === "−" ? "-" : match[3] || match[4]);
            offset = re.lastIndex;
            if (tokens.length > 128) throw Error("La expresión contiene demasiados términos.");
        }
        var position = 0, depth = 0;
        function checked(number) {
            if (!isFinite(number) || Math.abs(number) > 1e100)
                throw Error("Resultado fuera de rango o división por cero.");
            return number;
        }
        function atom() {
            if (++depth > 16) throw Error("Demasiados niveles de paréntesis u operadores.");
            var token = tokens[position++], value;
            if (token === "+" || token === "-") value = (token === "-" ? -1 : 1) * power();
            else if (token === "(") {
                value = expression();
                if (tokens[position++] !== ")") throw Error("Falta cerrar un paréntesis.");
            } else if (token === "pi") value = Math.PI;
            else if (token === "e") value = Math.E;
            else if (typeof token === "number") value = token;
            else throw Error("Expresión incompleta o inválida.");
            depth--;
            return checked(value);
        }
        function power() {
            var result = atom();
            if (tokens[position] === "^") {
                position++;
                if (++depth > 16) throw Error("Demasiadas potencias.");
                result = checked(Math.pow(result, power()));
                depth--;
            }
            return result;
        }
        function term() {
            var result = power();
            while (["*", "/", "%"].indexOf(tokens[position]) >= 0) {
                var operator = tokens[position++], operand = power();
                result = checked(operator === "*" ? result * operand : operator === "/" ? result / operand : result % operand);
            }
            return result;
        }
        function expression() {
            var result = term();
            while (tokens[position] === "+" || tokens[position] === "-") {
                var operator = tokens[position++], operand = term();
                result = checked(operator === "+" ? result + operand : result - operand);
            }
            return result;
        }
        var value = expression();
        if (position !== tokens.length) throw Error("Expresión incompleta o inválida.");
        return { valid: true, value: Number(value.toPrecision(12)).toString(), error: "" };
    } catch (error) {
        return { valid: false, value: "", error: String(error && error.message ? error.message : error) };
    }
}

var modes = [
    { id: "calc", name: "Calcular", description: "Operaciones acotadas · >calc", completion: ">calc " },
    { id: "scheme", name: "Esquemas", description: "Material You y cinco temas alternativos", completion: ">scheme " },
    { id: "variant", name: "Variantes Material You", description: "Colores desde el fondo actual", completion: ">variant " },
    { id: "wallpaper", name: "Fondos de pantalla", description: "Ver fondos y abrir Ajustes de fondo", completion: ">wallpaper " }
];

// Allowlist: la interfaz nunca construye un comando desde el texto escrito.
var actions = [
    { id: "settings", name: "Ajustes", description: "Preferencias de Wysun", argv: ["settings"] },
    { id: "files", name: "Archivos", description: "Explorar archivos", argv: ["files"] },
    { id: "music", name: "Música", description: "Biblioteca de Wysun Music", argv: ["music"] },
    { id: "clipboard", name: "Portapapeles", description: "Historial del portapapeles", argv: ["clipboard"] },
    { id: "emoji", name: "Emojis", description: "Selector de emojis", argv: ["emoji"] },
    { id: "notes", name: "Notas", description: "Notas personales", argv: ["notes"] },
    { id: "color", name: "Colores", description: "Selector de color", argv: ["color"] },
    { id: "network", name: "Conexiones", description: "Red y Bluetooth", argv: ["network"] },
    { id: "audio", name: "Audio", description: "Volumen y dispositivos", argv: ["audio"] },
    { id: "calendar", name: "Calendario", description: "Agenda y fechas", argv: ["calendar"] },
    { id: "recorder", name: "Grabadora", description: "Biblioteca de Wysun Recorder", argv: ["recorder"] },
    { id: "screenshot", name: "Capturas", description: "Biblioteca de Wysun Screenshot", argv: ["screenshot"] },
    { id: "processes", name: "Procesos", description: "Monitor de procesos", argv: ["processes"] },
    { id: "tools", name: "Utilidades", description: "Herramientas de Wysun", argv: ["tools"] },
    { id: "notifications", name: "Notificaciones", description: "Historial de Dunst", argv: ["notifications"] },
    { id: "lock", name: "Bloquear", description: "Usar el bloqueo seguro existente", argv: ["lock"] },
    { id: "power", name: "Sesión", description: "Abrir opciones de sesión", argv: ["power"] }
];

var schemes = [
    { id: "dynamic", name: "Material You", description: "Principal · colores desde el fondo actual" },
    { id: "dynamic-light", name: "Material You claro", description: "Colores dinámicos · modo claro" },
    { id: "dynamic-dark", name: "Material You oscuro", description: "Colores dinámicos · modo oscuro" },
    { id: "space-black", name: "Space Black", description: "Esquema fijo alternativo" },
    { id: "tokyo", name: "Tokyo", description: "Space Black · esquema fijo alternativo" },
    { id: "severance", name: "Severance", description: "Space Black · esquema fijo alternativo" },
    { id: "fluent:light", name: "Fluent claro", description: "Esquema fijo alternativo" },
    { id: "fluent:dark", name: "Fluent oscuro", description: "Esquema fijo alternativo" }
];

var variants = [
    { id: "vibrant", name: "Vibrante" }, { id: "tonalspot", name: "Tonal" },
    { id: "expressive", name: "Expresivo" }, { id: "fidelity", name: "Fidelidad" },
    { id: "content", name: "Contenido" }, { id: "fruitsalad", name: "Ensalada de frutas" },
    { id: "rainbow", name: "Arcoíris" }, { id: "neutral", name: "Neutro" }, { id: "monochrome", name: "Monocromo" }
];

function actionArgv(id) {
    var action = actions.find(function(entry) { return entry.id === id; });
    return action ? ["wysun"].concat(action.argv) : [];
}

function schemeArgv(id) {
    if (!schemes.some(function(scheme) { return scheme.id === id; })) return [];
    if (id === "dynamic") return ["wysun", "scheme", "set", "--dynamic"];
    if (id.indexOf("dynamic-") === 0) return ["wysun", "scheme", "set", "--dynamic", "--mode", id.slice(8)];
    return ["wysun", "scheme", "set", id];
}

function variantArgv(id) {
    return variants.some(function(variant) { return variant.id === id; })
        ? ["wysun", "scheme", "set", "--dynamic", "--variant", id] : [];
}

function isCurrentScheme(id, dynamicActive, dynamicMode, style, variant) {
    if (dynamicActive) {
        if (id === "dynamic") return true;
        if (id === "dynamic-light") return dynamicMode === "light";
        if (id === "dynamic-dark") return dynamicMode === "dark";
        return false;
    }
    // Fixed Space Black variants use their own id; Fluent needs style:variant.
    return style === "fluent" ? id === "fluent:" + variant : id === variant;
}
