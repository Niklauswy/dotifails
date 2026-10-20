.pragma library

function configHome(xdgConfigHome, home) {
    return typeof xdgConfigHome === "string" && xdgConfigHome.length > 0
        ? xdgConfigHome : home + "/.config";
}

function orbitFile(configHomePath, filename) {
    return configHomePath + "/orbit/" + filename;
}
