.pragma library

// Existing Wysun modes remain accessible from the native launcher's > search.
// These are argv arrays, never shell strings, and never replace user actions.
function utilities() {
    return [
        ["Portapapeles", "Historial, favoritos, OCR y opciones del historial", "content_paste", ["wysun", "clipboard"]],
        ["Archivos", "Carpetas, pestañas y búsqueda de archivos", "folder", ["wysun", "files"]],
        ["Snippets", "Fragmentos de texto y abreviaturas", "code", ["wysun", "snippets"]],
        ["Calculadora", "Operaciones y conversiones de Wysun", "calculate", ["wysun", "calculator"]],
        ["Emoji", "Buscar, copiar y pegar símbolos", "emoji_emotions", ["wysun", "emoji"]],
        ["Ventanas", "Buscar y enfocar ventanas abiertas", "view_carousel", ["wysun", "windows"]],
        ["Wysun Music", "Biblioteca, reproducción y descargas", "music_note", ["wysun", "music"]],
        ["Wysun Music Mini", "Controles compactos de reproducción", "album", ["wysun", "music-mini"]],
        ["Wysun Notes", "Notas locales y edición", "notes", ["wysun", "notes"]],
        ["Wysun Colors", "Capturar, convertir y guardar colores", "colorize", ["wysun", "colors"]],
        ["Wysun Processes", "Procesos y recursos del sistema", "memory", ["wysun", "processes"]],
        ["Wysun Tools", "Proyectos, diagnósticos y archivos", "terminal", ["wysun", "tools"]],
        ["Conexiones", "Wi-Fi, Ethernet, Bluetooth, VPN y SSH", "wifi", ["wysun", "connections"]],
        ["Sonido", "Volumen y dispositivos de audio", "volume_up", ["wysun", "audio"]],
        ["Notificaciones", "Historial y modo concentración", "notifications", ["wysun", "notifications"]],
        ["Calendario", "Consultar fechas", "calendar_month", ["wysun", "calendar"]],
        ["Sistema", "Memoria, carga y batería", "monitoring", ["wysun", "system"]],
        ["Sesión", "Bloqueo, suspensión y opciones de energía", "power_settings_new", ["wysun", "power"]],
        ["Wysun Recorder", "Biblioteca y controles de grabación", "videocam", ["wysun", "recorder"]],
        ["Wysun Screenshot", "Biblioteca y captura de pantalla", "screenshot", ["wysun", "screenshot"]],
        ["Wysun Settings", "Pantallas, atajos, reglas, inicio y copias", "settings", ["wysun", "settings"]],
        ["Fondo y estilo", "Cambiar el fondo y las preferencias de color", "wallpaper", ["wysun", "settings", "wallpaper"]],
        ["Efectos y animaciones", "Sombras, desenfoque y velocidad", "animation", ["wysun", "settings", "effects"]],
        ["Terminal", "Abrir la terminal configurada", "terminal", ["wysun-terminal"]],
        ["Barra lateral", "Abrir o cerrar el lateral", "dock_to_right", ["wysun", "shell", "sidebar"]]
    ].map(function(item) {
        return {name: item[0], description: item[1], icon: item[2], command: item[3], enabled: true, dangerous: false};
    });
}

function entries(configured, enableDangerous) {
    var configuredCommands = configured.map(function(action) { return JSON.stringify(action.command); });
    var added = utilities().filter(function(action) {
        return configuredCommands.indexOf(JSON.stringify(action.command)) < 0;
    });
    return configured.concat(added).filter(function(action) {
        // This inherited argv is invalid: wallpaper_main only accepts `set`.
        if (JSON.stringify(action.command) === '["wysun","wallpaper","-r"]')
            return false;
        if (!action.enabled || (action.dangerous && !enableDangerous))
            return false;
        return true;
    });
}
