// Stable selection from Settings, never from the currently focused monitor.
function primaryName(names, displays) {
    names = names.slice().sort();
    if (!names.length) return "";
    const profiles = displays.profiles || {};
    const exact = profiles[names.join("|")];
    if (exact) {
        const primary = exact.find(p => p.enabled && p.primary && names.includes(p.name));
        return primary ? primary.name : names[0];
    }
    // A saved profile can include a disabled output, absent from Qt's screens.
    const candidates = Object.keys(profiles).sort((a, b) => a.split("|").length - b.split("|").length || a.localeCompare(b));
    for (const key of candidates) {
        if (!names.every(name => key.split("|").includes(name))) continue;
        const primary = profiles[key].find(p => p.enabled && p.primary && names.includes(p.name));
        if (primary) return primary.name;
    }
    return names[0];
}

function drawerSurface(kind) {
    return ["dashboard", "test", "windows", "menu", "quicksettings", "notifications", "sidebar", "session", "ai"].includes(kind);
}
