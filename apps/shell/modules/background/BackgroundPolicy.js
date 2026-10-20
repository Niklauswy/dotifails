.pragma library
// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// services/Wallpapers.qml y modules/background/Background.qml, commit
// 507d66285e9d9fde9330adc64159cfdebb28c19a. Véanse THIRD_PARTY.md y LICENSES/GPL-3.0.txt.

function object(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function clockSettings(environment, outputName, fullscreen) {
    var wallpaper = object(object(environment).wallpaper);
    var local = object(object(wallpaper.monitors)[outputName]);
    var globalClock = object(wallpaper.clock), localClock = object(local.clock);
    var enabled = localClock.enabled === undefined ? globalClock.enabled : localClock.enabled;
    var position = localClock.position || globalClock.position || "top-left";
    if (!/^(top|middle|bottom)-(left|center|right)$/.test(position)) position = "top-left";
    return { enabled: enabled === true && fullscreen !== true, position: position };
}

function localUrl(path) {
    // No remote content, user commands, video, captures or colour generation.
    if (typeof path !== "string" || path[0] !== "/" || /[\x00-\x1f\x7f]/.test(path)) return "";
    return "file://" + encodeURI(path).replace(/#/g, "%23").replace(/\?/g, "%3F");
}

function position(areaWidth, areaHeight, width, height, margin, place) {
    var parts = place.split("-");
    var left = Math.min(margin, Math.max(0, (areaWidth - width) / 2));
    var top = Math.min(margin, Math.max(0, (areaHeight - height) / 2));
    return {
        x: parts[1] === "center" ? Math.max(0, (areaWidth - width) / 2) :
            parts[1] === "right" ? Math.max(0, areaWidth - width - left) : left,
        y: parts[0] === "middle" ? Math.max(0, (areaHeight - height) / 2) :
            parts[0] === "bottom" ? Math.max(0, areaHeight - height - top) : top
    };
}
